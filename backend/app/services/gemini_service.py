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
        self, text: str, source_lang: str = "auto", target_lang: str = "en", improve_mode: bool = False
    ) -> dict:
        """
        Traduz texto usando Google Gemini com lógica avançada (Improve Mode).
        """
        if not self.model:
            raise ValueError("Google API Key não configurada")

        # Prompt construction idêntico ao original
        prompt = f"""
        You are an expert linguist, translator, and copy editor. 
        Your task is to process the following text provided by the user.
    
        Input Text:
        "{text}"
    
        Target Language: {target_lang}
    
        Instructions:
        1. Identify the language of the 'Input Text'.
        2. { "If 'Improve Mode' is active: strict instructions to first rewriting the 'Input Text' in its ORIGINAL language to be more fluid, professional, grammatically correct, and easy to read. This is the 'improved_text'. Then, translate this 'improved_text' into the 'Target Language'. " if improve_mode else "Translate the 'Input Text' directly into the 'Target Language'. If 'Improve Mode' is NOT active, 'improved_text' should be null or empty string." }
        3. Return the result in valid JSON format.
    
        Required JSON Structure:
        {{
            "detected_language": "Name of the source language (e.g., Portuguese, English)",
            "improved_text": "The improved version of the original text (only if improve_mode is True, otherwise null)",
            "translated_text": "The final translation in {target_lang}"
        }}
        """

        try:
            response = self.model.generate_content(prompt)
            # Parse the JSON response
            import json
            
            # Limpeza básica caso o modelo retorne markdown ```json
            clean_text = response.text.strip()
            if clean_text.startswith("```json"):
                clean_text = clean_text[7:]
            if clean_text.endswith("```"):
                clean_text = clean_text[:-3]
                
            result = json.loads(clean_text)
            
            # Handle cases where the model returns a list (lógica do original)
            if isinstance(result, list):
                if len(result) > 0 and isinstance(result[0], dict):
                    result = result[0]
                else:
                    found = False
                    for item in result:
                        if isinstance(item, dict):
                            result = item
                            found = True
                            break
                    if not found:
                         # Fallback simples
                        return {
                            "detected_language": "Unknown",
                            "improved_text": None,
                            "translated_text": str(result)
                        }
            
            return result

        except Exception as e:
            print(f"Error processing text: {e}")
            raise e
