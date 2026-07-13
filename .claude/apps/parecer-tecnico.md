---
name: parecer-tecnico
description: Parecer Técnico (PATEC) — caso técnico completo conduzido por conversa (JulIA), com ciclo iterativo com fornecedor, verificação final e revisão de especificação. Microserviço próprio.
metadata:
  type: project
---

# Parecer Técnico (PATEC)

**Status:** Beta
**Categoria:** Análise
**Origem:** portado do PATEC_PLUS em 2026-07 (substituiu integralmente a versão anterior — backend e frontend).

## O que faz

O parecer é um **caso técnico** com ciclo de vida completo, dirigido por
`pareceres.fase_caso`:

```
SETUP → REQUISITOS → ANALISE → CICLO_FORNECEDOR → VERIFICACAO_FINAL → FECHADO
```

1. **Setup/Requisitos (W1)** — upload de docs; a LLM extrai a lista de requisitos, o engenheiro edita e aprova → tabela `requisitos` (fonte única de verdade, validada por humano).
2. **Análise (R1/W2)** — `run_analysis_sync` lê os requisitos aprovados do BD (não re-extrai), classifica A–E, vincula `ItemParecer.requisito_id`. `POST /ciclo/iniciar` (W2) leva ao ciclo. **A análise só roda na fase ANALISE** (gate em `analise.py`).
3. **Ciclo com fornecedor (W3/R2/W4)** — resposta entra por `POST /rodadas` (tipos 1–4: `PROPOSTA_REVISADA`, `RESPOSTA_ITENS`, `RESPOSTA_ITENS_PROPOSTA_POSTERIOR`, `EMAIL_AVULSO`) ou pela carta XLSX (`/reimportar-respostas`). LLM sugere vínculos → engenheiro confirma (W3) → avaliação R2 → decisão por item (W4): `ACEITAR / ESCLARECER / REJEITAR / REPROVAR_CASO`.
4. **Verificação final (R3/W5)** — Tipo 1 dispensa LLM; tipos 2/3/4 exigem proposta final + verificação contra os acordos.
5. **Fechamento (W6)** — `POST /fechar` com `APROVADO / COM_PENDENCIA / REPROVADO`.
6. **Revisão de especificação (R4/W7, lateral)** — `POST /spec-versoes`: diff contra os requisitos do BD (cenários A/B/C); aplicar reabre alterados, desativa removidos (nunca apaga), inclui novos.

Estados do item: `ABERTO → PENDENTE_FORNECEDOR → EM_REAVALIACAO → ACEITO/REPROVADO` (+ `DESATIVADO`).

## Frontend — UI conversacional (JulIA)

A página do caso é uma **thread de conversa única** (estilo chat), derivada 100%
do estado do backend — F5 é idempotente. Tudo em `src/components/parecer-tecnico/`:

- `derive-step.ts` — função pura: escolhe o ÚNICO passo ativo + widget a partir do snapshot (a precedência espelha `state_machine.py`).
- `derive-timeline.ts` — remonta o passado "congelado" com timestamps reais do BD.
- `conversation-provider.tsx` — snapshot único (parecer, docs, requisitos, draft, itens, rodadas, resumo, verificação, specVersoes, chatHistory), `refreshSnapshot()` e UM poller consolidado para todos os jobs assíncronos.
- `widgets/` — um widget interativo por passo (upload via `<Dropzone>`, requisitos, progress, análise-resultado, rodada, vinculação, decisão, verificação, fechar, export, spec).
- `commands.ts` — comandos locais da barra de texto (`ver tabela`, `ver itens`, `exportar …`, `revisar especificação`, `reanalisar`, `editar requisitos`, `fechar caso`); o que não casa vai ao chat RAG.
- `data-panel.tsx` / `widgets/ciclo-table-panel.tsx` — modais de tabela (banco do caso; decisões W4 em lote).
- `status-badge.tsx` — badges A–E/parecer geral/processamento (usado na lista).

**Ações de chat (contrato `<acao>`)**: a LLM JulIA emite bloco estruturado que o
backend filtra do stream e executa; o frontend ressincroniza. A LLM nunca despeja
JSON/tabela no chat.

