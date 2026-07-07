"""
Agente Avaliador de respostas do fornecedor (operacao R2).

Responde a pergunta: "a resposta do fornecedor resolve a pendência que foi apontada?"
Distinto do Analisador — não avalia a proposta original, apenas julga se a RESPOSTA
do fornecedor resolve a pendência específica registrada na rodada anterior. Quando
disponível, lê o histórico de acordos do item (rodadas anteriores no BD central)
para detectar respostas que apenas repetem rodadas passadas.
"""
import logging

from app.services.llm_client import call_llm, extract_json
from app.services.prompts.avaliacao import (
    AVALIACAO_HISTORICO_TEMPLATE,
    AVALIACAO_SYSTEM_PROMPT,
    AVALIACAO_USER_TEMPLATE,
)

logger = logging.getLogger(__name__)


class EvaluationResult:
    def __init__(self, veredito: str, justificativa: str, acao_requerida: str | None):
        self.veredito = veredito
        self.justificativa = justificativa
        self.acao_requerida = acao_requerida


_VALID_VEREDITOS = {"ATENDE", "PARCIAL", "NAO_ATENDE"}


def avaliar_resposta(
    requisito: str,
    pendencia: str,
    resposta: str,
    historico_acordos: str | None = None,
) -> EvaluationResult:
    """
    Chama o LLM para avaliar se a resposta do fornecedor resolve a pendência.
    `historico_acordos` (R2): rodadas anteriores do item serializadas em texto.
    Roda de forma síncrona — use asyncio.to_thread em contextos async.
    Nunca levanta exceção: em caso de falha, retorna veredito PARCIAL com a mensagem de erro.
    """
    historico_section = (
        AVALIACAO_HISTORICO_TEMPLATE.format(historico=historico_acordos.strip())
        if historico_acordos and historico_acordos.strip()
        else ""
    )
    user_content = AVALIACAO_USER_TEMPLATE.format(
        requisito=requisito.strip(),
        pendencia=pendencia.strip(),
        historico_section=historico_section,
        resposta=resposta.strip(),
    )

    logger.info(
        "Evaluator LLM call: req_chars=%d, pend_chars=%d, resp_chars=%d, com_historico=%s",
        len(requisito), len(pendencia), len(resposta), bool(historico_acordos),
    )

    try:
        raw = call_llm(AVALIACAO_SYSTEM_PROMPT, user_content)
        data = extract_json(raw)
    except Exception as exc:
        logger.exception("Evaluator LLM call failed")
        return EvaluationResult(
            veredito="PARCIAL",
            justificativa=f"Erro interno ao chamar avaliador: {exc}",
            acao_requerida="Reprocessar avaliacao manualmente.",
        )

    veredito = str(data.get("veredito", "")).upper().strip()
    if veredito not in _VALID_VEREDITOS:
        logger.warning("Evaluator returned unexpected veredito=%r, defaulting to PARCIAL", veredito)
        veredito = "PARCIAL"

    justificativa = str(data.get("justificativa", "")).strip() or "Justificativa nao fornecida."
    acao_requerida = data.get("acao_requerida") or None
    if isinstance(acao_requerida, str):
        acao_requerida = acao_requerida.strip() or None

    return EvaluationResult(
        veredito=veredito,
        justificativa=justificativa,
        acao_requerida=acao_requerida,
    )
