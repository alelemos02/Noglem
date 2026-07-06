---
name: deploy
description: >-
  Deploy MANUAL do enghub-v2 (noglem). Use SOMENTE quando o usuario pedir
  explicitamente: "deploy", "shippar", "subir pra producao", "publica isso",
  "/deploy". NUNCA execute deploy automaticamente ao terminar uma tarefa —
  espere o usuario chamar esta skill. Faz bump de versao obrigatorio (tabela
  semver X.Y.Z), commit em Conventional Commits, push pra origin main (que
  dispara o deploy automatico da Vercel/Railway) e valida AO VIVO em
  www.noglem.com.br antes de declarar sucesso.
---

# Deploy — enghub-v2 (noglem)

**Regra de ouro: deploy NUNCA e automatico.** Só rode este fluxo quando o
usuário chamar a skill explicitamente. Terminar uma feature/fix/refactor **não**
é gatilho de deploy — apenas finalize o trabalho e pare.

A aplicação roda em **`www.noglem.com.br`**, não localmente. O mecanismo é
**push-to-deploy**: empurrar pra `origin main` faz a Vercel (frontend) e o
Railway (backends) deployarem sozinhos.

## 0. Detectar o que mudou

Rode `git status` e `git diff --stat` e classifique o que vai subir:

| O que mudou | Alvo | Deploy disparado por |
|---|---|---|
| Frontend Next.js (`src/`, etc.) | **Vercel** | push em `alelemos02/Noglem` |
| `backend/` | **Railway** (backend central) | push em `main` |
| `services/rag-backend/` | **Railway** (RAG) | push em `main` |
| `services/patec-backend/` | **Railway** (PATEC) | push em `main` |

## 1. Pré-checagem

- Mostre `git status` e `git diff --stat`. Confirme que há mudança pra shippar.
- Confirme a branch atual.
- **Nunca commite** `.env`, `.env.local` ou arquivos com credenciais.
- **Nunca** use `git add .` indiscriminado — adicione só os arquivos da mudança.

## 2. Bump de versão (OBRIGATÓRIO — nunca pule)

A versão é exibida no sidebar em `src/components/layout/sidebar.tsx`. Formato `VX.Y.Z`.

Incremente segundo a natureza da mudança:

| Segmento | Quando incrementar |
|---|---|
| **X** (v**2**.0.3) | Impacto muito grande: redesign de layout, mudanças de arquitetura |
| **Y** (v2.**0**.3) | Inclusão de nova ferramenta no dashboard |
| **Z** (v2.0.**3**) | Ajustes menores: melhorias em ferramentas existentes, correções |

- Pergunte ao usuário se houver dúvida sobre o segmento.
- Mostre o valor **ANTES → DEPOIS** explicitamente.
- Se você não alterou a versão, **PARE**. Não há deploy sem bump.

## 3. Atualizar contexto da ferramenta (se aplicável)

Se a mudança tocou uma ferramenta do dashboard, atualize o arquivo
`.claude/apps/{tool-id}.md` correspondente (arquitetura, endpoints, quirks)
**antes do commit**.

## 4. Validação local

- `npx tsc --noEmit` — corrija TODOS os erros de TypeScript.
- `npm run build` — não commite código que não builda.
- Se houver qualquer erro, **PARE e corrija** antes de continuar.

## 5. Commit (Conventional Commits)

- `git add` apenas dos arquivos da mudança (incluindo o bump de versão).
- Mensagem no formato `<tipo>(escopo): <descrição>` — `feat`/`fix`/`refactor`/`chore`/`docs`/`perf`.
- Nunca use `--no-verify`.
- Inclua o trailer `Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>`.
- Confirme que o bump entrou no commit (`git show --stat`).

## 6. Push (dispara o deploy automático)

- `git push origin main`.
- Informe quais serviços vão redeploy automaticamente (Vercel / Railway), com base no passo 0.

## 7. Validação AO VIVO (não pule)

- Aguarde o deploy terminar de fato (não só ser enfileirado) — cheque o painel da Vercel/Railway se precisar.
- Confirme em **`www.noglem.com.br`** (ambiente ao vivo, não local) que a **nova versão** está sendo servida — ex.: a versão `VX.Y.Z` no sidebar bate com o bump.
- Para backends, confirme via endpoint de health/version ou logs do Railway.
- Se vier a versão antiga (deploy obsoleto): re-cheque/re-deploye até refletir.
- Só então reporte sucesso, mostrando a prova (versão ao vivo / saída do health).

## Regras inegociáveis

- **Deploy só com pedido explícito** — nunca automático.
- Sem bump de versão → sem commit → sem push.
- Sem build limpo → sem commit.
- Nunca commitar segredos (`.env*`, chaves).
- Sem confirmação do ambiente ao vivo → não diga que terminou.
