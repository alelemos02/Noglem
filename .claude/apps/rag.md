---
name: rag
description: Conhecimento (RAG) — base de documentos técnicos com chat via IA generativa, coleções por usuário
metadata:
  type: project
---

# Conhecimento (RAG)

**Status:** Beta  
**Categoria:** Conhecimento

## O que faz

Sistema de RAG (Retrieval-Augmented Generation) baseado em coleções de documentos. Cada usuário cria coleções (ex: "Manuais de Engenharia"), faz upload de PDFs, e pode conversar com os documentos via chat com streaming.

## Arquivos principais

- Frontend (lista de coleções): `src/app/dashboard/rag/page.tsx`
- Frontend (chat da coleção): `src/app/dashboard/rag/[collectionId]/page.tsx`
- API Route (proxy catch-all): `src/app/api/rag/[...path]/route.ts`
- Backend: RAG microservice (`services/rag-backend/`, porta 8002)

## Fluxo de dados

```
Browser → /api/rag/* → RAG microservice (RAG_API_URL, porta 8002)
```

A API Route é um proxy catch-all que repassa todos os métodos (GET, POST, PUT, DELETE) para o microserviço RAG, preservando headers e body.

## Dependências de backend

- RAG microservice separado (Railway, `services/rag-backend/`)
- Variável de ambiente: `RAG_API_URL` (default: `http://localhost:8002`)
- Upload de PDFs: até 50MB (configurado na API Route com `maxContentLength`)

## Recursos suportados pelo proxy

- **SSE streaming** para respostas de chat (passado diretamente ao browser)
- **PDF downloads** (preserva Content-Disposition)
- **Multipart uploads** (PDFs para as coleções)

## Endpoints principais (via proxy)

```
GET  /api/rag/collections          → lista coleções do usuário
POST /api/rag/collections          → cria nova coleção
DEL  /api/rag/collections/{id}     → exclui coleção + documentos
POST /api/rag/collections/{id}/documents  → upload de PDF
POST /api/rag/collections/{id}/chat       → chat (SSE streaming)
```

## Modelo de dados

```ts
interface Collection {
  id: string;
  name: string;
  created_at: string;
  documents: unknown[];
}
```

## Redesign v3 (2026-07)

UI migrada para o design system v3 "instrumento de precisão" (ver `.claude/rules/design-system-conventions.md`):
- Header via `<PageHeader tool="{id}">` — nome/descrição/badge vêm do `tools-registry.ts`
- Upload via `<Dropzone>` compartilhado; loading via `<Spinner>`/`Button loading`
- Erros persistentes em `<Alert>`; sucesso/erro transiente via `toast` (sonner); ações destrutivas via `useConfirm()`
- Tokens novos: canvas/surface-1..3, edge, fg-*, accent azure — zero cores Tailwind literais
- Endpoints e lógica de negócio inalterados
