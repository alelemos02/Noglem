import json
import logging
from typing import AsyncGenerator

import httpx

from app.core.config import settings
from app.models.documento import Documento
from app.models.documento_chunk import DocumentoChunk
from app.models.item_parecer import ItemParecer
from app.models.mensagem_chat import MensagemChat
from app.models.parecer import Parecer
from app.models.recomendacao import Recomendacao
from app.services.analyzer import _extract_json, _validate_parecer_json
from app.services.llm_prompt import SYSTEM_PROMPT

logger = logging.getLogger(__name__)


CHAT_SYSTEM_PROMPT = SYSTEM_PROMPT + """

## MODO CONVERSA

Voce agora esta em modo de conversa com o especialista responsavel pelo parecer tecnico.
O parecer tecnico ja foi gerado e esta disponivel como contexto na primeira mensagem.

### REGRAS DE CONVERSA
1. Mantenha o mesmo rigor tecnico e persona de engenheiro senior de instrumentacao e automacao
2. Responda em portugues, de forma profissional e tecnica
3. Quando o especialista questionar uma classificacao, cite EXCLUSIVAMENTE o trecho exato e a localizacao (documento, pagina, secao) nos documentos da engenharia que originou o requisito
4. Se o especialista solicitar alteracoes, discuta tecnicamente antes de concordar - voce pode concordar se o argumento tecnico for valido
5. Voce pode sugerir reclassificacoes se convencido pelo argumento tecnico do especialista
6. NUNCA invente informacoes que nao estejam nos documentos originais analisados. Se voce nao encontrar uma informacao especifica no texto dos documentos fornecidos, diga EXPLICITAMENTE que nao encontrou - NUNCA fabrique dados como TAGs, numeros de serie, especificacoes ou valores que nao estejam literalmente no texto dos documentos
7. Se questionado sobre algo fora do escopo dos documentos, informe claramente que a informacao nao consta nos documentos analisados. Quando citar qualquer dado (TAGs, valores, especificacoes), COPIE o texto exato do documento - nunca parafraseie ou reconstrua de memoria
8. Seja objetivo e direto nas respostas, mas sem perder profundidade tecnica
9. Se um requisito que voce classificou nao estiver explicitamente nos documentos da engenharia, RECONHECA IMEDIATAMENTE o erro: informe que o item nao tem base documental e proponha sua remocao ou reclassificacao como D (Informacao Ausente do Fornecedor nao se aplica - neste caso, o item deve ser REMOVIDO por nao ter origem na documentacao da engenharia)
10. NUNCA use boas praticas de engenharia, normas implicitas ou conhecimento proprio como fundamento para criar ou manter um item do parecer. O fundamento DEVE ser sempre o texto literal dos documentos da engenharia fornecidos.

### RESTRICAO ABSOLUTA - FIDELIDADE AOS DOCUMENTOS
Todo item classificado no parecer tecnico deve ter rastreabilidade direta e explicita aos documentos da engenharia fornecidos.
Se voce nao consegue apontar o trecho exato do documento que origina um requisito, o item NAO deve existir no parecer.
Boas praticas, normas implicitas e conhecimento tecnico proprio NUNCA justificam a existencia de um item - apenas os documentos da engenharia o fazem.

### GERACAO DE NOVA TABELA
Quando o especialista solicitar a geracao de uma nova tabela (frases como "gere nova tabela", "atualize o parecer", "refaca a analise", "incorpore as alteracoes"), voce deve:
1. Confirmar as alteracoes que serao incorporadas
2. Gerar o JSON completo do parecer_tecnico no formato padrao (com resumo_executivo, itens, conclusao, recomendacoes)
3. O JSON deve ser retornado EXCLUSIVAMENTE, sem texto antes ou depois, sem blocos de codigo markdown

### FORMATO DE RESPOSTA
- Para respostas conversacionais: texto livre em markdown (pode usar **negrito**, listas, tabelas, etc.)
- Para geracao de nova tabela: retorne SOMENTE o JSON valido no formato do parecer_tecnico
"""


