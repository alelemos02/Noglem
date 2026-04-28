"""Parsing de texto bruto extraído de PDFs de desenhos de fundação."""

from __future__ import annotations

import re
from typing import Optional


# ── Padrões regex ──────────────────────────────────────────────────────────

# Anotação de raio em cm: R81, R825, R1250 — 2 a 4 dígitos
RE_RAIO_CM = re.compile(r'\bR(\d{2,4})\b')

# Elevação: "EL. +3,15", "EL +0,575", "EL -0,30"
RE_ELEVACAO = re.compile(r'EL\.?\s*([+-]?\d+[,\.]\d{1,3})')

# Dimensão numérica em centímetros (ex: "57,5", "15", "45")
RE_COTA_CM = re.compile(r'\b(\d{1,3}(?:[,\.]\d{1,2})?)\b')

# Especificação de estacas: "104 ESTACAS METÁLICAS HP310x110" ou "METÁLICA" (sem S)
RE_ESTACAS = re.compile(
    r'(\d+)\s+ESTACAS\s+(?:MET[AÁ]LICAS?\s+)?(HP\d+[xX]\d+)',
    re.IGNORECASE,
)

# Comprimento de estaca com faixa: "23 a 25m" ou "25m" ou "L = 25,00m"
RE_COMPRIMENTO_FAIXA = re.compile(
    r'(?:(\d+(?:[,\.]\d+)?)\s*(?:[aA]|até)\s+)?(\d+(?:[,\.]\d+)?)\s*m\b',
    re.IGNORECASE,
)

# Código do documento: DE-5210.00-26360-120-ET4-406=D
RE_DOCUMENTO = re.compile(
    r'DE-\d{4}\.\d{2}-\d{5,6}-\d{3}-\w{3}-\d{3}=\w'
)

# Tag do tanque: TQ-26360001, TQ-01-02, TQ 01
RE_TANQUE = re.compile(r'\bTQ[-\s]?[\d\-]+')


# ── Funções de parsing ─────────────────────────────────────────────────────


def parse_r_annotation(token: str) -> Optional[float]:
    m = RE_RAIO_CM.search(token)
    if m:
        return int(m.group(1)) / 100.0
    return None


def parse_elevation(token: str) -> Optional[float]:
    m = RE_ELEVACAO.search(token)
    if m:
        return float(m.group(1).replace(",", "."))
    return None


def parse_dimension_cm(token: str) -> Optional[float]:
    m = RE_COTA_CM.search(token)
    if m:
        try:
            return float(m.group(1).replace(",", ".")) / 100.0
        except ValueError:
            return None
    return None


def parse_pile_spec(text: str) -> Optional[tuple[int, str]]:
    m = RE_ESTACAS.search(text)
    if m:
        return int(m.group(1)), m.group(2).upper()
    return None


def parse_pile_length(text: str) -> Optional[float]:
    matches = RE_COMPRIMENTO_FAIXA.findall(text)
    valores: list[float] = []
    for low, high in matches:
        if high:
            try:
                valores.append(float(high.replace(",", ".")))
            except ValueError:
                pass
        if low:
            try:
                valores.append(float(low.replace(",", ".")))
            except ValueError:
                pass
    return max(valores) if valores else None


def extract_all_radii(text: str) -> list[float]:
    matches = RE_RAIO_CM.findall(text)
    radii = sorted({int(v) / 100.0 for v in matches}, reverse=True)
    return radii


def classify_radii(radii: list[float]) -> dict[str, float]:
    result: dict[str, float] = {}
    if not radii:
        return result

    result["r_base"] = radii[0]

    if len(radii) >= 2:
        if radii[0] / radii[-1] >= 5.0:
            result["r_poco"] = radii[-1]
            if len(radii) >= 3:
                result["r_ext_parede"] = radii[1]
                result["r_int_parede"] = radii[2]
            elif len(radii) == 2:
                result["r_ext_parede"] = radii[1]

    return result


def extract_document_id(text: str) -> Optional[str]:
    m = RE_DOCUMENTO.search(text)
    return m.group(0) if m else None


def extract_tank_tags(text: str) -> list[str]:
    RE_TRIPLA = re.compile(r'\bTQ-(\d+)/(\d+)/(\d+)\b')
    RE_DUPLA  = re.compile(r'\bTQ-(\d+)/(\d+)\b')

    seen: set[str] = set()
    result: list[str] = []

    def _expandir(base: str, *sufixos: str) -> None:
        for suf in sufixos:
            prefixo = base[: len(base) - len(suf)]
            tag = f"TQ-{prefixo}{suf}"
            if tag not in seen:
                seen.add(tag)
                result.append(tag)

    for m in RE_TRIPLA.finditer(text):
        _expandir(m.group(1), m.group(1), m.group(2), m.group(3))

    for m in RE_DUPLA.finditer(text):
        _expandir(m.group(1), m.group(1), m.group(2))

    if result:
        return result

    RE_INDIVIDUAL = re.compile(r'\bTQ[-\s]?\d{5,}')
    for tag in RE_INDIVIDUAL.findall(text):
        normalized = tag.strip()
        if normalized not in seen:
            seen.add(normalized)
            result.append(normalized)

    return result


def split_plan_section(text: str) -> tuple[str, str]:
    separadores = re.compile(r'CORTE\s+[A-Z]-[A-Z]|SEÇÃO\s+[A-Z]-[A-Z]', re.IGNORECASE)
    m = separadores.search(text)
    if m:
        return text[: m.start()], text[m.start():]
    return text, text
