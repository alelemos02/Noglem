from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class ConfigProjeto(BaseModel):
    folga_escavacao: float = 0.10
    esp_magro: float = 0.10
    folga_magro: float = 0.05
    esp_laje_poco: float = 0.15
    esp_parede_poco: float = 0.15
    tolerancia_validacao: float = 0.01
    threshold_texto_pdf: int = 200

    @classmethod
    def from_file(cls, path: Path) -> "ConfigProjeto":
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(**data)


class ElementoFundacao(BaseModel):
    item: str
    quantidade: Optional[int] = None
    raio: Optional[float] = None
    largura: Optional[float] = None
    comprimento: Optional[float] = None
    altura: Optional[float] = None
    altura_escavacao: Optional[float] = None
    # Campos calculados (preenchidos pelo calculator)
    concreto_estr: Optional[float] = None
    formas_in_situ: Optional[float] = None
    grout: Optional[float] = None
    c_magro: Optional[float] = None
    escav_h_menor_1_2: Optional[float] = None
    reat_h_menor_1_2: Optional[float] = None
    bota_fora: Optional[float] = None
    estacas: Optional[float] = None


class GeometriaExtraida(BaseModel):
    documento: str
    tanques: list[str] = Field(default_factory=list)
    total_tanques: int = 1
    itens: list[ElementoFundacao] = Field(default_factory=list)
    erro: Optional[str] = None
    fonte_extracao: str = "pdfplumber"


class ResultadoQuantitativo(BaseModel):
    geometria: GeometriaExtraida
    total_1_tanque: dict[str, float] = Field(default_factory=dict)
    total_geral: dict[str, float] = Field(default_factory=dict)
    validacoes_ok: bool = True
    erros_validacao: list[str] = Field(default_factory=list)
