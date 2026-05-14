---
name: pid-extractor
description: Extrator de P&ID — extrai instrumentos de P&IDs vetoriais, gera Instrument Index (Excel e PDF anotado)
metadata:
  type: project
---

# Extrator de P&ID

**Status:** Beta  
**Categoria:** Instrumentação

## O que faz

Processa P&IDs vetoriais em PDF e extrai automaticamente: instrumentos (tag, tipo ISA, símbolo, classificação, loop, área), loops de controle, números de linha e notas do desenho. Exporta Instrument Index como Excel ou PDF anotado com os instrumentos destacados. Suporta múltiplos arquivos com consolidação em batch.

## Arquivos principais

### Frontend
- Página: `src/app/dashboard/pid-extractor/page.tsx`

### API Routes
- Extração (preview JSON): `src/app/api/pid/extract/route.ts`
- Download Excel (single): `src/app/api/pid/extract/download/route.ts`
- Download PDF anotado (single): `src/app/api/pid/extract/preview/route.ts`
- Batch start: `src/app/api/pid/extract/batch/start/route.ts`
- Batch upload: `src/app/api/pid/extract/batch/upload/route.ts`
- Batch download Excel: `src/app/api/pid/extract/batch/download/route.ts`
- Batch download PDF: `src/app/api/pid/extract/batch/preview/route.ts`

### Backend
- Router: `backend/app/routers/pid.py`
- Orquestrador: `backend/app/services/pid_extract_service.py`
- Pipeline (em `backend/app/services/pid/core/`):
  - `ingestion.py` — leitura do PDF vetorial
  - `text_extraction.py` — extração de texto
  - `symbol_detector.py` — detecção de símbolos ISA
  - `tag_detector.py` — detecção de tags de instrumentos
  - `spatial_engine.py` — associação espacial tag↔símbolo
  - `hierarchy.py` — montagem da hierarquia loop/área
  - `llm_validator.py` — validação opcional via LLM
  - `cross_sheet.py` — correlação entre folhas
  - `title_block.py` — extração do carimbo
  - `notes_parser.py` — parsing de notas do desenho
- Exportação (`backend/app/services/pid/export/`):
  - `excel_export.py`, `pdf_export.py`, `csv_export.py`
- Config de perfis: `backend/app/services/pid/config/tag_profiles.yaml`
- Modelo: `backend/app/services/pid/models/instrument.py`

## Fluxo (single file)

```
Browser → POST /api/pid/extract (FormData) → Backend → PidExtractService → JSON com instrumentos
Browser → POST /api/pid/extract/download (FormData) → Backend → .xlsx
Browser → POST /api/pid/extract/preview (FormData) → Backend → .pdf anotado
```

## Fluxo (batch multi-arquivo)

```
1. POST /api/pid/extract/batch/start → batch_id
2. Para cada arquivo: POST /api/pid/extract/batch/upload (batch_id + file)
3. POST /api/pid/extract/batch/download ou /batch/preview (batch_id + profile) → arquivo consolidado
```

## Parâmetros de extração

```
profile: "promon" | "technip"   // formato das tags (definido em tag_profiles.yaml)
use_llm: "true" | "false"       // validação LLM (desligado por padrão)
```

## Limite de arquivo

**4 MB por arquivo** — limitação hard do Vercel por request. P&IDs maiores devem ser divididos antes do upload. O frontend valida e bloqueia arquivos acima do limite antes de enviar.

## Campos do InstrumentData

```ts
{ tag, isa_type, description, symbol, classification, is_physical,
  furnished_by_package, area, tag_number, qualifier, equipment,
  loop_id, line_number, sheet, confidence }
```

## Quirks conhecidos

- Apenas P&IDs vetoriais funcionam — P&IDs escaneados (raster) não são suportados
- O retry automático trata erro 429 (rate limit) com backoff de 1.5s × tentativa, até 3 tentativas
- Multi-arquivo: processados sequencialmente com delay de 400ms entre cada um para evitar rate limit
- Perfil ativo no frontend: `promon` (hardcoded em `buildFormData`)
