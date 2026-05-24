---
description: Scaffold a complete new JulIA tool end-to-end — registry, API route, dashboard page, and backend endpoint
---

Scaffold a complete new tool for the JulIA platform. Ask the user for:
1. Tool ID (kebab-case, e.g. `minha-ferramenta`)
2. Tool title (display name)
3. Tool description (one sentence)
4. Category: `documentacao` | `conhecimento` | `analise` | `instrumentacao`
5. Icon (Lucide icon name)
6. Which backend handles it: central (`backend/`) or new microservice

Then implement in this exact order:

**Step 1 — Tools Registry**
Add the tool to `src/lib/tools-registry.ts` with `status: 'coming_soon'`.

**Step 2 — API Route**
Create `src/app/api/<tool-id>/route.ts`:
- Import `buildBackendAuthHeaders` from `@/lib/backend`
- Validate auth headers (`X-Internal-API-Key`, `X-User-Id`)
- Proxy to backend with proper error handling
- Never expose stack traces — normalize error messages

**Step 3 — Dashboard Page**
Create `src/app/dashboard/<tool-id>/page.tsx`:
- Use only design system tokens (no raw Tailwind colors)
- Use `Card`, `Button`, `Badge`, `Input` from `@/components/ui/`
- Server component by default; `'use client'` only if needed
- Follow the layout pattern of existing tools

**Step 4 — Backend Endpoint**
Add to `backend/app/routers/<tool-id>.py` (or appropriate microservice):
- Keep `require_internal_api_key` on every endpoint
- Use Pydantic v2 for request/response schemas
- Add rate limiting if it involves AI calls

After scaffolding, update tool status to `'beta'` and do a git commit + push.
