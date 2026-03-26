import os
import uuid
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.config import settings
from app.dependencies.rate_limit import enforce_pid_rate_limit
from app.dependencies.security import require_internal_api_key
from app.services.pid_extract_service import PidExtractService

router = APIRouter(dependencies=[Depends(require_internal_api_key)])
pid_service = PidExtractService()


def validate_pdf(file: UploadFile):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Nome do arquivo não fornecido")
    ext = os.path.splitext(file.filename)[1].lower()
    if ext != ".pdf":
        raise HTTPException(status_code=400, detail=f"Tipo de arquivo não permitido: {ext}")


@router.post("/extract")
async def extract_instruments(
    file: UploadFile = File(...),
    profile: str = Form("promon"),
    use_llm: str = Form("false"),
    _: None = Depends(enforce_pid_rate_limit),
):
    """Extrai instrumentos de um P&ID (PDF vetorial) e retorna JSON."""
    validate_pdf(file)

    if profile not in ("promon", "technip"):
        raise HTTPException(status_code=400, detail=f"Profile inválido: {profile}")

    enable_llm = use_llm.lower() == "true"
    file_id = str(uuid.uuid4())
    temp_path = os.path.join(settings.UPLOAD_DIR, f"{file_id}.pdf")

    try:
        content = await file.read()
        with open(temp_path, "wb") as f:
            f.write(content)

        result = pid_service.extract_to_json(temp_path, profile_name=profile, use_llm=enable_llm)
        result["filename"] = file.filename or "unknown.pdf"
        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro na extração: {str(e)}")
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@router.post("/extract/preview")
async def extract_preview(
    file: UploadFile = File(...),
    profile: str = Form("promon"),
    use_llm: str = Form("false"),
    _: None = Depends(enforce_pid_rate_limit),
):
    """Extrai instrumentos e retorna PDF anotado vetorial com marcacoes coloridas."""
    validate_pdf(file)

    if profile not in ("promon", "technip"):
        raise HTTPException(status_code=400, detail=f"Profile inválido: {profile}")

    enable_llm = use_llm.lower() == "true"
    file_id = str(uuid.uuid4())
    temp_pdf = os.path.join(settings.UPLOAD_DIR, f"{file_id}.pdf")
    output_pdf = os.path.join(settings.OUTPUT_DIR, f"{file_id}_annotated.pdf")

    try:
        content = await file.read()
        with open(temp_pdf, "wb") as f:
            f.write(content)

        pid_service.extract_to_annotated_pdf(temp_pdf, output_pdf, profile_name=profile, use_llm=enable_llm)

        return FileResponse(
            output_pdf,
            media_type="application/pdf",
            filename=f"{os.path.splitext(file.filename or 'pid')[0]}_anotado.pdf",
        )

    except Exception as e:
        for path in [temp_pdf, output_pdf]:
            if os.path.exists(path):
                os.remove(path)
        raise HTTPException(status_code=500, detail=f"Erro na extração: {str(e)}")


@router.post("/extract/download")
async def download_excel(
    file: UploadFile = File(...),
    profile: str = Form("promon"),
    use_llm: str = Form("false"),
    _: None = Depends(enforce_pid_rate_limit),
):
    """Extrai instrumentos e retorna como arquivo Excel."""
    validate_pdf(file)

    if profile not in ("promon", "technip"):
        raise HTTPException(status_code=400, detail=f"Profile inválido: {profile}")

    enable_llm = use_llm.lower() == "true"
    file_id = str(uuid.uuid4())
    temp_pdf = os.path.join(settings.UPLOAD_DIR, f"{file_id}.pdf")
    output_excel = os.path.join(settings.OUTPUT_DIR, f"{file_id}_pid.xlsx")

    try:
        content = await file.read()
        with open(temp_pdf, "wb") as f:
            f.write(content)

        pid_service.extract_to_excel(temp_pdf, output_excel, profile_name=profile, use_llm=enable_llm)

        return FileResponse(
            output_excel,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=f"{os.path.splitext(file.filename or 'pid')[0]}_instrument_index.xlsx",
        )

    except Exception as e:
        for path in [temp_pdf, output_excel]:
            if os.path.exists(path):
                os.remove(path)
        raise HTTPException(status_code=500, detail=f"Erro na extração: {str(e)}")
