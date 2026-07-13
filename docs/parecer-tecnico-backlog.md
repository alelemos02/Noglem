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
- **Reforço futuro (Alavanca 3, não feita ainda):** alargar o verificador Pro para
  re-checar também todo item **A de requisito composto** ou cujo A não tenha citação
  explícita — hoje ele só pega inconsistência de valor entre itens parecidos.

---

## Observação estrutural — patec-api sem push-to-deploy

- O serviço **patec-api** (Railway) não está conectado ao GitHub, então push na
  `main` **não** o redeploya (só patec-worker e conhecimento-api sobem). Foi por
  isso que o fix v3.1.1 ficou preso de 11/07 a 13/07 sem ninguém notar. Todo deploy
  de backend do PATEC é manual via `railway up --service patec-api` até reconectar.
- **Ação:** painel Railway → serviço **patec-api** → Settings → Source → conectar
  `alelemos02/Noglem` com watch path `services/patec-backend/**` (igual ao patec-worker).
