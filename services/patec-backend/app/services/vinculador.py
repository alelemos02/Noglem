"""
Vinculacao automatica das respostas do fornecedor aos itens abertos
(bloco 23 do fluxo, operacao W3).

A LLM sugere os vinculos; o resultado e provisorio ate o engenheiro confirmar.
Tipo 1 (proposta totalmente revisada) nao usa LLM: cada item aberto recebe um
vinculo deterministico apontando para a proposta inteira.
"""

import json
import logging

from app.services.llm_client import call_llm, extract_json
from app.services.prompts.vinculacao import (
    VINCULACAO_SYSTEM_PROMPT,
    VINCULACAO_USER_TEMPLATE,
)

logger = logging.getLogger(__name__)

_TIPO_LABELS = {
    "PROPOSTA_REVISADA": "Tipo 1 — proposta totalmente revisada",
    "RESPOSTA_ITENS": "Tipo 2 — respostas aos itens, proposta antiga mantida",
    "RESPOSTA_ITENS_PROPOSTA_POSTERIOR": "Tipo 3 — respostas aos itens, proposta revisada vira depois",
    "EMAIL_AVULSO": "Tipo 4 — email com duvidas ou respostas avulsas",
}

_VALID_CONFIANCAS = {"ALTA", "MEDIA", "BAIXA"}


def vincular_respostas_llm(
    texto_resposta: str,
    itens_abertos: list[dict],
    tipo: str,
) -> dict:
    """
    Chama a LLM para mapear trechos da resposta aos itens abertos.

    `itens_abertos`: [{numero, descricao_requisito, valor_requerido, pendencia}]
    Retorna dict normalizado:
      {"vinculos": [{item_numero, trecho, confianca}],
       "trechos_sem_item": [...], "itens_sem_resposta": [...]}

    Sincrono — use asyncio.to_thread ou Celery em contextos async.
    """
    numeros_validos = {item["numero"] for item in itens_abertos}

    user_content = VINCULACAO_USER_TEMPLATE.format(
        tipo_label=_TIPO_LABELS.get(tipo, tipo),
        texto_resposta=texto_resposta.strip(),
        itens_json=json.dumps(itens_abertos, ensure_ascii=False, indent=2),
    )

    logger.info(
        "Vinculacao LLM: tipo=%s, resposta_chars=%d, itens_abertos=%d",
        tipo, len(texto_resposta), len(itens_abertos),
    )

    raw = call_llm(VINCULACAO_SYSTEM_PROMPT, user_content)
    data = extract_json(raw)

    vinculos_norm: list[dict] = []
    vistos: set[int] = set()
    for v in data.get("vinculos", []):
        numero = v.get("item_numero")
        if not isinstance(numero, int) or numero not in numeros_validos:
            logger.warning("Vinculo descartado: item_numero invalido %r", numero)
            continue
        if numero in vistos:
            logger.warning("Vinculo duplicado para item %d descartado", numero)
            continue
        vistos.add(numero)
        confianca = str(v.get("confianca", "")).upper()
        vinculos_norm.append({
            "item_numero": numero,
            "trecho": str(v.get("trecho", "")).strip()[:2000],
            "confianca": confianca if confianca in _VALID_CONFIANCAS else "BAIXA",
        })

    itens_sem_resposta = sorted(
        {n for n in numeros_validos if n not in vistos}
    )

    return {
        "vinculos": vinculos_norm,
        "trechos_sem_item": [
            str(t).strip()[:2000] for t in data.get("trechos_sem_item", []) if str(t).strip()
        ],
        "itens_sem_resposta": itens_sem_resposta,
    }


def vincular_proposta_revisada(itens_abertos: list[dict]) -> dict:
    """
    Tipo 1: a proposta inteira responde a todos os itens abertos — um vinculo
    deterministico por item, sem chamada LLM (a avaliacao item a item acontece
    na etapa seguinte, contra o texto completo da proposta).
    """
    return {
        "vinculos": [
            {"item_numero": item["numero"], "trecho": None, "confianca": "ALTA"}
            for item in itens_abertos
        ],
        "trechos_sem_item": [],
        "itens_sem_resposta": [],
    }
