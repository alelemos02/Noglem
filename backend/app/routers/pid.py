import os
import json
import shutil
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from starlette.datastructures import UploadFile as StarletteUploadFile

from app.config import settings
from app.dependencies.rate_limit import enforce_pid_rate_limit
from app.dependencies.security import require_internal_api_key
from app.services.pid_extract_service import PidExtractService

router = APIRouter(dependencies=[Depends(require_internal_api_key)])
pid_service = PidExtractService()
BATCH_DIR = os.path.join(settings.UPLOAD_DIR, "pid-batches")


def validate_pdf(file: UploadFile):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Nome do arquivo não fornecido")
    ext = os.path.splitext(file.filename)[1].lower()
    if ext != ".pdf":
        raise HTTPException(status_code=400, detail=f"Tipo de arquivo não permitido: {ext}")


def cleanup_files(paths: list[str]) -> None:
    for path in paths:
        if os.path.exists(path):
            os.remove(path)


def validate_profile(profile: str) -> None:
    if profile not in ("promon", "technip"):
        raise HTTPException(status_code=400, detail=f"Profile inválido: {profile}")


def batch_path(batch_id: str) -> str:
    if not batch_id or "/" in batch_id or "\\" in batch_id or ".." in batch_id:
        raise HTTPException(status_code=400, detail="Batch inválido")
    return os.path.join(BATCH_DIR, batch_id)


def cleanup_batch(batch_id: str, extra_paths: list[str] | None = None) -> None:
    if extra_paths:
        cleanup_files(extra_paths)

    path = batch_path(batch_id)
    if os.path.exists(path):
        shutil.rmtree(path, ignore_errors=True)


def load_batch_manifest(batch_id: str) -> tuple[list[str], dict[str, str]]:
    path = batch_path(batch_id)
    manifest_path = os.path.join(path, "manifest.json")
    if not os.path.exists(manifest_path):
        raise HTTPException(status_code=404, detail="Batch não encontrado")

    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)

    files = sorted(manifest.get("files", []), key=lambda item: item["index"])
    temp_paths = [item["path"] for item in files]
    source_filenames = {
        str(Path(item["path"]).resolve()): item["filename"]
        for item in files
    }

    if not temp_paths:
        raise HTTPException(status_code=400, detail="Batch sem arquivos")

    return temp_paths, source_filenames


async def parse_pid_uploads(request: Request) -> tuple[list[StarletteUploadFile], str, bool]:
    form = await request.form()
    uploads = [
        item
        for item in [*form.getlist("files"), *form.getlist("file")]
        if isinstance(item, StarletteUploadFile)
    ]

    if not uploads:
        raise HTTPException(status_code=400, detail="Nenhum arquivo PDF fornecido")

    profile = str(form.get("profile") or "promon")
    validate_profile(profile)

    use_llm = str(form.get("use_llm") or "false").lower() == "true"
    return uploads, profile, use_llm


async def save_pid_uploads(files: list[StarletteUploadFile]) -> tuple[list[str], dict[str, str]]:
    temp_paths: list[str] = []
    source_filenames: dict[str, str] = {}

    for index, file in enumerate(files):
        validate_pdf(file)
        file_id = str(uuid.uuid4())
        temp_path = os.path.join(settings.UPLOAD_DIR, f"{file_id}_{index}.pdf")
        content = await file.read()
        with open(temp_path, "wb") as f:
            f.write(content)

        resolved_path = str(Path(temp_path).resolve())
        source_filenames[resolved_path] = file.filename or f"pid_{index + 1}.pdf"
        temp_paths.append(temp_path)

    return temp_paths, source_filenames


@router.post("/extract/batch/start")
async def start_batch():
    """Cria um batch temporário para exportação consolidada."""
    os.makedirs(BATCH_DIR, exist_ok=True)
    batch_id = str(uuid.uuid4())
    path = batch_path(batch_id)
    os.makedirs(path, exist_ok=False)

    with open(os.path.join(path, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump({"files": []}, f)

    return {"batch_id": batch_id}


@router.post("/extract/batch/upload")
async def upload_batch_file(
    batch_id: str = Form(...),
    index: int = Form(...),
    file: UploadFile = File(...),
    _: None = Depends(enforce_pid_rate_limit),
):
    """Recebe um PDF do batch mantendo o limite de upload por arquivo."""
    validate_pdf(file)

    path = batch_path(batch_id)
    manifest_path = os.path.join(path, "manifest.json")
    if not os.path.exists(manifest_path):
        raise HTTPException(status_code=404, detail="Batch não encontrado")

    temp_path = os.path.join(path, f"{index:04d}_{uuid.uuid4()}.pdf")
    try:
        content = await file.read()
        with open(temp_path, "wb") as f:
            f.write(content)

        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)

        manifest["files"] = [
            item for item in manifest.get("files", [])
            if item.get("index") != index
        ]
        manifest["files"].append({
            "index": index,
            "path": temp_path,
            "filename": file.filename or f"pid_{index + 1}.pdf",
        })

        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f)

        return {"ok": True}
    except Exception:
        cleanup_files([temp_path])
        raise


