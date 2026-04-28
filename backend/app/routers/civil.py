import os
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response

from app.config import settings
from app.dependencies.rate_limit import enforce_pdf_rate_limit
from app.dependencies.security import require_internal_api_key
from app.services.civil.calculator import calcular_todos
from app.services.civil.excel_generator import gerar_excel_bytes
from app.services.civil.models import ConfigProjeto, ResultadoQuantitativo
from app.services.civil.pdf_extractor import ExtractionError, PDFExtractor
from app.services.civil.validator import validar_calculos, validar_geometria

router = APIRouter(dependencies=[Depends(require_internal_api_key)])

_CONFIG_PATH = Path(__file__).parent.parent / "services" / "civil" / "config" / "defaults.json"


async def _extrair_resultado(file: UploadFile) -> tuple[ResultadoQuantitativo, str]:
    """Valida, salva, processa e retorna (resultado, filename_base). Lança HTTPException em erros."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Nome do arquivo não fornecido")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext != ".pdf":
        raise HTTPException(status_code=400, detail="Apenas arquivos PDF são aceitos")

    file_id = str(uuid.uuid4())
    temp_path = Path(settings.UPLOAD_DIR) / f"civil_{file_id}.pdf"

    try:
        content = await file.read()
        temp_path.write_bytes(content)

        config = ConfigProjeto.from_file(_CONFIG_PATH)
        extractor = PDFExtractor(config)

        try:
            geo = extractor.extract(temp_path)
        except ExtractionError as exc:
            raise HTTPException(status_code=422, detail=str(exc))

        missing = extractor.find_missing_fields(geo)
        if missing:
            raise HTTPException(
                status_code=422,
                detail=f"Campos não encontrados no PDF: {', '.join(missing)}. "
                       "Verifique se o arquivo é um desenho de fundação de tanque Petrobras.",
            )

        resultado = calcular_todos(geo, config)

        erros = validar_geometria(geo) + validar_calculos(resultado, config.tolerancia_validacao)
        if erros:
            raise HTTPException(
                status_code=422,
                detail=f"Validação falhou: {'; '.join(erros[:3])}",
            )

        nome_base = geo.documento.replace("/", "-").replace("\\", "-")
        return resultado, nome_base

    finally:
        if temp_path.exists():
            temp_path.unlink()


@router.post("/preview")
async def preview_pdf(
    file: UploadFile = File(...),
    _: None = Depends(enforce_pdf_rate_limit),
) -> dict[str, Any]:
    resultado, _ = await _extrair_resultado(file)
    geo = resultado.geometria
    return {
        "documento": geo.documento,
        "tanques": geo.tanques,
        "total_tanques": geo.total_tanques,
        "fonte_extracao": geo.fonte_extracao,
        "itens": [item.model_dump() for item in geo.itens],
        "total_1_tanque": resultado.total_1_tanque,
        "total_geral": resultado.total_geral,
    }


@router.post("/processar")
async def processar_pdf(
    file: UploadFile = File(...),
    _: None = Depends(enforce_pdf_rate_limit),
):
    resultado, nome_base = await _extrair_resultado(file)
    xlsx_bytes = gerar_excel_bytes([resultado])
    filename = f"quantitativo_{nome_base}.xlsx"

    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
