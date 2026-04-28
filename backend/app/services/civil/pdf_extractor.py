"""Extração de dados geométricos de PDFs de desenhos de fundação de tanques."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

from .geometry_parser import (
    classify_radii,
    extract_all_radii,
    extract_document_id,
    extract_tank_tags,
    parse_dimension_cm,
    parse_elevation,
    parse_pile_length,
    parse_pile_spec,
    split_plan_section,
)
from .models import ConfigProjeto, ElementoFundacao, GeometriaExtraida

logger = logging.getLogger(__name__)

_PT_TO_M_BASE = 25.4 / 72000
_CIRCLE_SQUARENESS = 0.05
_R_BASE_MIN, _R_BASE_MAX = 3.0, 20.0
_R_POCO_MIN, _R_POCO_MAX = 0.5, 1.5


class ExtractionError(Exception):
    """Levantada quando não é possível extrair dados suficientes do PDF."""


class PDFExtractor:
    """Extrai geometria de fundação de PDFs de desenhos técnicos Petrobras.

    Estratégia em quatro camadas:
    1. pdfplumber / PyMuPDF — texto nativo
    2. PyMuPDF words — anotações de elevação
    3. OCR (pytesseract) — texto nas vistas gráficas
    4. Análise vetorial — círculos nos caminhos vetoriais
    """

    CAMPOS_OBRIGATORIOS: dict[str, list[str]] = {
        "BASE": ["raio", "altura"],
        "POÇO": ["raio", "altura"],
        "ESTACAS": ["quantidade", "comprimento"],
    }

    def __init__(self, config: ConfigProjeto) -> None:
        self.config = config

    def extract(self, pdf_path: Path) -> GeometriaExtraida:
        logger.info("[1/4] Texto nativo (pdfplumber): %s", pdf_path.name)
        text = self._extract_text_pdfplumber(pdf_path)
        if len(text) < self.config.threshold_texto_pdf:
            text = self._extract_text_pymupdf(pdf_path)

        logger.info("[2/4] Elevações via PyMuPDF words")
        el_text = self._extract_elevacoes_pymupdf(pdf_path)
        if el_text:
            text = text + "\n" + el_text

        if "ESTACA" not in text.upper() or len(text) < 500:
            logger.info("[3/4] OCR — anotações gráficas não encontradas no texto nativo")
            ocr = self._extract_text_ocr(pdf_path)
            if ocr:
                text = text + "\n" + ocr
        else:
            logger.info("[3/4] OCR — pulado (texto nativo suficiente)")

        if len(text) < self.config.threshold_texto_pdf:
            raise ExtractionError(
                f"O PDF '{pdf_path.name}' não contém texto suficiente ({len(text)} chars)."
            )

        logger.info("[4/4] Raios via caminhos vetoriais (círculos)")
        scale = self._extract_scale_from_text(text)
        vector_radii = self._extract_circles_from_vectors(pdf_path, scale)

        geo = self._parse_text(text, pdf_path.stem)
        self._patch_radii_from_vectors(geo, vector_radii)

        return geo

    def find_missing_fields(self, geo: GeometriaExtraida) -> list[str]:
        missing: list[str] = []
        for nome_elemento, campos in self.CAMPOS_OBRIGATORIOS.items():
            item = self._encontrar_item(geo, nome_elemento)
            for campo in campos:
                valor = getattr(item, campo, None) if item else None
                if valor is None:
                    missing.append(f"{nome_elemento}.{campo}")
        return missing

    def apply_manual_values(
        self, geo: GeometriaExtraida, valores: dict[str, float | int | str]
    ) -> None:
        for chave, valor in valores.items():
            partes = chave.split(".", 1)
            if len(partes) != 2:
                continue
            nome_elem, campo = partes
            item = self._encontrar_item(geo, nome_elem)
            if item is None:
                item = ElementoFundacao(item=nome_elem)
                geo.itens.append(item)
            try:
                setattr(item, campo, valor)
            except Exception as exc:
                logger.warning("Não foi possível setar %s.%s = %s: %s", nome_elem, campo, valor, exc)

    def _extract_text_pdfplumber(self, pdf_path: Path) -> str:
        try:
            import pdfplumber  # type: ignore
            with pdfplumber.open(pdf_path) as pdf:
                partes: list[str] = []
                for page in pdf.pages:
                    texto = page.extract_text()
                    if texto:
                        partes.append(texto)
            return "\n".join(partes)
        except Exception as exc:
            logger.warning("pdfplumber falhou: %s", exc)
            return ""

    def _extract_text_pymupdf(self, pdf_path: Path) -> str:
        try:
            import fitz  # type: ignore
            doc = fitz.open(str(pdf_path))
            partes: list[str] = []
            for page in doc:
                partes.append(page.get_text())
            doc.close()
            return "\n".join(partes)
        except Exception as exc:
            logger.warning("PyMuPDF falhou: %s", exc)
            return ""

    def _extract_elevacoes_pymupdf(self, pdf_path: Path) -> str:
        try:
            import fitz  # type: ignore
            doc = fitz.open(str(pdf_path))
            page = doc[0]
            words = page.get_text("words")
            doc.close()

            elevacoes: list[str] = []
            for w in words:
                token = w[4]
                if re.match(r'^[+-]\d+[,\.]\d{1,3}$', token):
                    elevacoes.append(f"EL. {token}")

            return "\n".join(elevacoes)
        except Exception as exc:
            logger.warning("Extração de elevações PyMuPDF falhou: %s", exc)
            return ""

    def _extract_text_ocr(self, pdf_path: Path) -> str:
        try:
            import fitz  # type: ignore
            import pytesseract  # type: ignore
            from PIL import Image  # type: ignore

            doc = fitz.open(str(pdf_path))
            partes: list[str] = []
            for page in doc:
                mat = fitz.Matrix(300 / 72, 300 / 72)
                pix = page.get_pixmap(matrix=mat, colorspace=fitz.csGRAY)
                img = Image.frombytes("L", [pix.width, pix.height], pix.samples)
                ocr_text = pytesseract.image_to_string(
                    img, lang="por+eng", config="--psm 11 --oem 3"
                )
                partes.append(ocr_text)
            doc.close()
            return "\n".join(partes)
        except ImportError:
            logger.warning("pytesseract ou Pillow não instalado; OCR desativado")
            return ""
        except Exception as exc:
            logger.warning("OCR falhou: %s", exc)
            return ""

    def _extract_scale_from_text(self, text: str) -> int:
        m = re.search(r'1\s*:\s*(\d+)', text)
        return int(m.group(1)) if m else 50

    def _extract_circles_from_vectors(self, pdf_path: Path, scale: int) -> dict[str, float]:
        try:
            import fitz  # type: ignore

            pt_to_m = scale * _PT_TO_M_BASE

            doc = fitz.open(str(pdf_path))
            page = doc[0]
            drawings = page.get_drawings()
            doc.close()

            radii_m: list[float] = []
            for d in drawings:
                r = d["rect"]
                w = r.width
                h = r.height
                if w < 10 or h < 10:
                    continue
                if abs(w - h) / max(w, h) > _CIRCLE_SQUARENESS:
                    continue
                radius_m = round(w / 2 * pt_to_m, 4)
                radii_m.append(radius_m)

            radii_unique = self._dedup_radii(radii_m, tol=0.01)
            radii_unique.sort(reverse=True)

            result: dict[str, float] = {}

            for r in radii_unique:
                if _R_BASE_MIN <= r <= _R_BASE_MAX:
                    result["r_base"] = r
                    break

            poco_candidatos = sorted(
                [r for r in radii_unique if _R_POCO_MIN <= r <= _R_POCO_MAX]
            )
            anel_encontrado = False
            esp = self.config.esp_parede_poco
            for i in range(len(poco_candidatos) - 1, 0, -1):
                for j in range(i - 1, -1, -1):
                    diff = poco_candidatos[i] - poco_candidatos[j]
                    if 0.05 <= diff <= 0.30:
                        result["r_ext_parede"] = poco_candidatos[i]
                        result["r_poco"] = poco_candidatos[j]
                        anel_encontrado = True
                        break
                if anel_encontrado:
                    break

            if not anel_encontrado and poco_candidatos:
                result["r_poco"] = poco_candidatos[0]

            return result

        except Exception as exc:
            logger.warning("Extração vetorial de círculos falhou: %s", exc)
            return {}

    @staticmethod
    def _dedup_radii(radii: list[float], tol: float = 0.01) -> list[float]:
        if not radii:
            return []
        sorted_r = sorted(radii)
        unique: list[float] = [sorted_r[0]]
        for r in sorted_r[1:]:
            if abs(r - unique[-1]) > tol:
                unique.append(r)
        return unique

    def _patch_radii_from_vectors(self, geo: GeometriaExtraida, vector_radii: dict[str, float]) -> None:
        if not vector_radii:
            return

        base = self._encontrar_item(geo, "BASE")
        poco = self._encontrar_item(geo, "POÇO")
        parede = self._encontrar_item(geo, "PAREDE DO POÇO")
        parede_int = self._encontrar_item(geo, "PAREDE INTERNA DO POÇO")
        parede_ext = self._encontrar_item(geo, "PAREDE EXTERNA DO POÇO")
        laje = self._encontrar_item(geo, "LAJE DO POÇO")

        if base and base.raio is None and "r_base" in vector_radii:
            base.raio = vector_radii["r_base"]

        if poco and poco.raio is None and "r_poco" in vector_radii:
            poco.raio = vector_radii["r_poco"]

        if laje and laje.raio is None and "r_poco" in vector_radii:
            laje.raio = vector_radii["r_poco"]

        if parede and parede.raio is None and "r_ext_parede" in vector_radii:
            parede.raio = vector_radii["r_ext_parede"]

        if parede_int and parede_int.raio is None and "r_poco" in vector_radii:
            parede_int.raio = vector_radii["r_poco"]

        if parede_ext and parede_ext.raio is None and "r_ext_parede" in vector_radii:
            parede_ext.raio = vector_radii["r_ext_parede"]

    def _parse_text(self, text: str, nome_arquivo: str) -> GeometriaExtraida:
        texto_planta, texto_corte = split_plan_section(text)

        documento = extract_document_id(text) or nome_arquivo
        tanques = extract_tank_tags(text)
        total_tanques = len(tanques) if tanques else 1

        radii = extract_all_radii(texto_planta) or extract_all_radii(text)
        classificados = classify_radii(radii)

        r_base = classificados.get("r_base")
        r_poco = classificados.get("r_poco")
        r_ext_parede = classificados.get("r_ext_parede")

        if r_poco is None:
            r_poco = self._extrair_raio_poco_por_diametro(text)

        h_base = self._extrair_altura_base(texto_corte, text)
        h_poco = self._extrair_altura_poco(texto_corte, text, h_base)
        h_parede = self._extrair_altura_parede(texto_corte, text)

        pile_spec = parse_pile_spec(text)
        pile_length = self._extrair_comprimento_estaca(text)

        qtd_estacas: Optional[int] = None
        tipo_estaca: str = "HP310x110"
        if pile_spec:
            qtd_estacas, tipo_estaca = pile_spec

        r_ext_parede_calc = (
            r_ext_parede
            if r_ext_parede is not None
            else (r_poco + self.config.esp_parede_poco if r_poco is not None else None)
        )

        itens: list[ElementoFundacao] = [
            ElementoFundacao(item="BASE", raio=r_base, altura=h_base),
            ElementoFundacao(item="POÇO", raio=r_poco, altura=h_poco),
            ElementoFundacao(item="PAREDE DO POÇO", raio=r_ext_parede_calc, altura=h_parede),
            ElementoFundacao(item="LAJE DO POÇO", raio=r_poco, altura=self.config.esp_laje_poco),
            ElementoFundacao(item="PAREDE INTERNA DO POÇO", raio=r_poco, altura=h_parede),
            ElementoFundacao(item="PAREDE EXTERNA DO POÇO", raio=r_ext_parede_calc, altura=h_parede),
            ElementoFundacao(item=f"ESTACAS {tipo_estaca}", quantidade=qtd_estacas, comprimento=pile_length),
        ]

        return GeometriaExtraida(
            documento=documento,
            tanques=tanques,
            total_tanques=total_tanques,
            itens=itens,
            fonte_extracao="pdfplumber+ocr+vetor",
        )

    def _extrair_raio_poco_por_diametro(self, text: str) -> Optional[float]:
        m = re.search(r'[ØøDIAM\.]+\s*(\d{2,3}(?:[,\.]\d{1,2})?)', text, re.IGNORECASE)
        if m:
            try:
                diam_cm = float(m.group(1).replace(",", "."))
                if 80 <= diam_cm <= 300:
                    return round(diam_cm / 200.0, 4)
            except ValueError:
                pass

        for trecho in self._trechos_proximos(text, ["POÇO", "POCO", "SUMP"], janela=80):
            for m2 in re.finditer(r'\b(\d{3}(?:[,\.]\d{1,2})?)\b', trecho):
                try:
                    val = float(m2.group(1).replace(",", "."))
                    if 100 <= val <= 250:
                        return round(val / 200.0, 4)
                except ValueError:
                    pass
        return None

    def _extrair_altura_base(self, texto_corte: str, texto_completo: str) -> Optional[float]:
        elevacoes = sorted(set(self._todas_elevacoes(texto_completo)))
        for i in range(len(elevacoes) - 1, -1, -1):
            for j in range(i - 1, -1, -1):
                h = elevacoes[i] - elevacoes[j]
                if 0.30 <= h <= 0.90:
                    return round(h, 3)

        for trecho in self._trechos_proximos(
            texto_completo, ["ESPESSURA", "ESP.", "LAJE DE FUNDO"], janela=80
        ):
            valor = self._maior_cota_cm(trecho, minimo=0.3, maximo=0.9)
            if valor:
                return valor
        return None

    def _extrair_altura_poco(
        self, texto_corte: str, texto_completo: str, h_base: Optional[float] = None
    ) -> Optional[float]:
        for trecho in self._trechos_proximos(texto_completo, ["POÇO", "POCO", "SUMP"], janela=100):
            valor = self._maior_cota_cm(trecho, minimo=0.3, maximo=1.5)
            if valor:
                return valor
        if h_base is not None:
            return h_base
        return None

    def _extrair_altura_parede(self, texto_corte: str, texto_completo: str) -> Optional[float]:
        for trecho in self._trechos_proximos(texto_completo, ["PAREDE", "WALL"], janela=100):
            valor = self._maior_cota_cm(trecho, minimo=0.1, maximo=1.0)
            if valor:
                return valor
        return self.config.esp_parede_poco

    def _extrair_comprimento_estaca(self, texto: str) -> Optional[float]:
        for trecho in self._trechos_proximos(
            texto, ["COMPRIMENTO ESTIMADO", "ESTIMADO", "ESTIM"], janela=120
        ):
            valor = parse_pile_length(trecho)
            if valor and 5 <= valor <= 60:
                return valor
        valor = parse_pile_length(texto)
        if valor and 5 <= valor <= 60:
            return valor
        return None

    def _todas_elevacoes(self, texto: str) -> list[float]:
        from .geometry_parser import RE_ELEVACAO
        matches = RE_ELEVACAO.findall(texto)
        result: list[float] = []
        for m in matches:
            try:
                result.append(float(m.replace(",", ".")))
            except ValueError:
                pass
        return result

    def _trechos_proximos(
        self, texto: str, palavras_chave: list[str], janela: int = 100
    ) -> list[str]:
        trechos: list[str] = []
        for palavra in palavras_chave:
            for m in re.finditer(re.escape(palavra), texto, re.IGNORECASE):
                start = max(0, m.start() - janela)
                end = min(len(texto), m.end() + janela)
                trechos.append(texto[start:end])
        return trechos

    def _maior_cota_cm(
        self, trecho: str, minimo: float = 0.0, maximo: float = 10.0
    ) -> Optional[float]:
        from .geometry_parser import RE_COTA_CM
        valores: list[float] = []
        for m in RE_COTA_CM.finditer(trecho):
            try:
                v = float(m.group(1).replace(",", ".")) / 100.0
                if minimo <= v <= maximo:
                    valores.append(v)
            except ValueError:
                pass
        return max(valores) if valores else None

    @staticmethod
    def _encontrar_item(geo: GeometriaExtraida, nome: str) -> Optional[ElementoFundacao]:
        nome_lower = nome.lower()
        for item in geo.itens:
            item_lower = item.item.lower()
            if item_lower == nome_lower or item_lower.startswith(nome_lower):
                return item
        return None
