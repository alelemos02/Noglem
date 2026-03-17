"""Gemini Embedding Service for PATEC RAG.

Uses the Gemini gemini-embedding-001 model to generate 3072-dimensional embeddings
for document chunks (RETRIEVAL_DOCUMENT) and search queries (RETRIEVAL_QUERY).
"""

import asyncio
import json
import logging
import random
from typing import Literal

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

GEMINI_EMBEDDING_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:batchEmbedContents"
)

# Maximum texts per batch request (Gemini API limit)
MAX_BATCH_SIZE = 100

TaskType = Literal["RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY"]


async def embed_texts(
    texts: list[str],
    task_type: TaskType = "RETRIEVAL_DOCUMENT",
) -> list[list[float]]:
    """Embed a list of texts using Gemini text-embedding-004.

    Args:
        texts: List of text strings to embed.
        task_type: RETRIEVAL_DOCUMENT for indexing, RETRIEVAL_QUERY for search.

    Returns:
        List of 768-dimensional embedding vectors.
    """
    if not texts:
        return []

    api_key = settings.GEMINI_API_KEY.strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY nao configurada")

    model = settings.GEMINI_EMBEDDING_MODEL
    all_embeddings: list[list[float]] = []

    # Process in batches of MAX_BATCH_SIZE
    for batch_start in range(0, len(texts), MAX_BATCH_SIZE):
        batch = texts[batch_start : batch_start + MAX_BATCH_SIZE]
        embeddings = await _embed_batch(batch, model, task_type, api_key)
        all_embeddings.extend(embeddings)

    return all_embeddings


async def embed_query(query: str) -> list[float]:
    """Embed a single search query.

    Convenience wrapper around embed_texts with RETRIEVAL_QUERY task type.
    """
    results = await embed_texts([query], task_type="RETRIEVAL_QUERY")
    return results[0]


async def _embed_batch(
    texts: list[str],
    model: str,
    task_type: TaskType,
    api_key: str,
) -> list[list[float]]:
    """Embed a single batch (up to 100 texts) with retry logic."""
    url = GEMINI_EMBEDDING_URL.format(model=model)

    payload = {
        "requests": [
            {
                "model": f"models/{model}",
                "content": {"parts": [{"text": text}]},
                "taskType": task_type,
            }
            for text in texts
        ]
    }

    max_retries = settings.GEMINI_MAX_RETRIES
    base_delay = settings.GEMINI_RETRY_BASE_SECONDS
    max_delay = settings.GEMINI_RETRY_MAX_SECONDS

    for attempt in range(max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    url,
                    params={"key": api_key},
                    json=payload,
                )

            if response.status_code == 200:
                data = response.json()
                embeddings = []
                for emb in data.get("embeddings", []):
                    values = emb.get("values", [])
                    embeddings.append(values)
                return embeddings

            # Retry on 429 (rate limit) or 5xx (server error)
            if response.status_code in (429, 500, 502, 503) and attempt < max_retries:
                delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay)
                logger.warning(
                    "Gemini embedding API returned %d, retrying in %.1fs (attempt %d/%d)",
                    response.status_code,
                    delay,
                    attempt + 1,
                    max_retries,
                )
                await asyncio.sleep(delay)
                continue

            # Non-retryable error
            body = response.text
            detail = None
            try:
                err_data = json.loads(body)
                detail = err_data.get("error", {}).get("message")
            except Exception:
                detail = body[:500]
            raise RuntimeError(
                f"Gemini Embedding API error ({response.status_code}): {detail}"
            )

        except httpx.TimeoutException:
            if attempt < max_retries:
                delay = min(base_delay * (2 ** attempt), max_delay)
                logger.warning(
                    "Gemini embedding timeout, retrying in %.1fs (attempt %d/%d)",
                    delay,
                    attempt + 1,
                    max_retries,
                )
                await asyncio.sleep(delay)
                continue
            raise RuntimeError("Gemini Embedding API timeout after all retries")

    raise RuntimeError("Gemini Embedding API failed after all retries")
