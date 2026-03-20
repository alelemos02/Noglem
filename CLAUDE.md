# CLAUDE.md — JulIA (Claude Code)

Leia **AGENTS.md** para todas as convencoes do projeto: arquitetura, design system, como alterar/adicionar ferramentas, stack e variaveis de ambiente.

O que esta abaixo e especifico do Claude Code e nao se aplica a outros agentes.

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

**Fluxo de deploy:** faca o commit + push para o GitHub. Vercel e Railway fazem o deploy automaticamente.

Correcoes de bug devem ser commitadas e enviadas ao GitHub — nao basta rodar localmente.

Para verificar logs de producao: acesse o painel do Railway ou Vercel.

---

## Atualizacao deste arquivo

`CLAUDE.md` e `AGENTS.md` **nao sao atualizados automaticamente**.
Peca explicitamente quando quiser atualizar: *"atualiza o CLAUDE.md / AGENTS.md com isso"*.
