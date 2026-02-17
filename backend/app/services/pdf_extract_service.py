import pdfplumber
import pandas as pd
from typing import Dict, List, Any


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

        return {
            "total_pages": total_pages,
            "tables_found": len(tables_data),
            "tables": tables_data,
        }

    def extract_to_excel(self, pdf_path: str, output_path: str, page_indices: List[int] = None) -> str:
        """
        Extrai tabelas e salva como arquivo Excel.
        """
        result = self.extract_tables(pdf_path, page_indices)

        if not result["tables"]:
            # Se não achar nada, cria um Excel vazio com aviso (comportamento original)
            with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
                pd.DataFrame(["Nenhuma tabela encontrada"]).to_excel(writer, sheet_name="Info", header=False, index=False)
            return output_path

        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            for i, table_data in enumerate(result["tables"]):
                # Criar DataFrame
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

                # Salvar no Excel
                df.to_excel(writer, sheet_name=sheet_name, index=False)

        return output_path
