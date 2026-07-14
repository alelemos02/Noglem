# Backlog de problemas — Parecer Técnico

> Lista de bugs/ajustes encontrados no uso do **Parecer Técnico**, para serem
> corrigidos **em lote** quando o Alexandre der o comando. Enquanto isso: apenas
> registrar e propor direção de solução — **não executar nada**.
>
> **Histórico resolvido:** #1 (erro falso ao excluir), #2 (voz humana nas mensagens
> de fluxo), #3 (resposta de item em prosa, não ficha — resolvido em 13/07 pondo o
> chat no `gemini-3.1-pro-preview` + exemplo âncora no prompt; validado pelo usuário).

---

## Ajuste #4 — Análise carimba "A" (atendido) sem o fornecedor confirmar tudo (falso-A)

- **Status:** APLICADO em 2026-07-13 (análise no Pro + regra anti-falso-A no prompt) —
  aguardando validação com o **caso-controle** (reanalisar o parecer do item 3 do
  video wall; o item DEVE sair B, não A).
- **Sintoma real:** requisito composto (estação de video wall **com 4 monitores 55″
  + suportes + rack 19″**). O fornecedor confirmou monitores e suportes mas ficou
  **calado sobre o rack 19″**. A análise mesmo assim classificou **A (atendimento
  integral)** — afirmou conformidade de uma condição que o fornecedor nunca
  confirmou. Falso-A = desvio que vira pleito/aditivo na obra: o erro mais caro.
- **Causa-raiz (dois culpados):**
  1. **Análise no modelo fraco.** A classificação A/B/C/D rodava em `GEMINI_MODEL`
     (`gemini-2.5-flash`) via `analyzer.py` `_call_gemini`. Extração e verifier já
     eram Pro; só a classificação ficou no flash.
  2. **Prompt permitia "A" sem prova.** Em `prompts/analise.py`, a citação do trecho
     do fornecedor era exigida só para B/C/D; para A bastava "confirme em 1 frase". A
     "regra de ouro" era assimétrica (blindava falso-negativo, não falso-positivo).
     Então bastava bater parte das condições pra carimbar A.
- **Correção aplicada:**
  1. **`GEMINI_ANALYSIS_MODEL=gemini-3.1-pro-preview`** para a classificação (single/
     chunk/reduce em `analyzer.py`). `GEMINI_MODEL` (flash) vira só incidental
     (formatação, reparo JSON, estimativa, recuperação de valor). Modelo de análise
     entra na chave de cache (`tasks.py`) + `PROMPT_VERSION` 10→11 → invalida cache.
  2. **Seção ANTI-FALSO-POSITIVO no prompt:** decompor requisito em condições
     atômicas; A exige confirmação EXPLÍCITA (com citação) de CADA condição; silêncio
     ≠ atendimento; viés conservador (na dúvida, nunca A). Critério de A na tabela e
     regra de comprimento da justificativa também reforçados.
- **Arquivos:** `app/core/config.py`, `app/services/analyzer.py`, `app/services/tasks.py`,
  `app/services/prompts/analise.py`, `app/main.py` (health expõe `analysis_model`).
- **Validação (13/07):** caso-controle reanalisado saiu B (falso-A eliminado), mas a
  `acao_requerida` ainda esqueceu o rack 19″ → virou o Ajuste #5 abaixo.

---

## Ajuste #5 — Ação incompleta: sub-condição não confirmada fica fora da acao_requerida

- **Status:** APLICADO em 2026-07-13 (verificador de condições atômicas) — aguardando
  validação com o caso-controle (item do video wall deve listar rack 19″ E suportes
  E TAG na ação, com `condicoes_verificadas` populada).
- **Sintoma:** mesmo com a análise no Pro e a regra anti-falso-A, o item do video
  wall saiu B com ação cobrindo só "suportes + TAG" — o rack 19″ (não confirmado
  pelo fornecedor) ficou fora. Ação incompleta = o fornecedor só responde o que está
  na carta; condição fora da ação passa sem cobrança.
- **Causa-raiz:** decomposição atômica era só instrução mental no prompt (nada
  persistido/conferido); verificador Pro antigo só re-checava valor-copiado; limite
  de 150 chars na `acao_requerida` forçava a LLM a escolher qual pendência cortar.
