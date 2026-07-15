"""
Reavaliacao cirurgica de itens do parecer (ajuste #13).

Quando a engenharia corrige a descricao/valor requerido de itens JA analisados
(via chat, acao atualizar_itens) — inclusive no meio do ciclo com o fornecedor —
os itens afetados sao reclassificados contra a proposta ORIGINAL, sem rodar o R1
completo (que e bloqueado fora da fase ANALISE, apagaria o vinculo com as
rodadas e leria os requisitos antigos, desfazendo a correcao). Os estados por
item seguem a maquina legal: reabrir_revisao_spec -> ABERTO -> classificar_*.
"""

import asyncio
import json
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.documento import Documento
from app.models.item_parecer import ItemParecer
from app.models.parecer import Parecer
from app.models.usuario import Usuario
from app.services.audit import registrar_auditoria
from app.services.doc_selection import eng_docs_correntes
from app.services.llm_client import call_llm, extract_json
from app.services.prompts.analise import (
    REAVALIACAO_SYSTEM_PROMPT,
    REAVALIACAO_USER_TEMPLATE,
)
from app.services.prompts.seguranca import envelopar
from app.services.state_machine import (
    ANALISE,
    CICLO_FORNECEDOR,
    DESATIVADO,
    compute_avanco_automatico,
    evento_para_classificacao,
    transicionar,
)

logger = logging.getLogger(__name__)

REAVALIA_MAX_ITENS = 15
_FORN_SLICE = 60_000
_ENG_SLICE = 30_000
_ANEXO_SLICE = 30_000
_STATUS_VALIDOS = {"A", "B", "C", "D", "E"}
_FASES_REAVALIACAO = {ANALISE, CICLO_FORNECEDOR}


def _calcular_atualizacoes(
    estados_atuais: dict[int, str], resposta: dict
) -> list[dict]:
    """Cruza a resposta da LLM com os itens pedidos e devolve as atualizacoes
    aplicaveis. Funcao pura (testavel): `estados_atuais` mapeia numero -> estado
    atual do item. Ignora numeros nao pedidos, duplicados e status invalidos;
    `acao_requerida` de item "A" e sempre None; o estado novo segue a maquina
    (reabrir_revisao_spec -> ABERTO -> classificar_(nao_)aprovado)."""
    atualizacoes: list[dict] = []
    vistos: set[int] = set()
    for bruto in resposta.get("itens") or []:
        if not isinstance(bruto, dict):
            continue
        numero = bruto.get("numero")
        if not isinstance(numero, int) or isinstance(numero, bool):
            continue
        if numero not in estados_atuais or numero in vistos:
            continue
        status = bruto.get("status")
        if status not in _STATUS_VALIDOS:
            continue
        vistos.add(numero)
        estado_novo = transicionar(
            transicionar(estados_atuais[numero], "reabrir_revisao_spec"),
            evento_para_classificacao(status),
        )
        justificativa = str(bruto.get("justificativa_tecnica") or "").strip()
        acao = bruto.get("acao_requerida")
        acao = str(acao).strip() if acao is not None else ""
        valor_forn = bruto.get("valor_fornecedor")
        valor_forn = str(valor_forn).strip() if valor_forn is not None else ""
        atualizacoes.append(
            {
                "numero": numero,
                "status": status,
                "estado": estado_novo,
                "justificativa_tecnica": justificativa or None,
                "acao_requerida": None if status == "A" else (acao or None),
                "valor_fornecedor": valor_forn or None,
            }
        )
    return atualizacoes


async def _carregar_textos(parecer_id, db: AsyncSession) -> tuple[str, str, str]:
    """(texto_engenharia, texto_fornecedor, texto_anexos) com slices — mesmo
    recorte de documentos da analise R1 (tasks.py), em versao async."""
    docs_result = await db.execute(
        select(Documento).where(Documento.parecer_id == parecer_id)
    )
    docs = list(docs_result.scalars().all())

    def _junta(selecao: list[Documento], corte: int) -> str:
        return "\n\n---\n\n".join(
            f"### {d.nome_arquivo}\n\n{d.texto_extraido or ''}" for d in selecao
        )[:corte]

    forn_docs = [d for d in docs if d.tipo == "fornecedor"]
    if not forn_docs:
        raise ValueError(
            "Nenhuma proposta do fornecedor no caso — nada contra o que reavaliar."
        )
    return (
        _junta(eng_docs_correntes(docs), _ENG_SLICE),
        _junta(forn_docs, _FORN_SLICE),
        _junta([d for d in docs if d.tipo == "anexo_engenharia"], _ANEXO_SLICE),
    )


