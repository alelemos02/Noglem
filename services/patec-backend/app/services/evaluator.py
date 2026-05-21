"""
Agente Avaliador de respostas do fornecedor.

Responde a pergunta: "a resposta do fornecedor resolve a pendência que foi apontada?"
Distinto do Analisador — não avalia a proposta original, apenas julga se a RESPOSTA
do fornecedor resolve a pendência específica registrada na rodada anterior.
"""
import json
import logging

from app.services.analyzer import _call_gemini, _extract_json

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """Voce e um avaliador tecnico cetico de respostas de fornecedores em projetos EPC.
Sua tarefa NAO e analisar a proposta original, e sim julgar se a RESPOSTA do fornecedor
resolve a pendencia especifica que foi apontada.

CRITERIOS:
- ATENDE: a resposta fornece o dado, documento ou compromisso concreto que foi pedido,
  com referencia verificavel (documento, pagina, item, valor numerico).
- PARCIAL: responde apenas parte; ou promete sem comprovar; ou cita documento que nao
  foi anexado; ou atende com ressalva relevante.
- NAO_ATENDE: evasiva; repete a proposta original sem complemento; ignora a pendencia;
  ou responde algo que nao e o que foi pedido.

REGRA ANTI-EVASIVA: respostas como "conforme pratica usual", "oportunamente",
"a confirmar", "padrao do fabricante", "sera fornecido" SEM dado concreto associado
sao, no maximo, PARCIAL. Nunca classifique uma promessa nao comprovada como ATENDE.

Seja objetivo e factual. Nao de beneficio da duvida ao fornecedor. Cite exatamente qual
parte da resposta sustenta seu veredito.

Retorne EXCLUSIVAMENTE JSON valido, sem texto adicional, sem markdown:
{
  "veredito": "ATENDE" | "PARCIAL" | "NAO_ATENDE",
  "justificativa": "<string, citando trecho da resposta>",
  "acao_requerida": "<string descrevendo o que ainda falta, ou null se ATENDE>"
}"""

_USER_TEMPLATE = """## REQUISITO ORIGINAL DA ENGENHARIA
{requisito}

## PENDENCIA QUE FOI APONTADA (acao requerida da rodada anterior)
{pendencia}

## RESPOSTA DO FORNECEDOR (a ser avaliada)
{resposta}

Avalie se a resposta do fornecedor resolve a pendencia."""


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
) -> EvaluationResult:
    """
    Chama o LLM para avaliar se a resposta do fornecedor resolve a pendência.
    Roda de forma síncrona — use asyncio.to_thread em contextos async.
    Nunca levanta exceção: em caso de falha, retorna veredito PARCIAL com a mensagem de erro.
    """
    user_content = _USER_TEMPLATE.format(
        requisito=requisito.strip(),
        pendencia=pendencia.strip(),
        resposta=resposta.strip(),
    )

    logger.info(
        "Evaluator LLM call: req_chars=%d, pend_chars=%d, resp_chars=%d",
        len(requisito), len(pendencia), len(resposta),
    )

    try:
        raw = _call_gemini(_SYSTEM_PROMPT, user_content)
        data = _extract_json(raw)
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
