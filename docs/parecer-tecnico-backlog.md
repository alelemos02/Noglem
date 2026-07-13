# Backlog de problemas — Parecer Técnico

> Lista de bugs/ajustes encontrados no uso do **Parecer Técnico**, para serem
> corrigidos **em lote** quando o Alexandre der o comando. Enquanto isso: apenas
> registrar e propor direção de solução — **não executar nada**.
>
> Hipóteses marcadas com _(a confirmar)_ ainda não foram validadas no código.
>
> **Histórico:** #1 (erro falso ao excluir) e #2 (voz humana da JulIA nas
> mensagens de fluxo) aplicados na v3.1.1 e em produção. #3 (item em prosa) foi
> escrito mas **NÃO surtiu efeito** — reaberto abaixo com a causa-raiz real.

---

## Ajuste #3 (REABERTO) — Resposta sobre um item ainda vem como "ficha de campos"

- **Status:** APLICADO em 2026-07-13 (chat no Pro + exemplo âncora no prompt) —
  aguardando validação no uso. Se ainda vier ficha em caso antigo, o próximo
  passo é iniciar um caso novo (histórico limpo) para isolar o efeito.
- **Sintoma:** ao perguntar "me fale do item N", a JulIA responde com o dump
  rotulado (`Item N:` / `Descrição do Requisito:` / `Valor Requerido:` /
  `Valor Fornecedor:` / `Status:` / `Justificativa Técnica:` / `Ação Requerida:` /
  `Prioridade:`), exatamente o que o Ajuste #3 deveria ter eliminado. Persiste
  mesmo com o backend redeployado (patec-api, 13/07) e o prompt novo confirmado
  no ar.
- **O que já foi descartado:**
  - **Não é template.** Os itens são injetados no contexto como **JSON compacto**
    (`itens_summary`, `chat.py:565-575`), não como ficha. A ficha é **gerada pelo
    próprio LLM**.
  - **A instrução anti-ficha ESTÁ no ar.** `chat.py:141-146` diz textualmente para
    NÃO despejar campos rotulados e explicar em prosa. Confirmado deployado.
- **Causa-raiz (duas forças somando):**
  1. **Modelo fraco.** O chat roda em `settings.GEMINI_MODEL = "gemini-2.5-flash"`
     (`config.py:42`, usado em `chat.py:854`). O próprio código admite em
     `chat.py:372`: _"(ja vimos o modelo ignorar instrucoes de prompt)"_. O flash
     não obedece a instrução de estilo. **A escolha do flash foi um workaround de
     404**: o commit v3.1.1 trocou `gemini-3.1-pro` → `gemini-2.5-flash` porque o
     nome Pro **sem** o sufixo `-preview` dava 404. Só que o nome Pro **correto**
     (`gemini-3.1-pro-preview`) já existe e já roda em produção para extração (W1)
     e verifier (`config.py:57,62`). Ou seja: dava pra ter apontado o chat pro Pro
     certo desde o início.
  2. **Histórico da conversa contamina.** O chat inclui as mensagens anteriores da
     thread no contexto (`chat.py:716-726`). Num caso antigo, o histórico já tem
     várias respostas no formato ficha (geradas pelo prompt velho). Modelo fraco
     imita o padrão das próprias mensagens anteriores — a repetição em contexto
     pesa mais que a instrução do system prompt. Por isso o problema é mais teimoso
     em casos antigos do que num caso novo.
- **Direção de correção (recomendada):**
  1. **Apontar o chat para o Pro que funciona.** Criar `GEMINI_CHAT_MODEL` (default
     `gemini-3.1-pro-preview`, mesmo nome já usado por extração/verifier) e usar em
     `chat.py:792,854` no lugar de `GEMINI_MODEL`. Baixo risco (nome já exercitado
     em prod). Custo/latência sobem só no chat (volume baixo, interativo).
  2. **Reforçar a regra com exemplo.** Mover a regra anti-ficha para o topo do
     system prompt e colar um exemplo concreto BOM (prosa) × RUIM (ficha). Modelos
     seguem exemplo melhor que instrução abstrata — blinda mesmo o flash.
  3. **Validar em caso NOVO** (histórico limpo) além do caso antigo, para separar o
     efeito "modelo" do efeito "histórico contaminado".
- **Arquivos:** `services/patec-backend/app/services/chat.py`,
  `services/patec-backend/app/core/config.py`.
- **Deploy:** patec-api **não** tem push-to-deploy do GitHub — exige `railway up`
  manual (ou reconectar o Source no painel). Ver observação estrutural abaixo.

---

## Observação estrutural — patec-api sem push-to-deploy

- O serviço **patec-api** (Railway) não está conectado ao GitHub, então push na
  `main` **não** o redeploya (só patec-worker e conhecimento-api sobem). Foi por
  isso que o fix v3.1.1 ficou preso de 11/07 a 13/07 sem ninguém notar.
- **Ação:** no painel Railway → serviço **patec-api** → Settings → Source →
  conectar `alelemos02/Noglem` com watch path `services/patec-backend/**` (igual
  ao patec-worker). Enquanto não fizer, todo deploy de backend do PATEC é manual
  via `railway up --service patec-api`.