- **Correção aplicada:**
  1. **`verify_atomic_conditions`** (analyzer.py) — último gate pós-cache, Pro,
     itens A/B: decompõe o requisito em condições, veredito por condição
     (CONFIRMADA com evidência / NAO_MENCIONADA / DIVERGENTE), guardas
     anti-alucinação determinísticas, rebaixa status (nunca melhora) e força TODAS
     as não-confirmadas na ação (compõe determinístico se a ação da LLM não cobrir).
  2. Coluna de auditoria `itens_parecer.condicoes_verificadas` (migration `fa0cond10`).
  3. Prompt de análise: regra 5 (ação enumera TODAS as pendências) + limite da ação
     150→300; `FIELD_OPTIMIZATION_SYSTEM`: "comprimir pode, omitir pendência não".
  4. `PROMPT_VERSION` 11→12 (invalida cache); flag `ENABLE_ATOMIC_VERIFIER`
     (rollback via env, sem deploy). 7 testes unitários novos (201 passando).
- **Fase 2 (registrada, NÃO implementada):** decomposição estruturada no W1 — campo
  `condicoes` JSON por requisito na extração (`prompts/extracao.py` + coluna em
  `requisitos` + tela de aprovação); o verificador atômico passaria a receber
  condições canônicas em vez de decompor na hora. Atacar se o padrão "perde
  condição" persistir mesmo com o gate.

---

## Observação estrutural — patec-api sem push-to-deploy

- O serviço **patec-api** (Railway) não está conectado ao GitHub, então push na
  `main` **não** o redeploya (só patec-worker e conhecimento-api sobem). Foi por
  isso que o fix v3.1.1 ficou preso de 11/07 a 13/07 sem ninguém notar. Todo deploy
  de backend do PATEC é manual via `railway up --service patec-api` até reconectar.
- **Ação:** painel Railway → serviço **patec-api** → Settings → Source → conectar
  `alelemos02/Noglem` com watch path `services/patec-backend/**` (igual ao patec-worker).

---

## Ajuste #6 — Sem botões para ver tabela/itens/extrações/documentos (só comando de texto)

- **Status:** APLICADO em 2026-07-13 — `CaseSidebar` (trilha lateral no caso) com
  botões "Tabela do caso", "Itens", "Rastreabilidade", "Requisitos" e "Documentos"
  (os dois últimos abrem modal lendo o snapshot). Comandos de texto seguem valendo.
- **Sintoma:** dentro de um caso, para ver a "Tabela do caso" (banco), os itens, a
  extração/requisitos ou os documentos carregados, o usuário **precisa digitar** o
  comando ("ver tabela", "ver itens", "rastreabilidade"). Repro real: pediu à JulIA
  para checar item excedente; ela achou o Item 18 (status E), mas **não havia como
  ver a tabela** — teve que digitar "ver tabela" pra abrir. As ações existem, mas
  ficam escondidas.
- **Esperado:** um **sidebar/painel à esquerda dentro do caso** com botões clicáveis
  para: ver extrações/requisitos, ver a tabela do caso (itens), ver rastreabilidade
  e ver os **documentos carregados**. Navegação visual, sem precisar decorar comando.
- **Causa-raiz (confirmada):** a tela do caso é UI 100% conversacional. O
  `conversation-screen.tsx:52-78` só renderiza header (link "←", número/projeto) +
  `PhaseLine` + `Thread` + `InputBar` — **nenhum controle persistente**. Todas as
  ações vivem como parsers de texto em `commands.ts`: "ver tabela" →
  `setShowDataPanel(true)` (`commands.ts:126-132`), "ver itens"/"ver item N" →
  widget items-browser (`commands.ts:107-118`), "rastreabilidade" →
  widget rastreabilidade (`commands.ts:121-123`). Os únicos botões que abrem a
  tabela ficam **dentro de widgets transitórios** da thread (`analise-resultado-widget.tsx:75`,
  `requisitos-widget.tsx:121`) — que rolam pra fora da tela; depois disso só resta
  digitar. O docstring do `data-panel.tsx:4-5` afirma "sempre acessível pelo botão
  no topo", mas **esse botão no topo não existe** (comentário desatualizado). Para
  "documentos carregados" não há visualizador persistente — o `upload-widget.tsx` só
  serve à etapa de upload; os docs vivem em `snapshot.documentos` mas sem tela
  dedicada.
