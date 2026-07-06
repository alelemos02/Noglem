import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Any, Optional

import pdfplumber
import pandas as pd

logger = logging.getLogger(__name__)

# Render DPI para páginas escaneadas antes de mandar pro Gemini. 150 mantém o OCR
# preciso (testado no instrument index) e é mais rápido/leve que 200.
OCR_RENDER_DPI = 150
# As páginas de um chunk são OCR'd em paralelo. O frontend limita o chunk a poucas
# páginas para o request caber no timeout do Vercel (~60s); 5 workers cobrem isso.
OCR_MAX_WORKERS = 5
# Fração mínima da página coberta por uma imagem para tratá-la como scan. Scans
# "pesquisáveis" (imagem da tabela + camada de texto de OCR por cima) têm a imagem
# cobrindo a página inteira e nenhuma linha vetorial de grade.
IMAGE_PAGE_MIN_COVERAGE = 0.5

_OCR_PROMPT = (
    "Você está extraindo dados tabulares da imagem de UMA página de um documento "
    "técnico de engenharia escaneado (ex.: instrument index, lista de cabos, folha "
    "de dados). Extraia TODAS as tabelas visíveis na página.\n"
    "Responda APENAS com JSON neste formato:\n"
    '{"tables": [{"headers": ["coluna 1", "coluna 2", ...], '
    '"rows": [["celula", "celula", ...], ...]}]}\n'
    "Regras:\n"
    "- Preserve a ordem das colunas exatamente como aparecem.\n"
    "- Cada linha de rows deve ter o mesmo número de elementos que headers; use \"\" para célula vazia.\n"
    "- Transcreva o texto fielmente; não invente, não resuma e não traduza valores.\n"
    "- Ignore o carimbo/título do desenho e blocos de assinatura se não fizerem parte da tabela principal.\n"
    '- Se não houver tabela, responda {"tables": []}.'
)

_ocr_model = None
_ocr_available: Optional[bool] = None


def _get_ocr_model():
    """Carrega o modelo Gemini de visão sob demanda (mesmo padrão do pdf_comments_service)."""
    global _ocr_model, _ocr_available
    if _ocr_available is False:
        return None
    if _ocr_model is not None:
        return _ocr_model

    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        _ocr_available = False
        return None

    try:
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        _ocr_model = genai.GenerativeModel("gemini-3.5-flash")
        _ocr_available = True
        return _ocr_model
    except Exception:
        logger.exception("Falha ao inicializar o modelo Gemini para OCR")
        _ocr_available = False
        return None


def _is_image_page(page) -> bool:
    """True se a tabela da página está numa imagem (scan), não em texto/grade vetorial.

    pdfplumber só extrai tabela a partir de linhas vetoriais (``lines``/``rects``) ou do
    alinhamento do texto. Num scan "pesquisável" não há grade vetorial e o texto é uma
    camada de OCR ruidosa — ``extract_tables`` retorna vazio. Detectamos esse caso
    (imagem cobrindo a página + sem grade) para mandar a página pro OCR via Gemini, em
    vez de descartá-la silenciosamente só porque ela tem uma camada de texto embutida.
    """
    if page.lines or page.rects:  # PDF digital de verdade desenha a grade com vetores
        return False
    if not page.images:
        return False
    area = (page.width or 0) * (page.height or 0)
    if area <= 0:
        return False
    coverage = max(img["width"] * img["height"] for img in page.images) / area
    return coverage >= IMAGE_PAGE_MIN_COVERAGE


