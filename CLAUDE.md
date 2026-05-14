# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Leia **AGENTS.md** para todas as convencoes do projeto: arquitetura, design system, como alterar/adicionar ferramentas, stack e variaveis de ambiente.

O que esta abaixo e especifico do Claude Code e nao se aplica a outros agentes.

---

## Comandos de desenvolvimento

### Frontend (Next.js)
```bash
npm run dev          # Dev server em localhost:3000
npm run build        # Build de producao
npm run lint         # ESLint
npx tsc --noEmit     # Type-check sem emitir arquivos
```

### Backend Central (FastAPI, porta 8000)
```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

### PATEC Microservice (FastAPI, porta 8001)
```bash
cd services/patec-backend
python run.py
# Migrations: alembic upgrade head
# Nova migration: alembic revision --autogenerate -m "descricao"
```

### RAG / Conhecimento Microservice (FastAPI, porta 8002)
```bash
cd services/rag-backend
uvicorn app.main:app --reload --port 8002
```

---

## Comportamento esperado

- Leia os arquivos relevantes antes de propor qualquer mudanca
- Altere apenas o que foi pedido — sem refatoracoes nao solicitadas
- Use `Edit` para modificar arquivos existentes, `Write` apenas para arquivos novos
- Nao crie arquivos `.md` de documentacao sem instrucao explicita
- Se o escopo do pedido for ambiguo, pergunte antes de codar

## Ferramentas do Claude Code

- Use `TodoWrite` para tarefas com mais de 3 passos
- Marque cada tarefa como concluida imediatamente apos finaliza-la
- Prefira chamadas de ferramentas em paralelo quando nao ha dependencia entre elas

## Ambiente de producao

**A aplicacao roda em `www.noglem.com.br` — nao localmente.**

- **Frontend**: Vercel (deploy automatico via push no GitHub `alelemos02/Noglem`)
- **Backend central**: Railway (diretorio raiz: `backend/`)
- **RAG microservice**: Railway (diretorio raiz: `services/rag-backend/`)
- **PATEC microservice**: Railway (diretorio raiz: `services/patec-backend/`)

**Fluxo de deploy:**
- **DEPLOY / GITHUB:** Toda alteracao finalizada deve sempre ser comitada (`git commit`) e subida para o GitHub (`git push origin main`), para garantir que reflita no site. A Vercel e o Railway fazem o deploy automaticamente.
- **REGRA OBRIGATORIA:** Sempre que finalizar uma alteracao (feature, fix, refactor), faca `git commit` e `git push origin main` automaticamente — nunca espere o usuario pedir.

Correcoes de bug devem seguir a mesma regra: devem ser commitadas e enviadas ao GitHub — nao basta rodar localmente.

Para verificar logs de producao: acesse o painel do Railway ou Vercel.

---

## gstack

- Use the `/browse` skill from gstack for **all web browsing** — never use `mcp__claude-in-chrome__*` tools directly.
- Available gstack skills: `/office-hours`, `/plan-ceo-review`, `/plan-eng-review`, `/plan-design-review`, `/design-consultation`, `/review`, `/ship`, `/land-and-deploy`, `/canary`, `/benchmark`, `/browse`, `/qa`, `/qa-only`, `/design-review`, `/setup-browser-cookies`, `/setup-deploy`, `/retro`, `/investigate`, `/document-release`, `/codex`, `/cso`, `/autoplan`, `/careful`, `/freeze`, `/guard`, `/unfreeze`, `/gstack-upgrade`.

---

## Versionamento do site

A versao do site e exibida no sidebar em `src/components/layout/sidebar.tsx`.
**REGRA OBRIGATORIA:** A versao DEVE ser atualizada a cada deploy.

Formato: `VX.Y.Z`

| Segmento | Quando incrementar |
|----------|-------------------|
| **X** (ex: v**2**.0.3) | Impacto muito grande: redesign de layout, mudancas brutas de arquitetura |
| **Y** (ex: v2.**0**.3) | Inclusao de nova ferramenta no dashboard |
| **Z** (ex: v2.0.**3**) | Atualizacoes menores: melhorias em ferramentas existentes, correcoes, ajustes |

Versao atual: **v2.0.3**

---

## Atualizacao deste arquivo

`CLAUDE.md` e `AGENTS.md` **nao sao atualizados automaticamente**.
Peca explicitamente quando quiser atualizar: *"atualiza o CLAUDE.md / AGENTS.md com isso"*.

## Contexto por ferramenta (.claude/apps/)

Cada ferramenta do dashboard tem um arquivo de contexto em `.claude/apps/{tool-id}.md`.

**REGRA OBRIGATORIA:** Sempre que finalizar uma alteracao em qualquer ferramenta (frontend, API Route ou backend), atualize o arquivo `.claude/apps/` correspondente para refletir a mudanca — arquitetura, endpoints, quirks, dependencias. Faca isso antes do commit.

## Skill routing

When the user's request matches an available skill, invoke it via the Skill tool. When in doubt, invoke the skill.

Key routing rules:
- Product ideas/brainstorming → invoke /office-hours
- Strategy/scope → invoke /plan-ceo-review
- Architecture → invoke /plan-eng-review
- Design system/plan review → invoke /design-consultation or /plan-design-review
- Full review pipeline → invoke /autoplan
- Bugs/errors → invoke /investigate
- QA/testing site behavior → invoke /qa or /qa-only
- Code review/diff check → invoke /review
- Visual polish → invoke /design-review
- Ship/deploy/PR → invoke /ship or /land-and-deploy
- Save progress → invoke /context-save
- Resume context → invoke /context-restore
- PATEC analysis review/optimization → invoke /patec-otimizar