**Voz da JulIA (persona)**: ela é a **engenheira** que conduz o caso (não uma
"assistente"/sistema), em 1ª pessoa, humana e próxima, mas técnica e precisa.
Regras no `_JULIA_PERSONA_BASE` (`services/chat.py`): explicar itens **em prosa**
(nunca despejar campos "Categoria:/Valor Requerido:/Status:"), usar o **primeiro
nome** com parcimônia — passado via `usuario_nome` em `build_chat_context`, vindo
de `current_user.nome` no endpoint — e emoji só em ocasião muito especial. As
falas fixas do onboarding seguem a mesma voz em
`src/components/parecer-tecnico/script.ts`.

### Páginas
- Lista: `src/app/dashboard/parecer-tecnico/page.tsx` (cards + badge de fase/desfecho)
- Criar: `src/app/dashboard/parecer-tecnico/novo/page.tsx` (form → redireciona para a conversa)
- Caso: `src/app/dashboard/parecer-tecnico/[id]/page.tsx` (ConversationProvider + ConversationScreen, escapa o padding do Shell com `-m-6 h-[calc(100vh-3.5rem)]`)
- Qualidade (dono): `src/app/dashboard/parecer-tecnico/qualidade/page.tsx` — métricas da IA, protegida por `OWNER_EMAILS` no backend

### Entrada e navegação (dashboard PATEC-first, 2026-07)
O PATEC é a **entrada padrão da área logada**: `/` (logado) e `/dashboard`
redirecionam para `/dashboard/parecer-tecnico`. A grade "Agentes" foi removida
(as demais ferramentas seguem acessíveis só por URL direta; `tools-registry.ts`
continua existindo para o `PageHeader`). A sidebar (`src/components/layout/sidebar.tsx`)
é dedicada ao PATEC: **Casos** (ativa na lista e em `/[id]`), **Novo parecer** e
**Qualidade** — esta última renderizada só para `isAdminEmail` no client; o gate
real continua sendo `OWNER_EMAILS` no backend.

### API Route (proxy)
`src/app/api/parecer-tecnico/[...path]/route.ts` — Clerk auth + `X-Internal-API-Key`
+ `X-User-Id`; exporta **GET/POST/PUT/PATCH/DELETE**; suporta SSE (chat) e downloads.
Para rotas `v1/admin*` envia também `X-User-Email` (e-mail real do Clerk) — é ele
que o `require_owner` compara com `OWNER_EMAILS` (usuários Clerk ficam gravados
com e-mail sintético `clerk_<id>@noglem.com.br`).

Cliente tipado: `src/lib/patec-api.ts` (único client autorizado).

> **Quirk:** o helper `request()` em `patec-api.ts` trata `204 No Content`/corpo
> vazio **antes** de parsear JSON — sem isso, o DELETE (que responde 204) fazia o
> caller tratar sucesso como erro (falso "N parecer(es) não puderam ser excluídos").

## Backend — microserviço (`services/patec-backend/`, Railway, porta 8001)

FastAPI + Celery + PostgreSQL/pgvector + Redis. Deploy: `railway.toml` (API) +
`railway.worker.toml` (worker Celery). `start.sh` roda `alembic upgrade head` no boot.

Serviços-chave (`app/services/`):
- `llm_client.py` — único cliente LLM (Gemini via httpx); ninguém chama o provedor direto.
- `prompts/` — prompts por operação: `analise`, `extracao` (W1), `vinculacao` (W3), `avaliacao` (R2), `verificacao` (R3), `spec_diff` (R4), `seguranca`.
- `analyzer.py` — orquestração R1; `_validate_parecer_json` é o normalizador central (repara chaves corrompidas pela LLM).
- `tasks.py` — Celery `run_analysis_sync`; cache `CacheAnalise` chaveado por `PROMPT_VERSION` + requisitos + docs + disciplina + idioma. **Mudou prompt/lógica de `analyze_documents`? Incremente `PROMPT_VERSION`.** Pipeline pós-cache (grounding, consistency, recovery, optimize) roda mesmo em cache hit.
- `requisitos.py` (W1), `ciclo.py` (W3/R2), `verificador_final.py` (R3), `spec_diff.py` (R4), `state_machine.py` (item + caso), `doc_selection.py` (só o doc de engenharia mais recente por nome), `ocr.py`, `chat.py`/`chat_memory.py` (chat RAG com ações), `exporter.py` (PDF/XLSX/DOCX + carta de pendências), `indexer.py`/`retriever.py` (pgvector).

