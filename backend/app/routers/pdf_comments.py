import tempfile
from dataclasses import asdict
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.dependencies.security import require_internal_api_key
from app.dependencies.rate_limit import enforce_pdf_rate_limit
from app.services.pdf_comments_service import analyze_batch, extract_from_pdf, generate_excel

router = APIRouter(dependencies=[Depends(require_internal_api_key)])

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB


@router.post("/process")
async def process_pdfs(
    files: list[UploadFile] = File(...),
    _: None = Depends(enforce_pdf_rate_limit),
):
    if not files:
        raise HTTPException(status_code=400, detail="Nenhum arquivo enviado.")

    results = []
    tmp_dir = Path(tempfile.mkdtemp())

    try:
        for upload in files:
            filename = upload.filename or "arquivo.pdf"
            content = await upload.read()

            if len(content) > MAX_FILE_SIZE:
                results.append({
                    "filename": filename,
                    "annotations": [],
                    "error": f"Arquivo muito grande ({len(content) // 1024 // 1024} MB). Máximo: 100 MB.",
                    "page_count": 0,
                })
                continue

            if not filename.lower().endswith(".pdf"):
                results.append({
                    "filename": filename,
                    "annotations": [],
                    "error": "Tipo de arquivo inválido. Apenas PDFs são aceitos.",
                    "page_count": 0,
                })
                continue

            tmp_path = tmp_dir / filename
            tmp_path.write_bytes(content)

            result = extract_from_pdf(tmp_path)
            results.append(asdict(result))

            tmp_path.unlink(missing_ok=True)
    finally:
        try:
            tmp_dir.rmdir()
        except OSError:
            pass

    # Collect all annotations across files and run AI analysis in parallel
    all_annotations = [a for r in results if not r.get("error") for a in r.get("annotations", [])]
    analyze_batch(all_annotations)

    total_annotations = sum(
        len(r.get("annotations", [])) for r in results if not r.get("error")
    )

    return {
        "results": results,
        "total_annotations": total_annotations,
        "total_files": len(results),
    }


@router.post("/export")
async def export_excel(
    payload: dict,
    _: None = Depends(enforce_pdf_rate_limit),
):
    results = payload.get("results", [])
    if not results:
        raise HTTPException(status_code=400, detail="Nenhum resultado para exportar.")

    buf = generate_excel(results)

    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="comentarios.xlsx"'},
    )
