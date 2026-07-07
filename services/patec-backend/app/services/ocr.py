"""
OCR/transcricao multimodal de documentos que a extracao normal nao le
(imagens png/jpg/webp e PDFs escaneados/so-imagem).

Roda em Celery (LLM-bound — nunca no request de upload, que estouraria o timeout).
Renderiza cada pagina/imagem e pede ao Gemini a transcricao fiel; concatena o
texto e atualiza `Documento.texto_extraido`. Depois enfileira a indexacao RAG.
Fecha o achado A2 (antes, imagem/scan entrava como texto vazio).
"""

import base64
import logging
import uuid

import fitz  # PyMuPDF
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.progress import set_progress
from app.models.documento import Documento
from app.services.llm_client import call_llm_multimodal

logger = logging.getLogger(__name__)

_sync_engine = None

_IMAGE_TYPES = {"png", "jpg", "jpeg", "webp"}
_MIME_BY_EXT = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
}
# Teto de paginas por documento — evita OCR de um PDF gigante consumir a cota toda.
_MAX_OCR_PAGES = 30

_OCR_SYSTEM = """Voce e um transcritor tecnico de documentos de engenharia. Transcreva
FIELMENTE e por completo todo o texto visivel na imagem, preservando numeros, unidades,
tags, tabelas (use ' | ' entre celulas) e a ordem de leitura. NAO resuma, NAO
interprete, NAO adicione comentarios. Se algo estiver ilegivel, escreva [ilegivel].
Responda apenas com o texto transcrito."""

_OCR_USER = "Transcreva integralmente o texto desta pagina/documento de engenharia."


def _get_sync_engine():
    global _sync_engine
    if _sync_engine is None:
        _sync_engine = create_engine(settings.DATABASE_URL_SYNC)
    return _sync_engine


def _render_paginas_pdf(conteudo: bytes) -> list[bytes]:
    """Renderiza cada pagina do PDF (bytes) como PNG (150 dpi) — PDFs escaneados."""
    doc = fitz.open(stream=conteudo, filetype="pdf")
    imagens: list[bytes] = []
    try:
        for i, page in enumerate(doc):
            if i >= _MAX_OCR_PAGES:
                break
            pix = page.get_pixmap(dpi=150)
            imagens.append(pix.tobytes("png"))
    finally:
        doc.close()
    return imagens


def run_ocr_sync(documento_id: str, conteudo: bytes) -> dict:
    """Corpo da task Celery: OCR de um documento imagem/PDF escaneado.

    Recebe os BYTES do arquivo (nao o caminho): o worker roda em outro
    container/host e nao compartilha o filesystem da API — passar os bytes pela
    fila e o unico caminho portavel (funciona local e em producao/Railway).
    """
    key = f"ocr:{documento_id}"
    engine = _get_sync_engine()
    try:
        with Session(engine) as db:
            doc = db.get(Documento, uuid.UUID(documento_id))
            if not doc:
                return {"error": "Documento nao encontrado"}

            ext = (doc.tipo_arquivo or "").lower()
            set_progress(key, 10, "Preparando OCR do documento...", "ocr")

            if ext in _IMAGE_TYPES:
                imagens = [(_MIME_BY_EXT.get(ext, "image/png"), conteudo)]
            elif ext == "pdf":
                imagens = [("image/png", p) for p in _render_paginas_pdf(conteudo)]
            else:
                set_progress(key, 100, f"OCR nao suporta .{ext}", "error")
                return {"error": f"OCR nao suportado para .{ext}"}

            if not imagens:
                set_progress(key, 100, "Documento sem paginas para OCR", "error")
                return {"error": "Nenhuma pagina para OCR"}

            # Transcreve pagina a pagina (fidelidade + progresso). Falha em uma
            # pagina nao derruba as demais.
            partes: list[str] = []
            total = len(imagens)
            for idx, (mime, raw) in enumerate(imagens, start=1):
                set_progress(
                    key, 10 + int(80 * idx / total),
                    f"Transcrevendo pagina {idx}/{total}...", "ocr",
                )
                try:
                    texto_pg = call_llm_multimodal(
                        _OCR_SYSTEM, _OCR_USER, [(mime, raw)], max_output_tokens=8192
                    )
                except Exception as e:
                    logger.warning("OCR falhou na pagina %d de %s: %s", idx, documento_id, e)
                    texto_pg = f"[pagina {idx}: falha no OCR]"
                if texto_pg.strip():
                    cabecalho = f"--- Pagina {idx} ---\n" if total > 1 else ""
                    partes.append(cabecalho + texto_pg.strip())

            texto = "\n\n".join(partes).strip()
            doc.texto_extraido = texto
            db.commit()

            set_progress(key, 95, "OCR concluido; indexando...", "ocr")
            try:
                from app.services.indexer import enqueue_indexing

                enqueue_indexing(documento_id)
            except Exception:
                logger.exception("Falha ao enfileirar indexacao pos-OCR de %s", documento_id)

            set_progress(
                key, 100,
                f"OCR concluido: {len(texto)} caracteres de {total} pagina(s).",
                "completed",
            )
            logger.info("OCR concluido para doc %s: %d chars", documento_id, len(texto))
            return {"chars": len(texto), "paginas": total}
    except Exception as e:
        logger.exception("OCR falhou para documento %s", documento_id)
        set_progress(key, 100, f"Erro no OCR: {str(e)[:200]}", "error")
        return {"error": str(e)[:300]}


def enqueue_ocr(documento_id: str, conteudo: bytes) -> str | None:
    """Enfileira o OCR no Celery (bytes em base64 na fila) e devolve o task id."""
    try:
        from app.worker import ocr_documento_task

        conteudo_b64 = base64.b64encode(conteudo).decode("ascii")
        task = ocr_documento_task.delay(documento_id, conteudo_b64)
        return task.id
    except Exception:
        logger.exception("Falha ao enfileirar OCR do documento %s", documento_id)
        return None
