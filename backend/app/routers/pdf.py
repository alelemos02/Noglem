import os
import uuid
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.config import settings
from app.dependencies.rate_limit import enforce_pdf_rate_limit
from app.dependencies.security import require_internal_api_key
from app.models.schemas import ExtractResponse, ConvertResponse
from app.services.pdf_extract_service import PdfExtractService
from app.services.pdf_convert_service import PdfConvertService

router = APIRouter(dependencies=[Depends(require_internal_api_key)])
extract_service = PdfExtractService()
convert_service = PdfConvertService()


def validate_pdf(file: UploadFile):
    """Valida se o arquivo é um PDF válido."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Nome do arquivo não fornecido")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400, detail=f"Tipo de arquivo não permitido: {ext}"
        )


@router.post("/extract", response_model=ExtractResponse)
async def extract_tables(
    file: UploadFile = File(...),
    _: None = Depends(enforce_pdf_rate_limit),
):
    """
    Extrai tabelas de um arquivo PDF.
    """
    validate_pdf(file)

    # Salvar arquivo temporariamente
    file_id = str(uuid.uuid4())
    temp_path = os.path.join(settings.UPLOAD_DIR, f"{file_id}.pdf")

    try:
        # Salvar upload
        content = await file.read()
        with open(temp_path, "wb") as f:
            f.write(content)

        # Extrair tabelas
        result = extract_service.extract_tables(temp_path)

        return ExtractResponse(
            filename=file.filename or "unknown.pdf",
            total_pages=result["total_pages"],
            tables_found=result["tables_found"],
            tables=result["tables"],
        )

    finally:
        # Limpar arquivo temporário
        if os.path.exists(temp_path):
            os.remove(temp_path)


@router.post("/extract/download")
async def download_excel(
    file: UploadFile = File(...),
    _: None = Depends(enforce_pdf_rate_limit),
):
    """
    Extrai tabelas e retorna como arquivo Excel.
    """
    validate_pdf(file)

    file_id = str(uuid.uuid4())
    temp_pdf = os.path.join(settings.UPLOAD_DIR, f"{file_id}.pdf")
    output_excel = os.path.join(settings.OUTPUT_DIR, f"{file_id}.xlsx")

    try:
        # Salvar upload
        content = await file.read()
        with open(temp_pdf, "wb") as f:
            f.write(content)

        # Extrair e salvar como Excel
        extract_service.extract_to_excel(temp_pdf, output_excel)

        return FileResponse(
            output_excel,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=f"{os.path.splitext(file.filename or 'tables')[0]}.xlsx",
        )

    except Exception as e:
        # Limpar arquivos em caso de erro
        for path in [temp_pdf, output_excel]:
            if os.path.exists(path):
                os.remove(path)
        raise HTTPException(status_code=500, detail=f"Erro na extração: {str(e)}")


@router.post("/convert", response_model=ConvertResponse)
async def convert_to_word(
    file: UploadFile = File(...),
    _: None = Depends(enforce_pdf_rate_limit),
):
    """
    Converte PDF para documento Word.
    """
    validate_pdf(file)

    file_id = str(uuid.uuid4())
    temp_pdf = os.path.join(settings.UPLOAD_DIR, f"{file_id}.pdf")
    output_docx = os.path.join(settings.OUTPUT_DIR, f"{file_id}.docx")

    try:
        # Salvar upload
        content = await file.read()
        original_size = len(content)

        with open(temp_pdf, "wb") as f:
            f.write(content)

        # Converter
        convert_service.convert(temp_pdf, output_docx)

        converted_size = os.path.getsize(output_docx)

        return ConvertResponse(
            filename=file.filename or "document.pdf",
            original_size=original_size,
            converted_size=converted_size,
            download_url=f"/api/pdf/download/{file_id}",
        )

    except Exception as e:
        # Limpar arquivos em caso de erro
        for path in [temp_pdf, output_docx]:
            if os.path.exists(path):
                os.remove(path)
        raise HTTPException(status_code=500, detail=f"Erro na conversão: {str(e)}")


@router.get("/download/{file_id}")
async def download_converted(
    file_id: str,
    _: None = Depends(enforce_pdf_rate_limit),
):
    """
    Baixa arquivo convertido.
    """
    docx_path = os.path.join(settings.OUTPUT_DIR, f"{file_id}.docx")

    if not os.path.exists(docx_path):
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")

    return FileResponse(
        docx_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename="converted.docx",
    )
