# MarkTrace — Extração de Comentários PDF

## Visão geral

Ferramenta que extrai automaticamente anotações de revisão de PDFs (Text, FreeText, Highlight,
Underline, StrikeOut, Squiggly) e exporta para Excel formatado. Filtra campos de template CAD
(AutoCAD/Revit) via flag Locked (bit 7) para retornar apenas comentários humanos.

## Arquivos

| Caminho | Função |
|---------|--------|
| `src/app/dashboard/pdf-comments/page.tsx` | Página frontend — upload multi-arquivo, preview, export |
| `src/app/api/pdf-comments/route.ts` | API Route proxy → POST `/api/pdf-comments/process` |
| `src/app/api/pdf-comments/export/route.ts` | API Route proxy → POST `/api/pdf-comments/export` |
| `backend/app/routers/pdf_comments.py` | Router FastAPI com endpoints `/process` e `/export` |
| `backend/app/services/pdf_comments_service.py` | Lógica de extração (PyMuPDF) e geração Excel (openpyxl) |

## Endpoints backend

- `POST /api/pdf-comments/process` — recebe `multipart/form-data` com campo `files[]`, retorna JSON:
  ```json
  { "results": [...], "total_annotations": N, "total_files": N }
  ```
- `POST /api/pdf-comments/export` — recebe JSON `{ "results": [...] }`, retorna `.xlsx` via StreamingResponse

## Dependências backend

`PyMuPDF` (já presente em `backend/requirements.txt`) e `openpyxl` (já presente). Sem dependências novas.

## Quirks

- Anotações FreeText com flag Locked (128) são campos de carimbo/legenda do AutoCAD — descartadas.
- Apenas tipos `COMMENT_TYPES` são aceitos; anotações gráficas (Line, Polygon, Stamp) são ignoradas.
- Limite: 100 MB por arquivo, validado no backend e comunicado ao frontend via campo `error` no resultado.
- Rate limit reutiliza `enforce_pdf_rate_limit` (5 req/min por usuário).

## Redesign v3 (2026-07)

UI migrada para o design system v3 "instrumento de precisão" (ver `.claude/rules/design-system-conventions.md`):
- Header via `<PageHeader tool="{id}">` — nome/descrição/badge vêm do `tools-registry.ts`
- Upload via `<Dropzone>` compartilhado; loading via `<Spinner>`/`Button loading`
- Erros persistentes em `<Alert>`; sucesso/erro transiente via `toast` (sonner); ações destrutivas via `useConfirm()`
- Tokens novos: canvas/surface-1..3, edge, fg-*, accent azure — zero cores Tailwind literais
- Endpoints e lógica de negócio inalterados