- **Direção de correção (não executar):** adicionar um painel/sidebar lateral na
  `conversation-screen.tsx`, com botões que só **religam handlers já existentes** no
  `conversation-provider` (baixo esforço, nada de backend novo): "Tabela do caso" →
  `setShowDataPanel(true)`; "Itens" → `pushWidget({widget:"items-browser"})`;
  "Rastreabilidade" → `pushWidget({widget:"rastreabilidade"})`; "Requisitos/Extração"
  → reusar o fluxo de editar/ver requisitos. Criar um viewer de **documentos
  carregados** a partir de `snapshot.documentos` (lista nome/tipo; download se já
  houver rota). Cuidar de dois sidebars: o global do dashboard (Casos/Novo/Qualidade)
  é outro — este é interno ao caso (a tela do caso é fullscreen, escapa o padding do
  Shell com `-m-6`).
- **Arquivos:** `src/components/parecer-tecnico/conversation-screen.tsx`,
  `commands.ts`, `conversation-provider.tsx`, `data-panel.tsx`,
  `widgets/items-browser-widget.tsx`, `widgets/rastreabilidade-widget.tsx`,
  `widgets/upload-widget.tsx`.
- **Deploy/observações:** mudança **100% frontend** (Vercel, push-to-deploy do repo
  `alelemos02/Noglem`) — não envolve o patec-backend. Os handlers/rotas já existem;
  falta só a afordância visual. Ver Ajuste #7 (botão de exportar no mesmo sidebar).

---

## Ajuste #7 — Sem botão para exportar relatório/carta (só comando de texto)

- **Status:** APLICADO em 2026-07-13 — grupo "Exportar" no `CaseSidebar`
  (PDF/Excel/Word + Carta de pendências), religando `exportar()`/`downloadCarta()`.
- **Sintoma:** para exportar o parecer (PDF/XLSX/DOCX) ou a carta de pendências, o
  usuário **precisa digitar** o comando ("exportar pdf", "exportar xlsx",
  "exportar docx", "carta"). Repro: perguntou "como faço para exportar a tabela"; a
  JulIA respondeu instruindo a **digitar** os comandos. Não há botão.
- **Esperado:** botão(ões) de exportação **no mesmo sidebar** do Ajuste #6 — escolher
  formato (PDF/Excel/Word) e baixar a carta de pendências com um clique.
- **Causa-raiz (confirmada):** exportação existe só como comando de texto em
  `commands.ts`: "exportar pdf|xlsx|docx" → `c.exportar(fmt)` (`commands.ts:89-99`)
  e "carta" → `c.downloadCarta()` (`commands.ts:102-104`). Os handlers `exportar` e
  `downloadCarta` já estão no `conversation-provider` e há `widgets/export-widget.tsx`,
  mas nenhum botão persistente na `conversation-screen.tsx` os aciona.
