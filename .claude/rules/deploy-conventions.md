---
description: Deploy conventions for this workspace — commit rules and how deploy works (manual via /deploy skill)
---

# Deploy Conventions

**Deploy NAO e automatico.** Terminar uma alteracao (feature, fix, refactor) **nao**
dispara deploy nem push — apenas finalize o trabalho e pare. O deploy so acontece
quando o usuario chamar explicitamente a skill **`/deploy`** (`.claude/skills/deploy/`),
que cuida de bump de versao, commit, push e validacao ao vivo.

## Mecanismo (push-to-deploy)

Quando a skill `/deploy` der push em `origin main`, o deploy acontece automaticamente:

- **Frontend (enghub-v2):** Vercel faz deploy via push no GitHub `alelemos02/Noglem`
- **Backend Central:** Railway faz deploy do diretorio `backend/`
- **RAG Microservice:** Railway faz deploy do diretorio `services/rag-backend/`
- **PATEC Microservice:** Railway faz deploy do diretorio `services/patec-backend/`

## Regras de commit

1. Sempre use mensagens descritivas em Conventional Commits (feat, fix, refactor, chore)
2. Nunca use `--no-verify`
3. Sempre inclua `Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>` no commit
4. Faca commit apenas dos arquivos alterados — nunca `git add .` indiscriminadamente
5. Nao faca commit de `.env`, `.env.local` ou arquivos com credenciais

## Verificacao pos-deploy

Para verificar logs de producao: painel do Railway (backends) ou Vercel (frontend).