Endpoints novos vs. versão antiga: `requisitos.py`, `verificacao.py`,
`revisao_spec.py`, `admin.py` (qualidade). Removidos: `llm_prompt.py`, `preview.py`
(não existe mais preview de documento).

### Variáveis de ambiente (Railway — API e worker)
Além das já existentes (`DATABASE_URL*`, `REDIS_URL`, `GEMINI_API_KEY`, `SECRET_KEY`,
`DOCUMENT_ENCRYPTION_KEY`, `INTERNAL_API_KEY`):
- `ENV=production` — ativa fail-fast de segredos default no startup (`validate_production_secrets`)
- `GEMINI_MODEL` (`gemini-2.5-flash`) — modelo INCIDENTAL barato: só chamadas utilitárias que não classificam (otimização de campos, reparo de JSON, estimativa, recuperação de valor do fornecedor)
- `GEMINI_ANALYSIS_MODEL=gemini-3.1-pro-preview` — análise item-a-item (classificação A/B/C/D, o coração). No Pro porque o flash carimbava "A" em requisito composto sem confirmar todas as condições. Entra na chave de cache (`tasks.py`)
- `GEMINI_CHAT_MODEL=gemini-3.1-pro-preview` — chat conversacional (JulIA); Pro para obedecer a voz (prosa, não ficha)
- `GEMINI_EXTRACTION_MODEL=gemini-3.1-pro-preview` (W1 define o escopo inteiro)
- `GEMINI_VERIFIER_MODEL=gemini-3.1-pro-preview` + `ENABLE_LLM_VERIFIER=true`
- `OWNER_EMAILS` — e-mails (reais, do login Clerk) com acesso ao dashboard de qualidade

**Regra anti-falso-A (prompt de análise):** o status A exige que o fornecedor
confirme EXPLICITAMENTE cada condição atômica do requisito (silêncio ≠ atendimento);
na dúvida, cair para D/B, nunca A. Ver seção "ANTI-FALSO-POSITIVO" em
`prompts/analise.py`. Mexeu nessa lógica? Incremente `PROMPT_VERSION` em `tasks.py`.

### Carta de pendências (layout XLSX)
Posições das colunas em `exporter.py` (`_CARTA_HEADERS`, `_CARTA_COL_RESPOSTA`,
`_CARTA_COL_ITEM_ID`) são a fonte única — o reimport determinístico em
`ciclo_avaliativo.py` importa essas constantes. Nunca re-hardcode coluna.

## Perfis de análise (governam só a extração W1)

`simples` (10) / `padrao` (15) / `completa` (20) / `integral` (todos) / `custom_N`.

## Fluxo de dados

```
Browser → patecApi.* → /api/parecer-tecnico/* → PATEC microservice (8001)
```

## Migração 2026-07 (PATEC_PLUS)

- 9 migrations novas (f1a0caso0001 … f9a0qaflag09) aplicadas automaticamente no deploy pelo `start.sh`. Elas **dropam** `pareceres.status_global` e `pareceres.rodada_atual` e renomeiam estados (`RESOLVIDO→ACEITO`, `ATENDE→ACEITAR` etc.) com backfill embutido.
- Pareceres legados nascem com `fase_caso='SETUP'`. Recomendado one-off pós-deploy:
  `UPDATE pareceres SET fase_caso='ANALISE' WHERE status_processamento='concluido' AND fase_caso='SETUP';`
- `PROMPT_VERSION` mudou → cache antigo é ignorado naturalmente.

## Skills relacionadas

- `/patec-otimizar` — revisão de concisão dos campos dos itens.
- `/verificar-fluxos` — auditoria estática dos gates W1–W7/R1–R4 e da máquina de estados (backend + derive-step).
