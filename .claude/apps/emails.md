---
name: emails
description: Email RAG — consulta de emails Microsoft 365 via IA (coming soon, infraestrutura backend já existe)
metadata:
  type: project
---

# Email RAG

**Status:** Coming Soon  
**Categoria:** Conhecimento

## O que vai fazer

Integração com Microsoft 365 via OAuth para sincronizar emails e consultá-los com IA generativa (RAG sobre emails).

## Estado atual

A infraestrutura de backend já existe mas a ferramenta não está disponível no produto ainda.

## Arquivos existentes

- Frontend placeholder: `src/app/dashboard/emails/page.tsx`
- API Routes: `src/app/api/email/[...path]/route.ts`, `src/app/api/email/callback/route.ts`
- Backend services (já implementados):
  - `backend/app/services/email/microsoft_graph.py` — integração Microsoft Graph API
  - `backend/app/services/email/email_sync_service.py` — sincronização de emails
  - `backend/app/services/email/email_vector_store.py` — armazenamento vetorial
  - `backend/app/services/email/email_rag_service.py` — consulta RAG sobre emails
  - `backend/app/services/email/local_embedding_service.py` — embeddings locais
- Backend router: `backend/app/routers/email.py`

## OAuth Microsoft 365

- Callback em `/api/email/callback` para tratar o redirect OAuth do Azure AD
- Requer configuração de `MICROSOFT_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET`, `MICROSOFT_TENANT_ID` no Railway

## Redesign v3 (2026-07)

UI migrada para o design system v3 "instrumento de precisão" (ver `.claude/rules/design-system-conventions.md`):
- Header via `<PageHeader tool="{id}">` — nome/descrição/badge vêm do `tools-registry.ts`
- Upload via `<Dropzone>` compartilhado; loading via `<Spinner>`/`Button loading`
- Erros persistentes em `<Alert>`; sucesso/erro transiente via `toast` (sonner); ações destrutivas via `useConfirm()`
- Tokens novos: canvas/surface-1..3, edge, fg-*, accent azure — zero cores Tailwind literais
- Endpoints e lógica de negócio inalterados