def _normalize_ocr_tables(raw: Any) -> List[Dict[str, Any]]:
    """Normaliza a resposta do Gemini em tabelas retangulares (rows do tamanho de headers)."""
    if isinstance(raw, dict):
        raw = raw.get("tables", [])
    if not isinstance(raw, list):
        return []

    out: List[Dict[str, Any]] = []
    for t in raw:
        if not isinstance(t, dict):
            continue
        headers = [str(h) if h is not None else "" for h in (t.get("headers") or [])]
        width = len(headers)
        if width == 0:
            continue
        rows = []
        for row in (t.get("rows") or []):
            if not isinstance(row, list):
                continue
            cells = [str(c) if c is not None else "" for c in row]
            # Garante retangularidade (pandas exige len(row) == len(headers))
            if len(cells) < width:
                cells += [""] * (width - len(cells))
            elif len(cells) > width:
                cells = cells[:width]
            rows.append(cells)
        if rows:
            out.append({"headers": headers, "rows": rows})
    return out


def _ocr_image_to_tables(model, png_bytes: bytes) -> List[Dict[str, Any]]:
    """Manda a imagem da página pro Gemini e devolve as tabelas estruturadas."""
    try:
        response = model.generate_content(
            [_OCR_PROMPT, {"mime_type": "image/png", "data": png_bytes}],
            generation_config={
                "temperature": 0,
                "response_mime_type": "application/json",
            },
        )
        text = (response.text or "").strip()
        if not text:
            return []
        return _normalize_ocr_tables(json.loads(text))
    except Exception:
        logger.exception("Falha no OCR de uma página via Gemini")
        return []


