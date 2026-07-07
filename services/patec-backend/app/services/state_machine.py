"""
Máquinas de estado do caso técnico — nível item e nível caso.

## Itens (itens_parecer.estado)

  ABERTO → estado inicial após criação/reabertura, antes da classificação.
  PENDENTE_FORNECEDOR → item não aprovado; aguarda resposta do fornecedor.
  EM_REAVALIACAO → fornecedor respondeu; engenharia decide.
  ACEITO → item conforme (terminal, reabrível só por revisão de spec).
  REPROVADO → item crítico reprovou o caso inteiro (terminal).
  DESATIVADO → requisito removido por revisão de spec (terminal; histórico preservado).

Eventos:
  classificar_aprovado       ABERTO → ACEITO                 (análise W2, status A)
  classificar_nao_aprovado   ABERTO → PENDENTE_FORNECEDOR
  fornecedor_respondeu       PENDENTE_FORNECEDOR → EM_REAVALIACAO   (vinculação W3)
  decidir_aceitar            EM_REAVALIACAO → ACEITO         (decisão humana W4)
  decidir_esclarecer         EM_REAVALIACAO → PENDENTE_FORNECEDOR
  decidir_rejeitar           EM_REAVALIACAO → PENDENTE_FORNECEDOR
  decidir_reprovar_caso      EM_REAVALIACAO → REPROVADO      (fecha o caso, desfecho REPROVADO)
  reabrir_revisao_spec       qualquer não-DESATIVADO → ABERTO       (revisão de spec W7)
  desativar                  qualquer → DESATIVADO           (requisito removido, W7)

Esclarecer e Rejeitar produzem o mesmo estado; a semântica fica registrada na
decisao_humana da rodada de avaliação.

## Caso (pareceres.fase_caso)

  SETUP → REQUISITOS → ANALISE → CICLO_FORNECEDOR → VERIFICACAO_FINAL → FECHADO

  O avanço CICLO_FORNECEDOR → VERIFICACAO_FINAL é AUTOMÁTICO quando todos os
  itens ativos estão ACEITOS (sem gate manual). REPROVAR_CASO leva direto a
  FECHADO. A revisão de spec (W7) pode regredir o caso para CICLO_FORNECEDOR.
"""

# ─────────────────────────────────────────────────────────────────── itens ──

ABERTO = "ABERTO"
PENDENTE_FORNECEDOR = "PENDENTE_FORNECEDOR"
EM_REAVALIACAO = "EM_REAVALIACAO"
ACEITO = "ACEITO"
REPROVADO = "REPROVADO"
DESATIVADO = "DESATIVADO"

ESTADOS_ITEM = {ABERTO, PENDENTE_FORNECEDOR, EM_REAVALIACAO, ACEITO, REPROVADO, DESATIVADO}

# Estados terminais — nenhum evento comum é válido a partir deles
# (reabrir_revisao_spec e desativar são exceções tratadas adiante).
ESTADOS_TERMINAIS_ITEM = {ACEITO, REPROVADO, DESATIVADO}

# Mapeamento (estado_atual, evento) → estado_seguinte
_TRANSITIONS: dict[tuple[str, str], str] = {
    (ABERTO, "classificar_aprovado"): ACEITO,
    (ABERTO, "classificar_nao_aprovado"): PENDENTE_FORNECEDOR,
    (PENDENTE_FORNECEDOR, "fornecedor_respondeu"): EM_REAVALIACAO,
    (EM_REAVALIACAO, "decidir_aceitar"): ACEITO,
    (EM_REAVALIACAO, "decidir_esclarecer"): PENDENTE_FORNECEDOR,
    (EM_REAVALIACAO, "decidir_rejeitar"): PENDENTE_FORNECEDOR,
    (EM_REAVALIACAO, "decidir_reprovar_caso"): REPROVADO,
    # Desfazer a decisão W4 (engenheiro errou o clique): volta para a fila de
    # decisão. Vale para ACEITAR (ACEITO) e ESCLARECER/REJEITAR (PENDENTE);
    # REPROVAR_CASO fecha o caso e NÃO é revertido por aqui.
    (ACEITO, "desfazer_decisao"): EM_REAVALIACAO,
    (PENDENTE_FORNECEDOR, "desfazer_decisao"): EM_REAVALIACAO,
}

# Eventos especiais da revisão de especificação (W7): valem a partir de
# qualquer estado exceto DESATIVADO (item removido não volta).
_EVENTO_REABRIR = "reabrir_revisao_spec"
_EVENTO_DESATIVAR = "desativar"

# Decisão humana (W4) → evento da máquina de estados
DECISAO_PARA_EVENTO = {
    "ACEITAR": "decidir_aceitar",
    "ESCLARECER": "decidir_esclarecer",
    "REJEITAR": "decidir_rejeitar",
    "REPROVAR_CASO": "decidir_reprovar_caso",
}

DECISOES_HUMANAS = set(DECISAO_PARA_EVENTO)


class TransicaoInvalidaError(ValueError):
    """Raised when a state transition is not allowed."""


def transicionar(estado_atual: str, evento: str) -> str:
    """
    Aplica um evento ao estado atual e devolve o novo estado.
    Levanta TransicaoInvalidaError se a transição não for permitida.
    """
    if evento == _EVENTO_DESATIVAR:
        return DESATIVADO

    if evento == _EVENTO_REABRIR:
        if estado_atual == DESATIVADO:
            raise TransicaoInvalidaError(
                "Item desativado não pode ser reaberto por revisão de especificação."
            )
        return ABERTO

    chave = (estado_atual, evento)
    if chave not in _TRANSITIONS:
        validos = [ev for (est, ev) in _TRANSITIONS if est == estado_atual]
        validos += [_EVENTO_REABRIR] if estado_atual != DESATIVADO else []
        raise TransicaoInvalidaError(
            f"Transição inválida: estado='{estado_atual}', evento='{evento}'. "
            f"Eventos válidos neste estado: {validos or ['nenhum (estado terminal)']}"
        )
    return _TRANSITIONS[chave]


