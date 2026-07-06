---
name: pdf-converter
description: Agente de Documento — converte PDF para Word ou formata .docx existente
metadata:
  type: project
---

# Agente de Documento (PDF para Word)

**Status:** Beta  
**Categoria:** Documentação  
**Nome no registry:** `pdf-converter` / UI: "Agente de Documento"

## O que faz

Dois modos na mesma tela, alternáveis via toggle:

1. **Converter PDF**: converte um PDF para documento Word editável (`.docx`)
2. **Formatar Word**: recebe um `.docx` e aplica formatação/limpeza

## Arquivos principais

- Frontend: `src/app/dashboard/pdf-converter/page.tsx`
- API Route (convert): `src/app/api/pdf/convert/route.ts`
- API Route (format): `src/app/api/pdf/format/route.ts`
- API Route (download): `src/app/api/pdf/download/[fileId]/route.ts`
- Backend services: `backend/app/services/pdf_convert_service.py`, `backend/app/services/word_format_service.py`

## Fluxo de dados

```
Modo convert: Browser (PDF) → POST /api/pdf/convert → Backend → pdf_convert_service → retorna { download_url, ... }
Modo format:  Browser (.docx) → POST /api/pdf/format → Backend → word_format_service → retorna { download_url, ... }
Download:     Browser → GET {download_url} → Backend → arquivo binário
```

## Dependências de backend

- Backend Central (porta 8000, Railway)
- O backend gera um arquivo temporário e retorna `download_url` apontando para `/api/pdf/download/[fileId]`

## Resposta dos endpoints de processamento

```json
{
  "filename": "documento_convertido.docx",
  "original_size": 102400,
  "converted_size": 85000,   // modo convert
  "formatted_size": 80000,   // modo format
  "download_url": "/api/pdf/download/abc-123"
}
```

## Quirks

- O frontend unifica `converted_size` e `formatted_size` sob `final_size` na interface
- Aceitar apenas `.pdf` no modo convert, apenas `.docx` no modo format — validação no frontend e backend

## Redesign v3 (2026-07)

UI migrada para o design system v3 "instrumento de precisão" (ver `.claude/rules/design-system-conventions.md`):
- Header via `<PageHeader tool="{id}">` — nome/descrição/badge vêm do `tools-registry.ts`
- Upload via `<Dropzone>` compartilhado; loading via `<Spinner>`/`Button loading`
- Erros persistentes em `<Alert>`; sucesso/erro transiente via `toast` (sonner); ações destrutivas via `useConfirm()`
- Tokens novos: canvas/surface-1..3, edge, fg-*, accent azure — zero cores Tailwind literais
- Endpoints e lógica de negócio inalterados
