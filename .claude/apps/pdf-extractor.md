---
name: pdf-extractor
description: Extrator de Tabelas — extrai tabelas de PDFs e exporta para Excel
metadata:
  type: project
---

# Extrator de Tabelas

**Status:** Beta  
**Categoria:** Documentação

## O que faz

Recebe um PDF, detecta todas as tabelas presentes e retorna preview estruturado (headers + rows por página). Permite download do resultado como arquivo `.xlsx`.

## Arquivos principais

- Frontend: `src/app/dashboard/pdf-extractor/page.tsx`
- API Route (preview): `src/app/api/pdf/extract/route.ts`
- API Route (download): `src/app/api/pdf/extract/download/route.ts`
- Backend service: `backend/app/services/pdf_extract_service.py`

## Fluxo de dados

```
Browser (FormData + PDF) → POST /api/pdf/extract → Backend Central → pdf_extract_service → resposta JSON
Browser (FormData + PDF) → POST /api/pdf/extract/download → Backend Central → pdf_extract_service → arquivo .xlsx
```

## Dependências de backend

- Backend Central (porta 8000, Railway)
- Rate limiting: `enforce_pdf_rate_limit`
- Biblioteca de extração: pdfplumber (inferido do serviço)

## Resposta de preview

```json
{
  "filename": "...",
  "total_pages": 10,
  "tables_found": 3,
  "tables": [
    { "page": 1, "table_index": 0, "headers": [...], "rows": [[...]] }
  ]
}
```

## Comportamento esperado

- PDFs sem tabelas retornam `tables_found: 0` sem erro
- O download re-envia o PDF para o backend (não cacheia o resultado do preview)
- Aceita apenas arquivos `.pdf`
