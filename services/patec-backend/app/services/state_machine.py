"""
Máquina de estados para o ciclo iterativo de avaliação de pareceres técnicos.

Estados do item:
  ABERTO → estado inicial após criação, antes de qualquer análise.
  PENDENTE_FORNECEDOR → item não aprovado na rodada; aguarda resposta do fornecedor.
  EM_REAVALIACAO → fornecedor respondeu; engenharia está avaliando a resposta.
  RESOLVIDO → item aprovado ou aceito definitivamente.
  ESCALONADO → item escalado manualmente; sai do loop de pendências.

Eventos disponíveis:
  classificar_aprovado       ABERTO → RESOLVIDO
  classificar_nao_aprovado   ABERTO → PENDENTE_FORNECEDOR
  fornecedor_respondeu       PENDENTE_FORNECEDOR → EM_REAVALIACAO
  aceitar                    EM_REAVALIACAO → RESOLVIDO
  rejeitar                   EM_REAVALIACAO → PENDENTE_FORNECEDOR
  escalar                    PENDENTE_FORNECEDOR → ESCALONADO
"""

ABERTO = "ABERTO"
PENDENTE_FORNECEDOR = "PENDENTE_FORNECEDOR"
EM_REAVALIACAO = "EM_REAVALIACAO"
RESOLVIDO = "RESOLVIDO"
ESCALONADO = "ESCALONADO"

# Mapeamento (estado_atual, evento) → estado_seguinte
_TRANSITIONS: dict[tuple[str, str], str] = {
    (ABERTO, "classificar_aprovado"): RESOLVIDO,
    (ABERTO, "classificar_nao_aprovado"): PENDENTE_FORNECEDOR,
    (PENDENTE_FORNECEDOR, "fornecedor_respondeu"): EM_REAVALIACAO,
    (PENDENTE_FORNECEDOR, "escalar"): ESCALONADO,
    (EM_REAVALIACAO, "aceitar"): RESOLVIDO,
    (EM_REAVALIACAO, "rejeitar"): PENDENTE_FORNECEDOR,
}

# Estados terminais — nenhum evento válido a partir deles
_TERMINAL_STATES = {RESOLVIDO, ESCALONADO}

# Estados válidos do parecer (status_global)
EM_ANALISE = "EM_ANALISE"
AGUARDANDO_FORNECEDOR = "AGUARDANDO_FORNECEDOR"
CONCLUIDO = "CONCLUIDO"


class TransicaoInvalidaError(ValueError):
    """Raised when a state transition is not allowed."""


def transicionar(estado_atual: str, evento: str) -> str:
    """
    Aplica um evento ao estado atual e devolve o novo estado.
    Levanta TransicaoInvalidaError se a transição não for permitida.
    """
    chave = (estado_atual, evento)
    if chave not in _TRANSITIONS:
        validos = [ev for (est, ev) in _TRANSITIONS if est == estado_atual]
        raise TransicaoInvalidaError(
            f"Transição inválida: estado='{estado_atual}', evento='{evento}'. "
            f"Eventos válidos neste estado: {validos or ['nenhum (estado terminal)']}"
        )
    return _TRANSITIONS[chave]


def evento_para_classificacao(classificacao_ia: str) -> str:
    """Converte classificação A/B/C/D/E no evento de estado correspondente."""
    return "classificar_aprovado" if classificacao_ia == "A" else "classificar_nao_aprovado"


def compute_status_global(estados: list[str]) -> str:
    """
    Calcula o status_global do parecer com base nos estados de seus itens.

    Regras (em ordem de precedência):
      1. Sem itens → EM_ANALISE
      2. Todos em {RESOLVIDO, ESCALONADO} → CONCLUIDO
      3. Qualquer EM_REAVALIACAO → EM_REAVALIACAO (reutiliza constante do item)
      4. Qualquer PENDENTE_FORNECEDOR → AGUARDANDO_FORNECEDOR
      5. Caso contrário → EM_ANALISE
    """
    if not estados:
        return EM_ANALISE

    estado_set = set(estados)

    if estado_set <= {RESOLVIDO, ESCALONADO}:
        return CONCLUIDO

    if EM_REAVALIACAO in estado_set:
        return EM_REAVALIACAO  # string idêntica ao estado do item

    if PENDENTE_FORNECEDOR in estado_set:
        return AGUARDANDO_FORNECEDOR

    return EM_ANALISE


def validar_estado(estado: str) -> None:
    """Levanta ValueError se o estado não for reconhecido."""
    validos = {ABERTO, PENDENTE_FORNECEDOR, EM_REAVALIACAO, RESOLVIDO, ESCALONADO}
    if estado not in validos:
        raise ValueError(f"Estado desconhecido: '{estado}'. Válidos: {sorted(validos)}")