def evento_para_classificacao(classificacao_ia: str) -> str:
    """Converte classificação A/B/C/D/E no evento de estado correspondente."""
    return "classificar_aprovado" if classificacao_ia == "A" else "classificar_nao_aprovado"


def evento_para_decisao(decisao: str) -> str:
    """Converte a decisão humana (W4) no evento da máquina de estados."""
    if decisao not in DECISAO_PARA_EVENTO:
        raise ValueError(
            f"Decisão desconhecida: '{decisao}'. Válidas: {sorted(DECISAO_PARA_EVENTO)}"
        )
    return DECISAO_PARA_EVENTO[decisao]


def validar_estado(estado: str) -> None:
    """Levanta ValueError se o estado não for reconhecido."""
    if estado not in ESTADOS_ITEM:
        raise ValueError(f"Estado desconhecido: '{estado}'. Válidos: {sorted(ESTADOS_ITEM)}")


# ──────────────────────────────────────────────────────────────────── caso ──

SETUP = "SETUP"
REQUISITOS = "REQUISITOS"
ANALISE = "ANALISE"
CICLO_FORNECEDOR = "CICLO_FORNECEDOR"
VERIFICACAO_FINAL = "VERIFICACAO_FINAL"
FECHADO = "FECHADO"

FASES_CASO = [SETUP, REQUISITOS, ANALISE, CICLO_FORNECEDOR, VERIFICACAO_FINAL, FECHADO]

DESFECHOS = {"APROVADO", "COM_PENDENCIA", "REPROVADO"}

# Transições explícitas de fase (a regressão por revisão de spec é tratada
# em transicionar_fase; o avanço automático em compute_avanco_automatico).
_FASE_TRANSITIONS: dict[tuple[str, str], str] = {
    (SETUP, "extrair_requisitos"): REQUISITOS,
    (SETUP, "aprovar_requisitos"): ANALISE,        # W1 direto do setup
    (REQUISITOS, "aprovar_requisitos"): ANALISE,   # W1
    (ANALISE, "aprovar_requisitos"): ANALISE,      # reaprovação pré-análise
    (ANALISE, "iniciar_ciclo"): CICLO_FORNECEDOR,  # W2: parecer gerado/enviado
    (CICLO_FORNECEDOR, "todos_itens_aceitos"): VERIFICACAO_FINAL,  # automático
    (CICLO_FORNECEDOR, "reprovar_caso"): FECHADO,
    (VERIFICACAO_FINAL, "fechar"): FECHADO,        # W6
    (CICLO_FORNECEDOR, "fechar"): FECHADO,         # W6: encerrar caso travado
    (ANALISE, "revisao_spec"): CICLO_FORNECEDOR,   # W7 cenário B/C
    (CICLO_FORNECEDOR, "revisao_spec"): CICLO_FORNECEDOR,
    (VERIFICACAO_FINAL, "revisao_spec"): CICLO_FORNECEDOR,
}


class FaseInvalidaError(ValueError):
    """Raised when a case-phase transition is not allowed."""


def transicionar_fase(fase_atual: str, evento: str) -> str:
    """
    Aplica um evento de caso à fase atual e devolve a nova fase.
    Levanta FaseInvalidaError se a transição não for permitida.
    """
    chave = (fase_atual, evento)
    if chave not in _FASE_TRANSITIONS:
        validos = [ev for (f, ev) in _FASE_TRANSITIONS if f == fase_atual]
        raise FaseInvalidaError(
            f"Transição de fase inválida: fase='{fase_atual}', evento='{evento}'. "
            f"Eventos válidos nesta fase: {validos or ['nenhum (caso fechado)']}"
        )
    return _FASE_TRANSITIONS[chave]


def itens_ativos(estados: list[str]) -> list[str]:
    """Filtra estados de itens desativados (fora de análises e contagens)."""
    return [e for e in estados if e != DESATIVADO]


def todos_aceitos(estados: list[str]) -> bool:
    """True quando todos os itens ativos estão ACEITOS (gatilho do avanço automático)."""
    ativos = itens_ativos(estados)
    return bool(ativos) and all(e == ACEITO for e in ativos)


def compute_avanco_automatico(fase_atual: str, estados: list[str]) -> str | None:
    """
    Bloco 28→29 do fluxo: quando TODOS os itens ativos estão aceitos, o caso
    avança sozinho de CICLO_FORNECEDOR para VERIFICACAO_FINAL — sem gate manual.
    Devolve a nova fase, ou None se não há avanço.
    """
    if fase_atual == CICLO_FORNECEDOR and todos_aceitos(estados):
        return VERIFICACAO_FINAL
    return None


def compute_resumo_ciclo(estados: list[str]) -> dict:
    """
    Resumo derivado do ciclo (substitui o antigo status_global persistido).
    """
    ativos = itens_ativos(estados)
    return {
        "total_itens": len(ativos),
        "abertos": sum(1 for e in ativos if e == ABERTO),
        "aguardando_fornecedor": sum(1 for e in ativos if e == PENDENTE_FORNECEDOR),
        "em_reavaliacao": sum(1 for e in ativos if e == EM_REAVALIACAO),
        "aceitos": sum(1 for e in ativos if e == ACEITO),
        "reprovados": sum(1 for e in ativos if e == REPROVADO),
        "desativados": len(estados) - len(ativos),
        "todos_aceitos": todos_aceitos(estados),
    }