class PdfExtractService:
    def extract_tables(self, pdf_path: str, page_indices: List[int] = None) -> Dict[str, Any]:
        """
        Extrai tabelas de um PDF com robustez e opção de seleção de páginas.
        Args:
            pdf_path: Caminho do arquivo PDF.
            page_indices: Lista opcional de índices de página (0-indexed) para processar.
        """
        tables_data = []
        total_pages = 0
        scanned_pages: List[tuple[int, int]] = []  # (page_num_1based, page_idx_0based)

        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)

            # Determinar quais páginas processar
            if page_indices is None:
                pages_to_process = [(i, p) for i, p in enumerate(pdf.pages)]
            else:
                pages_to_process = []
                for idx in page_indices:
                    if 0 <= idx < total_pages:
                        pages_to_process.append((idx, pdf.pages[idx]))

            for page_idx, page in pages_to_process:
                # page_num é 1-based para exibição
                page_num = page.page_number

                # Página escaneada → OCR via Gemini. Cobre tanto o scan puro (sem
                # texto embutido) quanto o scan "pesquisável" (imagem da tabela com
                # camada de OCR por cima): nos dois casos a tabela está na imagem e o
                # pdfplumber não consegue extrair dela.
                if not page.chars or _is_image_page(page):
                    scanned_pages.append((page_num, page_idx))
                    continue

                tables = page.extract_tables()

                for table_idx, table in enumerate(tables):
                    if not table or len(table) < 1:
                        continue

                    # Robust Header Handling (Lógica do original)
                    headers = []
                    rows = []
                    
                    if len(table) > 1:
                        raw_headers = table[0]
                        data_rows = table[1:]
                        
                        # Sanitize headers
                        counts = {}
                        for h in raw_headers:
                            # Handle None or whitespace
                            if h is None or str(h).strip() == "":
                                base_name = "Unnamed"
                            else:
                                base_name = str(h).strip()
                            
                            # Handle duplicates
                            if base_name in counts:
                                counts[base_name] += 1
                                headers.append(f"{base_name}.{counts[base_name]}")
                            else:
                                counts[base_name] = 0
                                headers.append(base_name)
                        
                        # Process rows calling str() on cells to avoid errors
                        for row in data_rows:
                            cleaned_row = [str(cell) if cell is not None else "" for cell in row]
                            rows.append(cleaned_row)
                    else:
                        # Tabela com apenas uma linha ou sem header claro
                        # Criar headers genéricos 0, 1, 2...
                        headers = [str(i) for i in range(len(table[0]))]
                        rows = [[str(cell) if cell is not None else "" for cell in table[0]]]

                    tables_data.append(
                        {
                            "page": page_num,
                            "table_index": table_idx,
                            "headers": headers,
                            "rows": rows,
                        }
                    )

        # OCR das páginas escaneadas (via Gemini) e merge no resultado.
        if scanned_pages:
            tables_data.extend(self._ocr_scanned_pages(pdf_path, scanned_pages))

        # Ordena por página e índice para preview/Excel consistentes.
        tables_data.sort(key=lambda t: (t["page"], t["table_index"]))

        return {
            "total_pages": total_pages,
            "tables_found": len(tables_data),
            "tables": tables_data,
        }

    def _ocr_scanned_pages(
        self, pdf_path: str, scanned_pages: List[tuple[int, int]]
    ) -> List[Dict[str, Any]]:
        """Renderiza páginas sem texto e extrai tabelas delas via Gemini (em paralelo)."""
        model = _get_ocr_model()
        if model is None:
            logger.warning(
                "%d página(s) escaneada(s) ignorada(s): Gemini OCR indisponível "
                "(GOOGLE_API_KEY ausente?)",
                len(scanned_pages),
            )
            return []

        # Renderiza sequencialmente (PyMuPDF não é thread-safe no mesmo documento);
        # o OCR — que é a parte lenta — roda em paralelo.
        import fitz  # PyMuPDF

        rendered: List[tuple[int, bytes]] = []
        doc = fitz.open(pdf_path)
        try:
            for page_num, page_idx in scanned_pages:
                pix = doc[page_idx].get_pixmap(dpi=OCR_RENDER_DPI)
                rendered.append((page_num, pix.tobytes("png")))
        finally:
            doc.close()

        def _task(item: tuple[int, bytes]) -> List[Dict[str, Any]]:
            page_num, png = item
            tables = _ocr_image_to_tables(model, png)
            return [
                {
                    "page": page_num,
                    "table_index": ti,
                    "headers": t["headers"],
                    "rows": t["rows"],
                }
                for ti, t in enumerate(tables)
            ]

        out: List[Dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=OCR_MAX_WORKERS) as executor:
            for res in executor.map(_task, rendered):
                out.extend(res)
        return out

    def extract_to_excel(self, pdf_path: str, output_path: str, page_indices: List[int] = None) -> str:
        """
        Extrai tabelas e salva como arquivo Excel.
        """
        result = self.extract_tables(pdf_path, page_indices)
        return self.tables_to_excel(result["tables"], output_path)

    def tables_to_excel(self, tables: List[Dict[str, Any]], output_path: str) -> str:
        """
        Escreve uma lista de tabelas já extraídas como arquivo Excel.
        Compartilhado entre a extração direta e o fluxo de auto-split (que envia
        as tabelas já extraídas em JSON, pois o PDF original é grande demais).
        """
        if not tables:
            # Se não achar nada, cria um Excel vazio com aviso (comportamento original)
            with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
                pd.DataFrame(["Nenhuma tabela encontrada"]).to_excel(writer, sheet_name="Info", header=False, index=False)
            return output_path

        used_names = {}
        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            for table_data in tables:
                # Se rows for vazio mas tiver headers, cria vazio. Se ambos vazios, pula.
                if not table_data["headers"] and not table_data["rows"]:
                    continue

                df = pd.DataFrame(table_data["rows"], columns=table_data["headers"])

                # Nome da sheet (máximo 31 caracteres)
                # Formato original: "Pág X - Tab Y"
                sheet_name = f"Pag {table_data['page']} - Tab {table_data['table_index'] + 1}"
                # Remover caracteres inválidos para Excel se necessário (:[])?/*\
                for char in [':', '[', ']', '?', '/', '*', '\\']:
                    sheet_name = sheet_name.replace(char, '')
                sheet_name = sheet_name[:31]

                # Garantir unicidade do nome (auto-split pode gerar páginas repetidas)
                if sheet_name in used_names:
                    used_names[sheet_name] += 1
                    suffix = f" ({used_names[sheet_name]})"
                    sheet_name = sheet_name[: 31 - len(suffix)] + suffix
                else:
                    used_names[sheet_name] = 0

                # Salvar no Excel
                df.to_excel(writer, sheet_name=sheet_name, index=False)

        return output_path
