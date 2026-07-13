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
