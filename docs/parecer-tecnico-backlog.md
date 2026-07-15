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

---

## Ajuste #9 — JulIA cega para documentos ANEXO (afirma não ter documento que está anexado)

- **Status:** APLICADO em 2026-07-14 (chat trata `anexo_engenharia` como lado engenharia).
- **Sintoma:** o usuário anexou um critério de projeto (E.DTAE001-TK1-00001) como
  documento complementar à MR (tipo `anexo_engenharia`). Ao pedir a análise cruzada,
  a JulIA afirmou que **só tinha a MR e as propostas** e que o TK1 "não foi carregado"
  — mesmo com o arquivo visível na lista de Documentos carregados (badge ANEXO).
- **Causa-raiz (confirmada):** o contexto do chat (`chat.py` `build_chat_context`)
  só considerava `engenharia` e `fornecedor`. Os anexos eram **triplamente ignorados**:
  (1) a seção "DOCUMENTOS ANALISADOS" (chat.py:596-598) listava só engenharia
  (`eng_docs_correntes`, que filtra `tipo=="engenharia"`) e fornecedor — a JulIA lia
  essa lista literalmente; (2) no modo full-text (688-703), o `texto_extraido` dos
  anexos não entrava; (3) no modo RAG, o rótulo do chunk (683) marcava tudo que não
  era `engenharia` como **"Fornecedor"** — anexos apareciam como se fossem do
  fornecedor. (O retriever/indexer JÁ indexam e recuperam anexos — sem filtro de tipo;
  e a ANÁLISE já os inclui via `texto_anexos`. O buraco era só no chat.)
- **Correção aplicada:** `anexo_docs = [d for d in documentos if d.tipo=="anexo_engenharia"]`;
  listados numa linha própria "Complementares da engenharia" na seção de documentos;
  `texto_extraido` incluído no modo full-text; rótulo do chunk RAG agora
  "Engenharia (complementar)". Sem migration, sem bump de versão do site.
- **Arquivos:** `services/patec-backend/app/services/chat.py`.
- **Deploy/observações:** backend-only → **patec-api** (`railway up`, sem push-to-deploy).
  O chat roda na API, não no worker.

---

## Ajuste #10 — JulIA "promete e não faz": narra aplicação na tabela sem emitir a ação

- **Status:** APLICADO em 2026-07-14 (rede de recuperação + selo persistente + prompt).
- **Sintoma:** em produção, a JulIA disse 2× "estou aplicando a atualização na
  tabela" e **nada foi gravado** — admitiu só quando cobrada ("acabei não disparando
  a atualização real na tabela. Falha minha!"). O usuário acha que o trabalho foi
  feito; a tabela continua intacta. Matador de confiança.
- **Causa-raiz (confirmada):** o chat só muta o banco quando o LLM emite o bloco
  invisível `<acao>{"tipo":"atualizar_itens",...}` no fim da resposta
  (endpoints/chat.py, split por string-find no stream). Sem o bloco, o caminho é
  100% silencioso: as 4 redes de segurança pós-stream cobriam só transições de
  fase e passos de setup — **nenhuma cobria `atualizar_itens`**. A narração falsa
  ainda era salva no histórico e contaminava turnos futuros ("narrar = feito").