- **Direção de correção (não executar):** no sidebar do caso (Ajuste #6), adicionar
  um grupo "Exportar" com botões que chamam os handlers existentes: PDF/XLSX/DOCX →
  `c.exportar(fmt)`; "Carta de pendências" → `c.downloadCarta()`. Reaproveitar o
  `export-widget.tsx` como conteúdo do botão/menu se fizer sentido. Zero backend novo.
- **Arquivos:** `src/components/parecer-tecnico/conversation-screen.tsx`,
  `commands.ts`, `conversation-provider.tsx`, `widgets/export-widget.tsx`.
- **Deploy/observações:** mudança **100% frontend** (Vercel). Casar com o Ajuste #6 —
  é o mesmo sidebar; provavelmente uma única implementação cobre os dois.

---

## Ajuste #8 — JulIA chama o usuário de "Usuário" (falta onboarding + perfil com apelido)

> **Escopo: plataforma** (não só o Parecer Técnico). O sintoma visível é na JulIA,
> mas o fix é um cadastro/perfil de usuário que serve todo o Noglem. Registrado aqui
> por ser irmão dos Ajustes #2/#3 (voz/nome da JulIA) e por ser onde o problema
> aparece.

- **Status:** APLICADO em 2026-07-13. Perfil no **Clerk `unsafeMetadata`** (sem
  migration): `ProfileProvider` (Shell) abre onboarding obrigatório no 1º login sem
  apelido; `ProfileDialog` coleta nome completo, apelido, ano de nascimento (Select),
  empresa, área. Header mostra o apelido ao lado da foto + item "Meu perfil" no menu
  do avatar. O proxy Next encaminha `X-User-Apelido` (URL-encoded) nas rotas de chat
  e o `chat.py` usa como `usuario_nome` (fallback `current_user.nome`). Zero migration,
  zero coluna nova.
- **Sintoma:** a JulIA trata o usuário por **"Usuário"** (ex.: "Sim, Usuário, excelente
  ponto…"), em vez do nome/apelido real da pessoa.
- **Esperado:**
  1. Logo após o cadastro (**inclusive login direto pelo Google**), abrir uma janela
     de dados gerais pedindo: **Nome completo**, **apelido / "como quer ser chamado"**,
     **ano de nascimento**, **empresa**, **área de atuação**. Todos campos livres,
     **exceto ano de nascimento** — este com formato padronizado de preenchimento
     (seletor/campo com máscara, não texto livre).
  2. A partir daí, a JulIA **sempre chama o usuário pelo apelido**.
  3. Tudo editável depois em **Configurações**, acessível ao clicar na **foto no canto
     superior direito**.
  4. O **apelido aparece ao lado da foto** no header.
- **Causa-raiz (confirmada):** no login via Clerk, `deps.py:52-54`
  (`_get_or_create_clerk_user`) cria o `Usuario` local com
  `nome=f"Usuário Noglem ({clerk_id[:8]})"` — um placeholder, porque o nome real do
  Clerk nunca é capturado. O chat monta a saudação a partir de `current_user.nome`
  (`api/v1/endpoints/chat.py:492` → `services/chat.py:781-784`, que pega
  `nome.strip().split()[0]` = "Usuário"). O modelo `Usuario`
  (`models/usuario.py:14-18`) só tem `nome/email/senha_hash/papel/ativo` — **não há
  `apelido`, `empresa`, `area_atuacao` nem `ano_nascimento`**, e não existe fluxo de
  onboarding que os colete.
- **Direção de correção (não executar):**
  1. **Onboarding (frontend):** modal no primeiro login (após Clerk, incl. Google) com
     os 5 campos; ano de nascimento como `<Select>` de anos ou input com máscara
     (reusar componentes do design system: `Input`, `Select`). Bloquear/nudge até
     preencher, mas permitir editar depois.
  2. **Armazenamento — decisão de arquitetura** _(a confirmar)_: perfil é de
     plataforma, não do PATEC. **Recomendado:** guardar em **Clerk metadata**
     (`unsafeMetadata`/`publicMetadata`) — sem migration, fonte única no frontend — e o
     **proxy Next encaminhar o apelido ao patec-backend** num header novo (padrão do
     `X-User-Email` já existente via `buildBackendAuthHeaders()` em `src/lib/backend.ts`
     e da API Route `src/app/api/parecer-tecnico/[...path]/route.ts`). O endpoint de
     chat passaria esse apelido como `usuario_nome` em vez de `current_user.nome`.
     **Alternativa:** colunas `apelido/empresa/area_atuacao/ano_nascimento` no
     `Usuario` do patec-backend (migration) — porém prende o perfil ao microserviço
     do PATEC, ruim para reuso por outras ferramentas.
  3. **Header:** mostrar o apelido ao lado do `UserButton` do Clerk em
     `src/components/layout/header.tsx`.
  4. **Configurações:** tela/aba acessível pelo menu do avatar, reeditando os mesmos
     campos (mesma fonte de verdade do onboarding).
- **Arquivos:** frontend — novo modal de onboarding, `src/components/layout/header.tsx`,
  `src/lib/backend.ts`, `src/app/api/parecer-tecnico/[...path]/route.ts`, uma tela de
  configurações; backend PATEC (se usar o apelido na JulIA) —
  `services/patec-backend/app/api/v1/endpoints/chat.py:492`,
  `services/patec-backend/app/services/chat.py:781-784`, e — só na alternativa de
  colunas — `app/models/usuario.py` + `app/core/deps.py:52-54` + migration.
- **Deploy/observações:** frontend na **Vercel** (push-to-deploy). Se tocar o
  patec-backend (chat/deps/model), lembrar que o **patec-api NÃO tem push-to-deploy**
  (exige `railway up` manual) e que colunas novas exigem migration — preferir a via
  Clerk-metadata + header justamente para evitar isso.
