---
description: Deploy conventions for this workspace — commit and push rules after completing any change
---

# Deploy Conventions

**REGRA OBRIGATORIA:** Sempre que finalizar uma alteracao (feature, fix, refactor), faca `git commit` e `git push origin main` automaticamente — nunca espere o usuario pedir.

## Deploy automatico

- **Frontend (enghub-v2):** Vercel faz deploy automatico via push no GitHub `alelemos02/Noglem`
- **Backend Central:** Railway faz deploy automatico do diretorio `backend/`
- **RAG Microservice:** Railway faz deploy automatico do diretorio `services/rag-backend/`
- **PATEC Microservice:** Railway faz deploy automatico do diretorio `services/patec-backend/`

## Regras de commit

1. Sempre use mensagens descritivas (feat, fix, refactor, chore)
2. Nunca use `--no-verify`
3. Sempre inclua `Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>` no commit
4. Faca commit apenas dos arquivos alterados — nunca `git add .` indiscriminadamente
5. Nao faca commit de `.env`, `.env.local` ou arquivos com credenciais

## Verificacao pos-deploy

Para verificar logs de producao: painel do Railway (backends) ou Vercel (frontend).