- **Correção aplicada:**
  1. Detector determinístico `detectar_promessa_aplicacao_itens` (services/chat.py):
     sentença a sentença, verbo afirmativo de aplicação + alvo (item/tabela/status…),
     ignorando pergunta, condicional, negação e referência a aplicação passada.
  2. Nova rede no endpoint (última da cadeia, gate pós-análise sem draft): promessa
     detectada → chamada JSON de recuperação re-deriva o patch prometido e o executa
     pelo `_executar_acao` normal (evento `action` + badge). Se a recuperação não
     render ação válida → nota visível **persistida na mensagem** ("⚠️ …não foi
     gravada… peça 'aplique agora na tabela'") + `action_error` com detail específico.
  3. Selo persistente sem migration: ação que muta tabela (`atualizar_itens`/
     `atualizar_requisitos`) seta `gerou_nova_tabela=True` na mensagem; o frontend
     (`derive-timeline.ts`) deriva o badge "Tabela do caso atualizada por esta
     resposta" — **sobrevive a F5** e nunca depende da prosa do LLM. Os chips
     efêmeros de sucesso do `applyChatAction` saíram (o badge derivado assume).
  4. Falha na execução da ação também corrige o registro: nota "não foi gravada"
     appendada à mensagem salva (UPDATE direto) + `action_error` com a mensagem
     real do erro (ex.: "Nenhum item correspondente para atualizar.").
  5. Prompt: regra "PROIBIDO afirmar que aplicou sem emitir o bloco <acao> NESTA
     resposta" em `_JULIA_ACAO_ITENS` e `_JULIA_ACAO_REQUISITOS`.
- **Arquivos:** `services/patec-backend/app/services/chat.py`,
  `services/patec-backend/app/api/v1/endpoints/chat.py`,
  `src/components/parecer-tecnico/derive-timeline.ts`,
  `src/components/parecer-tecnico/conversation-provider.tsx`.
- **Deploy/observações:** backend → **patec-api** (`railway up`, sem push-to-deploy);
  frontend → Vercel (bump de versão no deploy). Recuperação usa o modelo JSON barato;
  lixo é barrado pelo `_acao_valida` estendido (itens 1-50, `numero` int). A rede
  NÃO roda com draft de requisitos em revisão (fluxo próprio `atualizar_requisitos`).

---

## Ajuste #11 — JulIA alucina conteúdo de documento e cita página inventada

- **Status:** APLICADO em 2026-07-14 (grounding no prompt + guarda determinística de páginas).
- **Sintoma:** perguntada sobre o escopo do TK-8, a JulIA afirmou que ele exigia
  NVR, 2 estações de monitoramento e teclado-joystick "conforme página 10 e índice
  na página 2" — **inventado** (retratou-se quando questionada: "essas informações
  não constam nos documentos"). Padrão perigoso: fabricar conteúdo + número de
  página com confiança.
- **Causa-raiz (confirmada):** o RAG traz top-k trechos; quando o trecho exato não
  é recuperado, o modelo preenche a lacuna com conhecimento próprio de engenharia
  (persona sênior reforça). Os chunks têm rótulo "Pagina N", mas nada impedia citar
  página fora dos trechos.
- **Correção aplicada:** (1) regras novas de grounding em `_CHAT_MODO_CONVERSA`
  (regra 11: citar página APENAS se visível no rótulo/texto do trecho; sem trecho →
  "não localizei nos trechos que consultei" + oferecer conferir o documento;
  experiência serve para INTERPRETAR, nunca ATESTAR) e na regra 2 da persona.
  (2) Guarda determinística sem LLM no endpoint: página citada na resposta que não
  aparece em NENHUM texto enviado ao modelo (system prompt, contexto, histórico,
  mensagem) → nota advisory visível e persistida ("⚠️ Não consegui confirmar a
  página X nos trechos que consultei…"). Nunca bloqueia.
- **Limitações conhecidas:** intervalos ("páginas 10 a 12") validam só o primeiro
  número após o marcador; enumeração "página 29 e 110 pontos" NÃO captura o 110
  (de propósito — evita acusação em falso).
- **Arquivos:** `services/patec-backend/app/services/chat.py`,
  `services/patec-backend/app/api/v1/endpoints/chat.py`.
- **Deploy/observações:** backend-only → **patec-api** (`railway up`).

---

## Ajuste #12 — Amarração MR→anexo não decomposta ("1 sistema completo" em vez do escopo real)

- **Status:** APLICADO em 2026-07-14 (passe 2 de amarrações na extração W1).
- **Sintoma:** MR item 1.1 = "Sistema de CFTV conforme TK-8" virou requisito
  "1 sistema completo", em vez do desdobramento real do TK-8 (110 câmeras
  distribuídas por área, tabela da pág. 29). Vale para CFTV, Controle de Acesso,
  Telefonia e Cabeamento. Sem decompor, é impossível saber o que tem no escopo e
  cobrar o fornecedor item a item. Exigência: decomposição **automática** na carga
  dos documentos; "jamais 1 sistema completo".
- **Causa-raiz (confirmada), dupla e estrutural:** (a) **os anexos `anexo_engenharia`
  nunca entravam na extração** — `_load_eng_text` filtra só `tipo=="engenharia"`
  (requisitos.py + doc_selection.py); o LLM não tinha o texto do TK-8 nem se
  quisesse decompor; (b) a regra "GRANULARIDADE — NAO FRAGMENTE" do prompt de
  extração proibia desdobrar. A análise (W2) é escopo-fechado (1 item por requisito
  aprovado) → a decomposição TEM que acontecer no W1.
- **Correção aplicada:** passe 2 na extração (`extrair_requisitos`, entre a extração
  base e o `salvar_draft`): `anexo_docs_correntes` carrega os anexos (dedup por
  nome, slice 120k/doc, ilegível <200 chars vira aviso no resumo); pré-filtro
  determinístico `_anexos_citados` (stems do nome do arquivo — "TK-8"→"tk8" — no
  texto dos requisitos; fallback por palavra-chave "conforme/vide/…"; nada citado →
  passe pulado); UMA chamada batched (`AMARRACAO_SYSTEM_PROMPT`, Pro de extração)
  decompõe cada amarração **seguindo o desdobramento do próprio documento** (linha
  de tabela tipo/área/quantidade = um sub-requisito, `referencia_engenharia` = "MR
  <ref> + <anexo> pag. N"); merge determinístico `_merge_decomposicoes` substitui
  na posição e renumera (guardas: cap 80 subs/item, sub sem descrição descartado,
  duplicada primeira vence, herança de categoria/prioridade). Falha de LLM/JSON →
  lista base intacta (nunca pior que antes). Referência a documento NÃO anexado →
  aviso no resumo do draft ("anexe e re-extraia"). Exceção na regra de granularidade
  + teto de perfil: item amarrado fica UM item na extração base (com a referência
  explícita) e não conta no limite — o desdobramento vem no passe 2, sem teto.
- **Limitações conhecidas:** tabela-alvo além do slice de 120k sai parcial (sem
  detecção automática); anexos citados somando >300k chars pulam o passe com aviso
  (latência do request síncrono); a explosão de itens a jusante é o comportamento
  pedido (110 sub-requisitos aprovados = 110 itens na análise — custo/latência do
  R1 crescem). Caso já em CICLO_FORNECEDOR não re-extrai (fase só avança) — ajuste
  manual via chat, agora confiável pelo #10.
- **Arquivos:** `services/patec-backend/app/services/requisitos.py`,
  `services/patec-backend/app/services/doc_selection.py`,
  `services/patec-backend/app/services/prompts/extracao.py`.
- **Deploy/observações:** a extração roda **na patec-api** (síncrona, sem Celery) →
  `railway up --service patec-api`; worker NÃO é tocado (PROMPT_VERSION "12" e cache
  da análise preservados). Se a extração com anexos der 504 no proxy Vercel:
  plano B = `export const maxDuration = 60` no route.ts do proxy (300 já quebrou
  no passado) e/ou reduzir slice para 60k.

---

## Ajuste #13 — Alteração de descrição no ciclo não reavalia os itens ("Análise indisponível na fase CICLO_FORNECEDOR")

- **Status:** APLICADO em 2026-07-14 (reavaliação cirúrgica de itens + gatilho automático).
- **Sintoma:** no caso MR271 (fase CICLO_FORNECEDOR), o usuário corrigiu via chat a
  descrição/valor requerido dos itens 1-4 e pediu "reavalise essas descrições com a
  proposta do fornecedor". A JulIA emitiu a ação `reanalisar` (R1 completo), que é
  bloqueada fora da fase ANALISE → "Análise indisponível na fase CICLO_FORNECEDOR".
  Regra do produto: **alterou descrição → a análise DEVE ser refeita**, mesmo com a
  carta já enviada ao fornecedor.
- **Causa-raiz (confirmada):** só existia a reanálise COMPLETA (R1), corretamente
  proibida no ciclo (endpoints/analise.py gate) — ela regeneraria TODOS os itens a
  partir dos REQUISITOS aprovados (descrições ANTIGAS — desfaria a correção manual)
  e apagaria o vínculo com as rodadas. Não existia reavaliação por item.
- **Correção aplicada:**
  1. **Serviço novo `app/services/reavaliacao.py`** — reavaliação cirúrgica: UMA
     chamada batched (GEMINI_ANALYSIS_MODEL, prompt `REAVALIACAO_SYSTEM_PROMPT` com
     regras anti-falso-positivo) reclassifica SÓ os itens pedidos contra a proposta
     original; preserva `numero`; estado por item segue a máquina legal
     (`reabrir_revisao_spec` → ABERTO → `classificar_*`, mesmo caminho da revisão de
     spec/R1); avanço automático CICLO→VERIFICACAO_FINAL via
     `compute_avanco_automatico` se todos aceitos; auditoria
     `item_reavaliado_via_julia` por item; fases permitidas: ANALISE e
     CICLO_FORNECEDOR; máx. 15 itens por chamada.
  2. **Gatilho automático:** patch via chat (`atualizar_itens`) que toque
     `descricao_requisito`/`valor_requerido` dispara a reavaliação dos itens
     alterados na sequência (falha da reavaliação NUNCA desfaz o patch — vira aviso
     `reavaliacao_erro` no evento). Regra do usuário atendida ao pé da letra.
  3. **Nova ação de chat `reavaliar_itens`** (`{"numeros":[...]}`): pedido explícito
     "reavalie os itens 1 a 4" funciona no ciclo; prompt `_JULIA_ACAO_REAVALIAR_ITENS`
     contrasta com `reanalisar` (R1 só na fase ANALISE).
  4. **UX:** aviso no stream "(Reavaliando os itens contra a proposta — pode levar um
     minuto...)" antes da chamada; chip com o resultado ("item 3: B→A"); selo
     persistente "Tabela atualizada" já cobre (ação em `_ACOES_QUE_MUTAM_TABELA`).
- **Limitações conhecidas:** reavaliação NÃO roda o verificador atômico do R1 (as
  regras de enumeração de condições estão no próprio prompt); chamada síncrona no
  request SSE (~30-60s para poucos itens) — se estourar timeout do proxy em lotes
  grandes, mover para task Celery; `condicoes_verificadas` não é repopulada.
- **Arquivos:** `services/patec-backend/app/services/reavaliacao.py` (novo),
  `app/services/prompts/analise.py`, `app/api/v1/endpoints/chat.py`,
  `app/services/chat.py`, `src/lib/patec-api.ts`,
  `src/components/parecer-tecnico/conversation-provider.tsx`,
  `tests/unit/test_reavaliacao.py` (novo).
- **Deploy/observações:** roda na **patec-api** (`railway up`, sem push-to-deploy) +
  frontend Vercel (bump no deploy). Worker não tocado; PROMPT_VERSION/cache intactos.
