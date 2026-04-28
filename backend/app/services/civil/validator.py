"""Validações de coerência geométrica e numérica dos quantitativos."""

from __future__ import annotations

from .models import GeometriaExtraida, ResultadoQuantitativo


def _encontrar_item(geo: GeometriaExtraida, nome: str):
    nome_lower = nome.lower()
    for item in geo.itens:
        if item.item.lower() == nome_lower:
            return item
    return None


def validar_geometria(geo: GeometriaExtraida) -> list[str]:
    erros: list[str] = []

    poco = _encontrar_item(geo, "POÇO")
    parede = _encontrar_item(geo, "PAREDE DO POÇO")

    if poco and parede:
        r_int = poco.raio
        r_ext = parede.raio
        if r_int is not None and r_ext is not None and r_ext <= r_int:
            erros.append(
                f"R_externo_poco deve ser > R_interno_poco "
                f"(R_ext={r_ext}, R_int={r_int})"
            )

    base = _encontrar_item(geo, "BASE")
    if base and base.altura is not None and base.altura <= 0:
        erros.append(f"Altura da BASE deve ser positiva (valor={base.altura})")

    if base and base.raio is not None and base.raio <= 0:
        erros.append(f"Raio da BASE deve ser positivo (valor={base.raio})")

    return erros


def validar_calculos(
    resultado: ResultadoQuantitativo, tolerancia: float = 0.01
) -> list[str]:
    erros: list[str] = []
    geo = resultado.geometria

    poco = _encontrar_item(geo, "POÇO")
    if poco and poco.concreto_estr is not None and poco.concreto_estr >= 0:
        erros.append(
            f"POÇO deve ter concreto_estr NEGATIVO (valor={poco.concreto_estr})"
        )

    colunas = [
        "concreto_estr", "formas_in_situ", "grout", "c_magro",
        "escav_h_menor_1_2", "reat_h_menor_1_2", "bota_fora", "estacas",
    ]
    for col in colunas:
        soma_linhas = sum(getattr(item, col) or 0.0 for item in geo.itens)
        total_val = resultado.total_1_tanque.get(col, 0.0)
        if abs(soma_linhas - total_val) > tolerancia:
            erros.append(
                f"Soma das linhas ({soma_linhas:.4f}) ≠ TOTAL_1_TANQUE ({total_val:.4f}) "
                f"na coluna {col}"
            )

    n = geo.total_tanques
    for col in colunas:
        esperado = resultado.total_1_tanque.get(col, 0.0) * n
        geral_val = resultado.total_geral.get(col, 0.0)
        if abs(esperado - geral_val) > tolerancia:
            erros.append(
                f"TOTAL ({geral_val:.4f}) ≠ TOTAL_1_TANQUE × {n} ({esperado:.4f}) "
                f"na coluna {col}"
            )

    estacas_item = next(
        (i for i in geo.itens if "ESTACA" in i.item.upper()), None
    )
    if estacas_item and estacas_item.estacas is not None:
        esperado_estacas = (estacas_item.quantidade or 0) * (estacas_item.comprimento or 0.0)
        if abs(estacas_item.estacas - esperado_estacas) > tolerancia:
            erros.append(
                f"Estacas: quantidade × comprimento ({esperado_estacas:.2f}) ≠ "
                f"total ({estacas_item.estacas:.2f})"
            )

    return erros