def build_chat_context(
    parecer: Parecer,
    itens: list[ItemParecer],
    recomendacoes: list[Recomendacao],
    documentos: list[Documento],
    mensagens: list[MensagemChat],
    nova_mensagem: str,
    retrieved_chunks: list[DocumentoChunk] | None = None,
    include_full_text: bool = False,
) -> tuple[str, list[dict]]:
    """Build system prompt and contents array for Gemini multi-turn chat.

    When retrieved_chunks is provided (RAG mode), uses semantically relevant
    chunks instead of full document text. Falls back to full text when
    chunks are not available or for table regeneration.
    """

    eng_docs = [d for d in documentos if d.tipo == "engenharia"]
    forn_docs = [d for d in documentos if d.tipo == "fornecedor"]

    # Build compact items summary
    itens_summary = json.dumps([{
        "numero": i.numero,
        "categoria": i.categoria,
        "descricao_requisito": i.descricao_requisito[:200],
        "valor_requerido": (i.valor_requerido or "")[:150],
        "valor_fornecedor": (i.valor_fornecedor or "")[:150],
        "status": i.status,
        "justificativa_tecnica": i.justificativa_tecnica[:300] if i.justificativa_tecnica else "",
        "acao_requerida": (i.acao_requerida or "")[:200],
        "prioridade": i.prioridade,
    } for i in itens], ensure_ascii=False)

    context_parts = [
        f"## CONTEXTO DO PARECER TECNICO",
        f"Numero: {parecer.numero_parecer}",
        f"Projeto: {parecer.projeto}",
        f"Fornecedor: {parecer.fornecedor}",
        f"Parecer Geral: {parecer.parecer_geral or 'N/A'}",
        f"Total Itens: {parecer.total_itens}",
        f"Aprovados: {parecer.total_aprovados} | Com Comentarios: {parecer.total_aprovados_comentarios} | Rejeitados: {parecer.total_rejeitados} | Info Ausente: {parecer.total_info_ausente} | Adicionais: {parecer.total_itens_adicionais}",
        "",
        f"## DOCUMENTOS ANALISADOS",
        f"Engenharia: {', '.join(d.nome_arquivo for d in eng_docs)}",
        f"Fornecedor: {', '.join(d.nome_arquivo for d in forn_docs)}",
        "",
        f"## TABELA DE ITENS ATUAL",
        itens_summary,
        "",
        f"## CONCLUSAO",
        parecer.conclusao or "N/A",
        "",
        f"## RECOMENDACOES",
        "\n".join(f"- {r.texto}" for r in recomendacoes) or "N/A",
    ]

    # Include document content: either RAG chunks (preferred) or full text (fallback)
    if retrieved_chunks and not include_full_text:
        # RAG mode: include only semantically relevant chunks
        context_parts.extend([
            "",
            "## TRECHOS RELEVANTES DOS DOCUMENTOS (recuperados por relevancia semantica)",
            "Os trechos abaixo foram selecionados automaticamente como os mais relevantes "
            "para a pergunta atual. Cite SEMPRE o documento e pagina ao referenciar informacoes.",
            "Se a informacao necessaria nao estiver nestes trechos, informe que nao encontrou "
            "nos trechos disponibilizados.",
            "",
        ])
        for chunk in retrieved_chunks:
            tipo_label = "Engenharia" if chunk.tipo_documento == "engenharia" else "Fornecedor"
            page_info = f"Pagina {chunk.page_number}" if chunk.page_number else "Pagina ?"
            chunk_label = "TABELA" if chunk.chunk_type == "table" else "TEXTO"
            header = f"### [{tipo_label}] {chunk.nome_arquivo} - {page_info} ({chunk_label})"
            context_parts.append(f"{header}\n{chunk.conteudo}\n")
    else:
        # Full text mode: used for table regeneration or when RAG is not available
        context_parts.extend([
            "",
            "## TEXTO COMPLETO DOS DOCUMENTOS DA ENGENHARIA",
            "\n\n---\n\n".join(
                f"### {d.nome_arquivo}\n\n{d.texto_extraido or ''}"
                for d in eng_docs
            ),
            "",
            "## TEXTO COMPLETO DOS DOCUMENTOS DO FORNECEDOR",
            "\n\n---\n\n".join(
                f"### {d.nome_arquivo}\n\n{d.texto_extraido or ''}"
                for d in forn_docs
            ),
        ])

    context_msg = "\n".join(context_parts)

    contents = [
        {"role": "user", "parts": [{"text": context_msg}]},
        {"role": "model", "parts": [{"text": (
            "Entendido. Tenho o contexto completo do parecer tecnico "
            f"'{parecer.numero_parecer}' para o projeto '{parecer.projeto}', "
            f"fornecedor '{parecer.fornecedor}'. "
            f"O parecer geral e '{parecer.parecer_geral}' com {parecer.total_itens} itens analisados. "
            "Estou pronto para discutir os itens, justificativas, classificacoes e "
            "quaisquer questoes tecnicas. Como posso ajudar?"
        )}]},
    ]

    # Add conversation history (sliding window: last 20 messages)
    recent = mensagens[-20:] if len(mensagens) > 20 else mensagens
    for msg in recent:
        role = "user" if msg.papel == "user" else "model"
        contents.append({"role": role, "parts": [{"text": msg.conteudo}]})

    # Add new message
    contents.append({"role": "user", "parts": [{"text": nova_mensagem}]})

    return CHAT_SYSTEM_PROMPT, contents


