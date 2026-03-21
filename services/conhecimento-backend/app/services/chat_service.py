"""Chat service for Conhecimento RAG.

Uses Gemini 2.0 Flash for streaming chat responses with RAG context.
Adapted from PATEC's chat service — domain-agnostic system prompt.
"""

import json
import logging
from typing import AsyncGenerator

import httpx

from app.core.config import settings
from app.models.document_chunk import DocumentoChunk

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Voce e um analista de IA senior e engenheiro de sistemas (Persona: NotebookLM/Deep Researcher).\n"
    "Sua tarefa e sintetizar documentos tecnicos em narrativas ricas, estruturadas e densas.\n"
    "\n"
    "ESTRUTURA DE RESPOSTA (Estilo Deep Dive):\n"
    "- Se o usuario pedir um RESUMO ou PRINCIPAIS PONTOS, use uma estrutura numerada (1, 2, 3...) com titulos em negrito.\n"
    "- Para cada ponto, escreva um paragrafo denso explicando o 'Porque', o 'Como' e as 'Consequencias'. Nao seja superficial.\n"
    "- Conecte os pontos: Mostre como o ponto 1 afeta o ponto 3.\n"
    "- **INTRODUCAO**: Comece com um paragrafo de introducao contextualizando o tema.\n"
    "- **CONCLUSAO**: Termine com um paragrafo de sintese ou reflexao final.\n"
    "\n"
    "DIRETRIZES DE QUALIDADE:\n"
    "1. **Visao Holistica**: Identifique os 'Grandes Temas' mesmo que estejam espalhados.\n"
    "2. **Analogias**: Se util, use analogias para fixar o conceito.\n"
    "3. **Citacoes (OBRIGATORIO)**: Para CADA afirmacao tecnica ou fatica, inclua a citacao imediatamente apos a frase. "
    "Use o formato: `[NomeDoArquivo.pdf, Pagina: X]`. Se o paragrafo for baseado em multiplas paginas, cite todas.\n"
    "4. **Citacoes no Fim do Ponto**: Ao final de cada ponto, adicione: '*Fontes: [Arquivo.pdf, Pagina: X]*'.\n"
    "\n"
    "- SE O CONTEXTO PARECER TOTALMENTE IRRELEVANTE para a pergunta, diga que nao encontrou informacoes especificas. "
    "Porem, se o usuario pedir 'o que diz o documento' ou um 'resumo', tente resumir o que esta no contexto.\n"
)


def build_chat_context(
    chunks: list[DocumentoChunk],
    chat_history: list[dict],
    new_message: str,
) -> tuple[str, list[dict]]:
    """Build system prompt and contents array for Gemini multi-turn chat.

    Args:
        chunks: Retrieved and reranked document chunks.
        chat_history: List of {"role": "user"|"assistant", "content": str} dicts.
        new_message: The user's new question.

    Returns:
        Tuple of (system_prompt, contents) for Gemini API.
    """
    # Build context from chunks
    context_parts = []
    if chunks:
        context_parts.append("## TRECHOS RELEVANTES DOS DOCUMENTOS")
        context_parts.append(
            "Os trechos abaixo foram selecionados automaticamente como os mais relevantes "
            "para a pergunta atual. Cite SEMPRE o documento e pagina ao referenciar informacoes."
        )
        context_parts.append("")

        for chunk in chunks:
            page_info = f"Pagina {chunk.page_number}" if chunk.page_number else "Pagina ?"
            chunk_label = "TABELA" if chunk.chunk_type == "table" else "TEXTO"
            header = f"### {chunk.nome_arquivo} - {page_info} ({chunk_label})"
            context_parts.append(f"{header}\n{chunk.conteudo}\n")
    else:
        context_parts.append("Nenhum documento relevante encontrado para esta pergunta.")

    context_msg = "\n".join(context_parts)

    # Build system prompt with context
    full_system_prompt = SYSTEM_PROMPT

    # Build multi-turn conversation
    contents = [
        {"role": "user", "parts": [{"text": context_msg}]},
        {"role": "model", "parts": [{"text": (
            "Entendido. Tenho acesso aos trechos relevantes dos documentos da colecao. "
            "Estou pronto para responder perguntas com base nesse conteudo, "
            "sempre citando as fontes. Como posso ajudar?"
        )}]},
    ]

    # Add conversation history (sliding window: last 10 exchanges)
    recent = chat_history[-20:] if len(chat_history) > 20 else chat_history
    for msg in recent:
        role = "user" if msg["role"] == "user" else "model"
        content = msg["content"][:2000]  # Truncate long messages
        contents.append({"role": role, "parts": [{"text": content}]})

    # Add new message
    contents.append({"role": "user", "parts": [{"text": new_message}]})

    return full_system_prompt, contents


async def call_gemini_stream(
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


async def call_gemini_sync(
    system_prompt: str,
    contents: list[dict],
    max_tokens: int = 8192,
) -> str:
    """Call Gemini API synchronously (non-streaming) and return the full response."""
    api_key = settings.GEMINI_API_KEY.strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY nao configurada")

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.GEMINI_MODEL}:generateContent"
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
        response = await client.post(
            url, params={"key": api_key}, json=payload
        )

    if response.status_code >= 400:
        detail = None
        try:
            data = response.json()
            detail = data.get("error", {}).get("message")
        except Exception:
            detail = response.text[:500]
        raise RuntimeError(f"Erro Gemini API ({response.status_code}): {detail}")

    data = response.json()
    candidates = data.get("candidates", [])
    if not candidates:
        return "Nao foi possivel gerar uma resposta."

    parts = candidates[0].get("content", {}).get("parts", [])
    return "".join(p.get("text", "") for p in parts)
