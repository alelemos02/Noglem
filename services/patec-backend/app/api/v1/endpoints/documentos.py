import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.models.usuario import Usuario
from app.models.parecer import Parecer
from app.models.documento import Documento
from app.schemas.documento import DocumentoResponse
from app.services.document_crypto import encrypt_bytes, decrypted_temp_file
from app.services.text_extractor import extract_text

router = APIRouter(prefix="/pareceres/{parecer_id}/documentos", tags=["documentos"])

ALLOWED_EXTENSIONS = {"pdf", "docx", "xlsx"}
MAX_FILE_SIZE = settings.MAX_FILE_SIZE_MB * 1024 * 1024


def _get_extension(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def _to_response(d: Documento) -> DocumentoResponse:
    return DocumentoResponse(
        id=str(d.id),
        parecer_id=str(d.parecer_id),
        tipo=d.tipo,
        nome_arquivo=d.nome_arquivo,
        tipo_arquivo=d.tipo_arquivo,
        tamanho_bytes=d.tamanho_bytes,
        criado_em=d.criado_em,
    )


async def _get_parecer(parecer_id: uuid.UUID, db: AsyncSession) -> Parecer:
    result = await db.execute(select(Parecer).where(Parecer.id == parecer_id))
    parecer = result.scalar_one_or_none()
    if not parecer:
        raise HTTPException(status_code=404, detail="Parecer nao encontrado")
    return parecer


async def _upload_doc(
    parecer_id: uuid.UUID,
    tipo: str,
    file: UploadFile,
    db: AsyncSession,
) -> DocumentoResponse:
    parecer = await _get_parecer(parecer_id, db)

    ext = _get_extension(file.filename or "")
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de arquivo nao permitido: .{ext}. Permitidos: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Arquivo excede o tamanho maximo de {settings.MAX_FILE_SIZE_MB}MB",
        )

    # Save file
    upload_dir = os.path.join(settings.UPLOAD_DIR, str(parecer.id), tipo)
    os.makedirs(upload_dir, exist_ok=True)

    file_id = str(uuid.uuid4())
    file_path = os.path.join(upload_dir, f"{file_id}.{ext}")

    with open(file_path, "wb") as f:
        f.write(encrypt_bytes(content))

    # Extract text
    try:
        with decrypted_temp_file(file_path, ext) as decrypted_path:
            texto = extract_text(decrypted_path, ext)
    except Exception as e:
        os.remove(file_path)
        raise HTTPException(status_code=400, detail=f"Erro ao extrair texto: {str(e)}")

    # Save to DB
    documento = Documento(
        parecer_id=parecer.id,
        tipo=tipo,
        nome_arquivo=file.filename or f"arquivo.{ext}",
        tipo_arquivo=ext,
        tamanho_bytes=len(content),
        caminho_storage=file_path,
        texto_extraido=texto,
    )
    db.add(documento)
    await db.commit()
    await db.refresh(documento)

    return _to_response(documento)


@router.post("/engenharia", response_model=DocumentoResponse, status_code=status.HTTP_201_CREATED)
async def upload_engenharia(
    parecer_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_role("admin", "analista")),
):
    return await _upload_doc(parecer_id, "engenharia", file, db)


@router.post("/fornecedor", response_model=DocumentoResponse, status_code=status.HTTP_201_CREATED)
async def upload_fornecedor(
    parecer_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_role("admin", "analista")),
):
    return await _upload_doc(parecer_id, "fornecedor", file, db)


@router.get("", response_model=list[DocumentoResponse])
async def listar_documentos(
    parecer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    await _get_parecer(parecer_id, db)
    result = await db.execute(
        select(Documento).where(Documento.parecer_id == parecer_id).order_by(Documento.criado_em)
    )
    docs = result.scalars().all()
    return [_to_response(d) for d in docs]


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remover_documento(
    parecer_id: uuid.UUID,
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Usuario = Depends(require_role("admin", "analista")),
):
    result = await db.execute(
        select(Documento).where(Documento.id == doc_id, Documento.parecer_id == parecer_id)
    )
    documento = result.scalar_one_or_none()
    if not documento:
        raise HTTPException(status_code=404, detail="Documento nao encontrado")

    # Remove file
    if os.path.exists(documento.caminho_storage):
        os.remove(documento.caminho_storage)

    await db.delete(documento)
    await db.commit()
