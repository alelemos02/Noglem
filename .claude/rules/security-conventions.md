---
description: Security rules for the JulIA platform — API authentication, backend proxying
---

# Security Conventions

## Regra absoluta de arquitetura

**NUNCA chame os backends diretamente do browser. Sempre via API Route do Next.js.**

```
Browser → Next.js API Route → Backend (FastAPI)
```

Toda requisicao do Next.js para os backends deve incluir:
- `X-Internal-API-Key` — chave compartilhada validada no backend
- `X-User-Id` — Clerk User ID do usuario autenticado

Use sempre o helper `buildBackendAuthHeaders()` de `src/lib/backend.ts`.

## API Routes

- Nunca remova a validacao de auth das API Routes
- Normalize erros — nunca exponha stack traces do backend ao browser
- Retorne o status code original, normalize a mensagem de erro
- Sem `console.log` em producao — apenas `console.error` para erros reais

## Autenticacao

- Rotas protegidas: todo `/dashboard/*` requer autenticacao Clerk (`middleware.ts`)
- Rotas publicas: `/`, `/sign-in`, `/sign-up`, webhooks
- Backends FastAPI: sempre manter `require_internal_api_key` em todos os endpoints

## Segredos

- Variaveis de ambiente NUNCA commitadas no repositorio
- Frontend: `.env.local` (ignorado pelo git)
- Backends: configuracao no painel do Railway
- Nunca logar `INTERNAL_API_KEY`, `CLERK_SECRET_KEY` ou qualquer credencial
