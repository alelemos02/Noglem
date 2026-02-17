from fastapi import APIRouter, Depends, HTTPException

from app.models.schemas import TranslateRequest, TranslateResponse
from app.dependencies.rate_limit import enforce_translate_rate_limit
from app.dependencies.security import require_internal_api_key
from app.services.gemini_service import GeminiService

router = APIRouter(dependencies=[Depends(require_internal_api_key)])
gemini_service = GeminiService()


@router.post("/", response_model=TranslateResponse)
async def translate_text(
    request: TranslateRequest,
    _: None = Depends(enforce_translate_rate_limit),
):
    """
    Traduz texto usando Google Gemini.
    """
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Texto não pode estar vazio")

    try:
        result = await gemini_service.translate(
            text=request.text,
            source_lang=request.source_lang,
            target_lang=request.target_lang,
            improve_mode=request.improve_mode,
        )

        return TranslateResponse(
            original_text=request.text,
            translated_text=result.get("translated_text", ""),
            improved_text=result.get("improved_text"),
            detected_language=result.get("detected_language"),
            source_lang=request.source_lang,
            target_lang=request.target_lang,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro na tradução: {str(e)}")