@router.post("/extract/batch/download")
async def download_batch_excel(
    batch_id: str = Form(...),
    profile: str = Form("promon"),
    use_llm: str = Form("false"),
    _: None = Depends(enforce_pid_rate_limit),
):
    """Processa o batch e retorna um Excel consolidado em uma única aba."""
    validate_profile(profile)
    enable_llm = use_llm.lower() == "true"
    temp_paths, source_filenames = load_batch_manifest(batch_id)
    output_excel = os.path.join(settings.OUTPUT_DIR, f"{batch_id}_pid.xlsx")

    try:
        pid_service.extract_many_to_excel(
            temp_paths,
            output_excel,
            profile_name=profile,
            use_llm=enable_llm,
            source_filenames=source_filenames,
            single_sheet=True,
        )

        if not os.path.exists(output_excel):
            raise HTTPException(status_code=500, detail="Excel consolidado não foi gerado")

        return FileResponse(
            output_excel,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename="instrument_index_consolidado.xlsx",
            background=BackgroundTask(cleanup_batch, batch_id, [output_excel]),
        )
    except HTTPException:
        cleanup_batch(batch_id, [output_excel])
        raise
    except Exception as e:
        cleanup_batch(batch_id, [output_excel])
        raise HTTPException(status_code=500, detail=f"Erro na extração: {str(e)}")


@router.post("/extract/batch/preview")
async def preview_batch_pdf(
    batch_id: str = Form(...),
    profile: str = Form("promon"),
    use_llm: str = Form("false"),
    _: None = Depends(enforce_pid_rate_limit),
):
    """Processa o batch e retorna um PDF anotado consolidado."""
    validate_profile(profile)
    enable_llm = use_llm.lower() == "true"
    temp_paths, source_filenames = load_batch_manifest(batch_id)
    output_pdf = os.path.join(settings.OUTPUT_DIR, f"{batch_id}_annotated.pdf")

    try:
        pid_service.extract_many_to_annotated_pdf(
            temp_paths,
            output_pdf,
            profile_name=profile,
            use_llm=enable_llm,
            source_filenames=source_filenames,
        )

        if not os.path.exists(output_pdf):
            raise HTTPException(status_code=500, detail="PDF anotado consolidado não foi gerado")

        return FileResponse(
            output_pdf,
            media_type="application/pdf",
            filename="pids_anotados_consolidado.pdf",
            background=BackgroundTask(cleanup_batch, batch_id, [output_pdf]),
        )
    except HTTPException:
        cleanup_batch(batch_id, [output_pdf])
        raise
    except Exception as e:
        cleanup_batch(batch_id, [output_pdf])
        raise HTTPException(status_code=500, detail=f"Erro na extração: {str(e)}")


@router.post("/extract")
async def extract_instruments(
    file: UploadFile = File(...),
    profile: str = Form("promon"),
    use_llm: str = Form("false"),
    _: None = Depends(enforce_pid_rate_limit),
):
    """Extrai instrumentos de um P&ID (PDF vetorial) e retorna JSON."""
    validate_pdf(file)

    validate_profile(profile)

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
    request: Request,
    _: None = Depends(enforce_pid_rate_limit),
):
    """Extrai instrumentos e retorna um PDF anotado vetorial consolidado."""
    files, profile, enable_llm = await parse_pid_uploads(request)
    file_id = str(uuid.uuid4())
    output_pdf = os.path.join(settings.OUTPUT_DIR, f"{file_id}_annotated.pdf")
    temp_paths: list[str] = []

    try:
        temp_paths, source_filenames = await save_pid_uploads(files)

        pid_service.extract_many_to_annotated_pdf(
            temp_paths,
            output_pdf,
            profile_name=profile,
            use_llm=enable_llm,
            source_filenames=source_filenames,
        )

        if not os.path.exists(output_pdf):
            raise HTTPException(status_code=500, detail="PDF anotado não foi gerado")

        filename = (
            f"{os.path.splitext(files[0].filename or 'pid')[0]}_anotado.pdf"
            if len(files) == 1
            else "pids_anotados_consolidado.pdf"
        )

        return FileResponse(
            output_pdf,
            media_type="application/pdf",
            filename=filename,
            background=BackgroundTask(cleanup_files, [*temp_paths, output_pdf]),
        )

    except HTTPException:
        cleanup_files([*temp_paths, output_pdf])
        raise
    except Exception as e:
        cleanup_files([*temp_paths, output_pdf])
        raise HTTPException(status_code=500, detail=f"Erro na extração: {str(e)}")


@router.post("/extract/download")
async def download_excel(
    request: Request,
    _: None = Depends(enforce_pid_rate_limit),
):
    """Extrai instrumentos e retorna um Excel consolidado."""
    files, profile, enable_llm = await parse_pid_uploads(request)
    file_id = str(uuid.uuid4())
    output_excel = os.path.join(settings.OUTPUT_DIR, f"{file_id}_pid.xlsx")
    temp_paths: list[str] = []

    try:
        temp_paths, source_filenames = await save_pid_uploads(files)

        pid_service.extract_many_to_excel(
            temp_paths,
            output_excel,
            profile_name=profile,
            use_llm=enable_llm,
            source_filenames=source_filenames,
            single_sheet=len(temp_paths) > 1,
        )

        if not os.path.exists(output_excel):
            raise HTTPException(status_code=500, detail="Excel não foi gerado")

        filename = (
            f"{os.path.splitext(files[0].filename or 'pid')[0]}_instrument_index.xlsx"
            if len(files) == 1
            else "instrument_index_consolidado.xlsx"
        )

        return FileResponse(
            output_excel,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=filename,
            background=BackgroundTask(cleanup_files, [*temp_paths, output_excel]),
        )

    except HTTPException:
        cleanup_files([*temp_paths, output_excel])
        raise
    except Exception as e:
        cleanup_files([*temp_paths, output_excel])
        raise HTTPException(status_code=500, detail=f"Erro na extração: {str(e)}")
