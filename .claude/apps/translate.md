---
name: translate
description: Tradutor AI — traduz textos técnicos usando Google Gemini, com modo de melhoria de texto
metadata:
  type: project
---

# Tradutor AI

**Status:** Live  
**Categoria:** Documentação

## O que faz

Tradução de texto livre usando Google Gemini. Suporta detecção automática de idioma e modo "melhorar texto" que reescreve o original para maior fluidez antes de traduzir. Idiomas: PT, EN, ES, FR, DE, IT, ZH, JA, RU, AR.

## Arquivos principais

- Frontend: `src/app/dashboard/translate/page.tsx`
- API Route: `src/app/api/translate/route.ts`
- Backend router: `backend/app/routers/translate.py`
- Serviço LLM: `backend/app/services/gemini_service.py`

## Fluxo de dados

```
Browser → POST /api/translate → Backend Central (/api/translate/) → GeminiService → Google Gemini API
```

## Dependências de backend

- Backend Central (porta 8000, Railway)
- Google Gemini API (`GEMINI_API_KEY`)
- Rate limiting: `enforce_translate_rate_limit` (backend)

## Decisões de arquitetura

- Chama o backend central, não o Gemini diretamente do browser
- `improve_mode: true` faz o Gemini reescrever o original antes de traduzir, retornando `improved_text` além de `translated_text`
- `source_lang: "auto"` → Gemini detecta e retorna `detected_language`

## Campos da resposta

```json
{
  "translated_text": "...",
  "improved_text": "...",      // só quando improve_mode=true
  "detected_language": "...",  // só quando source_lang="auto"
  "original_text": "...",
  "source_lang": "...",
  "target_lang": "..."
}
```