async def reavaliar_itens(
    parecer_id,
    numeros: list[int],
    db: AsyncSession,
    usuario: Usuario | None,
) -> dict:
    """Reclassifica os itens `numeros` contra a proposta do fornecedor.

    Retorna {"total", "mudancas": [{numero, de, para}], "fase_caso"}. Levanta
    ValueError com mensagem exibivel quando a fase nao permite, nenhum item
    casa ou a LLM nao devolve resultado utilizavel — o caller transforma em
    action_error visivel no chat.
    """
    parecer_result = await db.execute(
        select(Parecer).where(Parecer.id == parecer_id)
    )
    parecer = parecer_result.scalar_one_or_none()
    if not parecer:
        raise ValueError("Parecer nao encontrado.")
    if parecer.fase_caso not in _FASES_REAVALIACAO:
        raise ValueError(
            f"Reavaliacao de itens indisponivel na fase {parecer.fase_caso}."
        )

    numeros_unicos = sorted(
        {n for n in numeros if isinstance(n, int) and not isinstance(n, bool)}
    )
    if not numeros_unicos:
        raise ValueError("Nenhum numero de item valido para reavaliar.")
    if len(numeros_unicos) > REAVALIA_MAX_ITENS:
        raise ValueError(
            f"Reavaliacao limitada a {REAVALIA_MAX_ITENS} itens por vez — "
            "peca em lotes menores."
        )

    itens_result = await db.execute(
        select(ItemParecer).where(
            ItemParecer.parecer_id == parecer_id,
            ItemParecer.numero.in_(numeros_unicos),
            ItemParecer.estado != DESATIVADO,
        )
    )
    itens = {i.numero: i for i in itens_result.scalars().all()}
    if not itens:
        raise ValueError("Nenhum item correspondente para reavaliar.")

    texto_eng, texto_forn, texto_anexos = await _carregar_textos(parecer_id, db)

    itens_json = json.dumps(
        [
            {
                "numero": i.numero,
                "descricao_requisito": i.descricao_requisito,
                "valor_requerido": i.valor_requerido,
                "norma_referencia": i.norma_referencia,
                "prioridade": i.prioridade,
                "status_atual": i.status,
            }
            for i in sorted(itens.values(), key=lambda x: x.numero)
        ],
        ensure_ascii=False,
    )
    secao_anexos = (
        "\n## DOCUMENTOS COMPLEMENTARES DA ENGENHARIA\n"
        + envelopar("DOC_ANEXO_ENGENHARIA", texto_anexos)
        + "\n"
        if texto_anexos.strip()
        else ""
    )
    user_content = REAVALIACAO_USER_TEMPLATE.format(
        itens_json=itens_json,
        texto_fornecedor=envelopar("DOC_FORNECEDOR", texto_forn),
        texto_engenharia=envelopar("DOC_ENGENHARIA", texto_eng),
        secao_anexos=secao_anexos,
        projeto=parecer.projeto,
        numero_parecer=parecer.numero_parecer,
    )
    logger.info(
        "Reavaliacao cirurgica: parecer=%s, itens=%s, modelo=%s",
        parecer_id,
        numeros_unicos,
        settings.GEMINI_ANALYSIS_MODEL,
    )
    resposta_text = await asyncio.to_thread(
        call_llm,
        REAVALIACAO_SYSTEM_PROMPT,
        user_content,
        model=settings.GEMINI_ANALYSIS_MODEL,
    )
    atualizacoes = _calcular_atualizacoes(
        {n: i.estado for n, i in itens.items()}, extract_json(resposta_text)
    )
    if not atualizacoes:
        raise ValueError(
            "A reavaliacao nao retornou resultado utilizavel — tente de novo."
        )

    mudancas: list[dict] = []
    for up in atualizacoes:
        item = itens[up["numero"]]
        status_anterior, estado_anterior = item.status, item.estado
        item.status = up["status"]
        item.estado = up["estado"]
        if up["justificativa_tecnica"]:
            item.justificativa_tecnica = up["justificativa_tecnica"]
        if up["status"] == "A":
            item.acao_requerida = None
        elif up["acao_requerida"]:
            item.acao_requerida = up["acao_requerida"]
        if up["valor_fornecedor"]:
            item.valor_fornecedor = up["valor_fornecedor"]
        if status_anterior != item.status:
            mudancas.append(
                {"numero": item.numero, "de": status_anterior, "para": item.status}
            )
        await registrar_auditoria(
            db,
            usuario,
            "item_reavaliado_via_julia",
            "item",
            recurso_id=str(item.id),
            detalhes=(
                f"item_numero={item.numero}; origem=reavaliacao_cirurgica; "
                f"status_anterior={status_anterior}; status_novo={item.status}; "
                f"estado_anterior={estado_anterior}; estado_novo={item.estado}"
            ),
        )

    # Avanco automatico (bloco 28->29): todos os itens ativos aceitos apos a
    # reavaliacao -> o caso segue sozinho para a verificacao final.
    estados_result = await db.execute(
        select(ItemParecer.estado).where(ItemParecer.parecer_id == parecer_id)
    )
    nova_fase = compute_avanco_automatico(
        parecer.fase_caso, [row[0] for row in estados_result.all()]
    )
    if nova_fase:
        logger.info(
            "Avanco automatico pos-reavaliacao: %s -> %s (parecer %s)",
            parecer.fase_caso,
            nova_fase,
            parecer_id,
        )
        parecer.fase_caso = nova_fase

    await db.commit()
    return {
        "total": len(atualizacoes),
        "mudancas": mudancas,
        "fase_caso": parecer.fase_caso,
    }