async def call_gemini_stream_async(
    system_prompt: str,
    contents: list[dict],
    max_tokens: int = 8192,
) -> AsyncGenerator[str, None]:
    """Call Gemini streaming API, yielding text chunks as they arrive."""
    api_key = settings.GEMINI_API_KEY.strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY nao configurada")

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.GEMINI_MODEL}:streamGenerateContent"
    )
    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": contents,
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": max_tokens,
        },
    }

    async with httpx.AsyncClient(timeout=180.0) as client:
        async with client.stream(
            "POST", url, params={"key": api_key, "alt": "sse"}, json=payload
        ) as response:
            if response.status_code >= 400:
                body = await response.aread()
                detail = None
                try:
                    data = json.loads(body)
                    detail = data.get("error", {}).get("message")
                except Exception:
                    detail = body.decode("utf-8", errors="replace")
                raise RuntimeError(f"Erro Gemini API ({response.status_code}): {detail}")

            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                raw = line[6:]
                if raw.strip() == "[DONE]":
                    break
                try:
                    chunk_data = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                candidates = chunk_data.get("candidates", [])
                if not candidates:
                    continue
                parts = candidates[0].get("content", {}).get("parts", [])
                for part in parts:
                    text = part.get("text", "")
                    if text:
                        yield text


def detect_table_regeneration(response_text: str) -> dict | None:
    """Check if the LLM response contains a new parecer_tecnico JSON.

    Returns validated parecer data if found, None otherwise.
    """
    try:
        data = _extract_json(response_text)
        if "parecer_tecnico" in data:
            return _validate_parecer_json(data)
        if "itens" in data and "resumo_executivo" in data:
            return _validate_parecer_json({"parecer_tecnico": data})
    except (json.JSONDecodeError, Exception):
        pass
    return None


def apply_table_update(db_session, parecer, result: dict):
    """Apply a new parecer_tecnico JSON to the database.

    This replaces items and recommendations with the new data.
    Uses the same logic as tasks.py run_analysis_sync (lines 162-224).
    Expects a synchronous SQLAlchemy session.
    """
    db_session.execute(
        ItemParecer.__table__.delete().where(ItemParecer.parecer_id == parecer.id)
    )
    db_session.execute(
        Recomendacao.__table__.delete().where(Recomendacao.parecer_id == parecer.id)
    )

    pt = result.get("parecer_tecnico", result)
    resumo = pt.get("resumo_executivo", {})
    itens = pt.get("itens", [])

    for item_data in itens:
        db_session.add(
            ItemParecer(
                parecer_id=parecer.id,
                numero=item_data.get("numero", 0),
                categoria=item_data.get("categoria"),
                descricao_requisito=item_data.get("descricao_requisito", ""),
                referencia_engenharia=item_data.get("referencia_engenharia"),
                referencia_fornecedor=item_data.get("referencia_fornecedor"),
                valor_requerido=item_data.get("valor_requerido"),
                valor_fornecedor=item_data.get("valor_fornecedor"),
                status=item_data.get("status", "D"),
                justificativa_tecnica=item_data.get("justificativa_tecnica", ""),
                acao_requerida=item_data.get("acao_requerida"),
                prioridade=item_data.get("prioridade"),
                norma_referencia=item_data.get("norma_referencia"),
            )
        )

    recomendacoes_data = pt.get("recomendacoes", [])
    for i, texto in enumerate(recomendacoes_data):
        db_session.add(
            Recomendacao(
                parecer_id=parecer.id,
                texto=texto if isinstance(texto, str) else str(texto),
                ordem=i + 1,
            )
        )

    parecer.total_itens = resumo.get("total_itens", len(itens))
    parecer.total_aprovados = resumo.get("aprovados", 0)
    parecer.total_aprovados_comentarios = resumo.get("aprovados_com_comentarios", 0)
    parecer.total_rejeitados = resumo.get("rejeitados", 0)
    parecer.total_info_ausente = resumo.get("informacao_ausente", 0)
    parecer.total_itens_adicionais = resumo.get("itens_adicionais_fornecedor", 0)
    parecer.parecer_geral = resumo.get("parecer_geral")
    parecer.comentario_geral = resumo.get("comentario_geral")
    parecer.conclusao = pt.get("conclusao")

    db_session.commit()
    return len(itens)
