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
- Split client-side: `src/lib/pdf-split.ts` (pdf-lib)
- API Route (preview): `src/app/api/pdf/extract/route.ts`
- API Route (download Excel a partir de JSON): `src/app/api/pdf/extract/excel/route.ts`
- API Route legada (download reenviando o PDF): `src/app/api/pdf/extract/download/route.ts` (não usada mais pelo frontend)
- Backend service: `backend/app/services/pdf_extract_service.py`

## Fluxo de dados

```
# Arquivo <= 4 MB
Browser (FormData + PDF) → POST /api/pdf/extract → Backend Central → pdf_extract_service.extract_tables → JSON

# Download Excel (qualquer tamanho — usa as tabelas já extraídas)
Browser (JSON: {filename, tables}) → POST /api/pdf/extract/excel → Backend → pdf_extract_service.tables_to_excel → .xlsx
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

## Limite de arquivo e auto-split

O Vercel rejeita request com corpo > ~4,5 MB na borda (HTTP 413 `FUNCTION_PAYLOAD_TOO_LARGE`), antes de a função rodar. Para contornar **sem o usuário precisar dividir o PDF na mão**:

- `SIZE_LIMIT = 4 MB` em `page.tsx`.
- Se o arquivo passa do limite, `splitPdfBySize` (`src/lib/pdf-split.ts`, via **pdf-lib**) divide o PDF **no navegador** em partes contíguas, cada uma < ~3,4 MB (margem de 85% para o overhead do multipart). Busca binária pelo maior número de páginas que cabe por parte.
- Cada parte é enviada separadamente para `/api/pdf/extract`; os resultados são consolidados, **remapeando o número de página** para o documento original (`page + (startPage - 1)`).
- Barra de progresso mostra "Processando parte X de N".
- Edge case: se uma única página sozinha passa do limite (ex.: scan em altíssima resolução), lança `PageTooLargeError` com mensagem pedindo para comprimir — não dá para dividir por página.
- O download do Excel **não reenvia o PDF**: manda as tabelas já extraídas (JSON) para `/api/pdf/extract/excel`, que reusa `tables_to_excel` no backend. Por isso funciona mesmo para PDFs grandes.
- **Rate limit:** como o split dispara N requests por extração, o backend usa `RATE_LIMIT_PDF_PER_MIN = 60` (era 5 — 5 não comportava nem um PDF dividido em 6+ partes). O frontend espaça os envios em 300ms e faz retry com backoff (1,5s × tentativa, até 4) em 429.

Mesmo limite/quirk da ferramenta pid-extractor (que ainda bloqueia em vez de auto-dividir).
