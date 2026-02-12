import google.generativeai as genai
from app.config import settings

# Mapeamento de códigos de idioma
LANGUAGE_NAMES = {
    "pt": "Portuguese",
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "ru": "Russian",
    "ar": "Arabic",
    "auto": "auto-detect",
}


class GeminiService:
    def __init__(self):
        if settings.GOOGLE_API_KEY:
            genai.configure(api_key=settings.GOOGLE_API_KEY)
            self.model = genai.GenerativeModel("gemini-2.0-flash")
        else:
            self.model = None

    async def translate(
        self, text: str, source_lang: str = "auto", target_lang: str = "en"
    ) -> str:
        """
        Traduz texto usando Google Gemini.
        """
        if not self.model:
            raise ValueError("Google API Key não configurada")

        source_name = LANGUAGE_NAMES.get(source_lang, source_lang)
        target_name = LANGUAGE_NAMES.get(target_lang, target_lang)

        if source_lang == "auto":
            prompt = f"""Translate the following text to {target_name}.
Only respond with the translation, no explanations or additional text.

Text to translate:
{text}"""
        else:
            prompt = f"""Translate the following text from {source_name} to {target_name}.
Only respond with the translation, no explanations or additional text.

Text to translate:
{text}"""

        response = self.model.generate_content(prompt)
        return response.text.strip()
