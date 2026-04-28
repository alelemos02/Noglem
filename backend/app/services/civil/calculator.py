"""Fórmulas de cálculo de quantitativos de fundação de tanques."""

from __future__ import annotations

import math
from typing import Optional

from .models import ConfigProjeto, ElementoFundacao, GeometriaExtraida, ResultadoQuantitativo

PI = math.pi

COLUNAS_CALCULADAS = [
    "concreto_estr",
    "formas_in_situ",
    "grout",
    "c_magro",
    "escav_h_menor_1_2",
    "reat_h_menor_1_2",
    "bota_fora",
    "estacas",
]


def calc_base(raio: float, altura: float, config: ConfigProjeto) -> dict[str, float]:
    v_concreto = PI * raio ** 2 * altura
    a_formas = 2 * PI * raio * altura
    v_magro = PI * (raio + config.folga_magro) ** 2 * config.esp_magro
    v_escav = PI * (raio + config.folga_escavacao) ** 2 * (altura + config.esp_magro)
    v_reat = 0.0
    v_bota_fora = v_escav - v_reat
    return {
        "concreto_estr": round(v_concreto, 4),
        "formas_in_situ": round(a_formas, 4),
        "c_magro": round(v_magro, 4),
        "escav_h_menor_1_2": round(v_escav, 4),
        "reat_h_menor_1_2": round(v_reat, 4),
        "bota_fora": round(v_bota_fora, 4),
    }


def calc_poco(raio: float, altura: float) -> dict[str, float]:
    v_concreto = -(PI * raio ** 2 * altura)
    return {"concreto_estr": round(v_concreto, 4)}


def calc_parede_poco(r_ext: float, r_int: float, altura: float) -> dict[str, float]:
    v_concreto = PI * (r_ext ** 2 - r_int ** 2) * altura
    a_formas = 2 * PI * r_int * altura + 2 * PI * r_ext * altura
    return {
        "concreto_estr": round(v_concreto, 4),
        "formas_in_situ": round(a_formas, 4),
    }


def calc_laje_poco(raio: float, espessura: float) -> dict[str, float]:
    v_concreto = PI * raio ** 2 * espessura
    return {"concreto_estr": round(v_concreto, 4)}


def calc_parede_interna(raio: float, altura: float) -> dict[str, float]:
    a_formas = 2 * PI * raio * altura
    return {"formas_in_situ": round(a_formas, 4)}


def calc_parede_externa(raio: float, altura: float) -> dict[str, float]:
    a_formas = 2 * PI * raio * altura
    return {"formas_in_situ": round(a_formas, 4)}


def calc_estacas(quantidade: int, comprimento_unitario: float) -> dict[str, float]:
    total = quantidade * comprimento_unitario
    return {"estacas": round(total, 2)}


def _soma_coluna(itens: list[ElementoFundacao], col: str) -> float:
    return sum(getattr(item, col) or 0.0 for item in itens)


def calc_totais(
    itens: list[ElementoFundacao], total_tanques: int
) -> tuple[dict[str, float], dict[str, float]]:
    total_1: dict[str, float] = {}
    for col in COLUNAS_CALCULADAS:
        soma = _soma_coluna(itens, col)
        total_1[col] = round(soma, 4)

    total_1["bota_fora"] = round(
        total_1["escav_h_menor_1_2"] - total_1["reat_h_menor_1_2"], 4
    )

    total_geral: dict[str, float] = {
        col: round(v * total_tanques, 4) for col, v in total_1.items()
    }
    return total_1, total_geral


def _encontrar_item(
    itens: list[ElementoFundacao], nome: str
) -> Optional[ElementoFundacao]:
    nome_lower = nome.lower()
    for item in itens:
        if item.item.lower() == nome_lower:
            return item
    return None


def calcular_todos(
    geo: GeometriaExtraida, config: ConfigProjeto
) -> ResultadoQuantitativo:
    itens = geo.itens

    base = _encontrar_item(itens, "BASE")
    poco = _encontrar_item(itens, "POÇO")
    parede_poco = _encontrar_item(itens, "PAREDE DO POÇO")
    laje_poco = _encontrar_item(itens, "LAJE DO POÇO")
    parede_interna = _encontrar_item(itens, "PAREDE INTERNA DO POÇO")
    parede_externa = _encontrar_item(itens, "PAREDE EXTERNA DO POÇO")
    estacas = next(
        (i for i in itens if "ESTACA" in i.item.upper()), None
    )

    if base and base.raio is not None and base.altura is not None:
        resultado = calc_base(base.raio, base.altura, config)
        for k, v in resultado.items():
            setattr(base, k, v)

    if poco and poco.raio is not None and poco.altura is not None:
        resultado = calc_poco(poco.raio, poco.altura)
        for k, v in resultado.items():
            setattr(poco, k, v)

    if parede_poco and poco:
        r_int = poco.raio
        r_ext = (r_int + config.esp_parede_poco) if r_int is not None else parede_poco.raio
        h = parede_poco.altura or config.esp_parede_poco
        if r_int is not None and r_ext is not None:
            resultado = calc_parede_poco(r_ext, r_int, h)
            for k, v in resultado.items():
                setattr(parede_poco, k, v)
            if parede_poco.raio is None:
                parede_poco.raio = r_ext

    if laje_poco:
        r = laje_poco.raio or (poco.raio if poco else None)
        esp = laje_poco.altura or config.esp_laje_poco
        if r is not None:
            resultado = calc_laje_poco(r, esp)
            for k, v in resultado.items():
                setattr(laje_poco, k, v)

    if parede_interna and poco and poco.raio is not None:
        h = parede_interna.altura or (parede_poco.altura if parede_poco else config.esp_parede_poco)
        resultado = calc_parede_interna(poco.raio, h)
        for k, v in resultado.items():
            setattr(parede_interna, k, v)
        if parede_interna.raio is None:
            parede_interna.raio = poco.raio

    if parede_externa and poco:
        r_ext = (poco.raio or 0.0) + config.esp_parede_poco
        if parede_poco and parede_poco.raio is not None:
            r_ext = parede_poco.raio
        h = parede_externa.altura or (parede_poco.altura if parede_poco else config.esp_parede_poco)
        resultado = calc_parede_externa(r_ext, h)
        for k, v in resultado.items():
            setattr(parede_externa, k, v)
        if parede_externa.raio is None:
            parede_externa.raio = r_ext

    if estacas and estacas.quantidade and estacas.quantidade > 0 and estacas.comprimento is not None:
        resultado = calc_estacas(estacas.quantidade, estacas.comprimento)
        for k, v in resultado.items():
            setattr(estacas, k, v)

    total_1, total_geral = calc_totais(itens, geo.total_tanques)

    return ResultadoQuantitativo(
        geometria=geo,
        total_1_tanque=total_1,
        total_geral=total_geral,
    )
