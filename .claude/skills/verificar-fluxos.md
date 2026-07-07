---
name: verificar-fluxos
description: Auditoria ESTÁTICA dos fluxos do PATEC — varre a máquina de estados (item + caso) e os endpoints dos gates W1–W7/R1–R4 contra o fluxo canônico do caso técnico, e cruza com o derive-step do frontend. Lê o código ATUAL a cada execução (não tem cenário chumbado, não envelhece). Use ao alterar qualquer parte do fluxo do caso (requisitos, análise, ciclo, decisões, verificação, fechamento, revisão de spec) ou quando o usuário pedir para "verificar/auditar os fluxos".
---

# Verificar fluxos do PATEC (auditoria estática)

Você é um auditor do fluxo do caso técnico. Sua tarefa é **ler o código atual** e
confirmar que cada gate e cada transição de estado batem com o **fluxo canônico**.
Não execute o app, não rode testes, não chame a LLM — esta é uma leitura crítica.

Base de caminhos: backend em `services/patec-backend/app/`, frontend em
`src/components/parecer-tecnico/`.

## Regras de ouro

1. **Releia o código a cada execução.** Os caminhos de arquivo abaixo são pontos de
   partida; os números de linha mudam — **re-localize por grep/símbolo**, nunca
   confie em linha fixa.
2. **A fonte da verdade do GRAFO é `services/patec-backend/app/services/state_machine.py`.** O
   fluxo canônico (abaixo) é o que ele DEVE expressar; se divergir, reporte.
3. **Reporte desvios, não reescreva.** A saída é um relatório; só proponha correção
   se o usuário pedir.

## Fluxo canônico (o que tem que ser verdade)

Fases do caso (`pareceres.fase_caso`):
`SETUP → REQUISITOS → ANALISE → CICLO_FORNECEDOR → VERIFICACAO_FINAL → FECHADO`

| Gate | Invariante que DEVE valer | Onde olhar (re-localize, sob `app/`) |
|---|---|---|
| **W1** `aprovar_requisitos` | carimba `aprovado_em`/`aprovado_por`; põe `fase_caso=ANALISE`; só nas fases `{SETUP,REQUISITOS,ANALISE}` (em CICLO+ bloqueia → revisão de spec); deleta+recria a lista | `services/requisitos.py`, `api/v1/endpoints/requisitos.py` |
| **R1** `run_analysis_sync` | lê só requisitos `aprovado_em IS NOT NULL` e `ativo`; **falha se vazio**; **escopo fechado** (1 item por requisito aprovado, sem re-extrair da engenharia); **chamada única quando há `itens_aprovados`** (o caminho chunked duplica/perde vínculo); cria `RodadaAvaliacao(origem='PROPOSTA_INICIAL')` por item; vincula `requisito_id`; usa só o doc de engenharia mais recente (`doc_selection.eng_docs_correntes`) | `services/tasks.py`, `services/analyzer.py` |
| **W2** `iniciar_ciclo` | guard `fase==ANALISE`; se `todos_aceitos` → `VERIFICACAO_FINAL`, senão `CICLO_FORNECEDOR` | `api/v1/endpoints/ciclo_avaliativo.py` |
| **W3** `confirmar_vinculacao` | aplica `fornecedor_respondeu` (item → `EM_REAVALIACAO`); `rodada.status=VINCULACAO_CONFIRMADA`; dispara R2 (`start_avaliacao_in_background`) | `api/v1/endpoints/ciclo_avaliativo.py`, `services/ciclo.py` |
| **R2** `run_avaliacao_sync` | avalia cada resposta confirmada **com o histórico de acordos** do item no prompt | `services/ciclo.py`, `services/evaluator.py` |
| **W4** `decidir_item` | guard `fase==CICLO_FORNECEDOR`; grava `decisao_humana`; transiciona o estado; `REPROVAR_CASO` → item `REPROVADO` + `fase=FECHADO` + `desfecho=REPROVADO`; **auto-avanço** (`compute_avanco_automatico`) após decisão; limpa `marcacao_revisao` ao reavaliar | `api/v1/endpoints/ciclo_avaliativo.py` |
| **R3/W5** verificação | bifurcação bloco 29: última rodada decidida `PROPOSTA_REVISADA` (Tipo 1) OU sem ciclo → `ia_dispensada=true`; tipos 2/3/4 exigem proposta final + R3; `validar` aceita `{CONFORME, CONFORME_COM_PENDENCIA, NAO_CONFORME}`; guard `fase==VERIFICACAO_FINAL` | `services/verificador_final.py`, `api/v1/endpoints/verificacao.py` |
| **W6** `fechar` | desfecho ∈ `{APROVADO,COM_PENDENCIA,REPROVADO}`; **exige W5** (resultado validado) quando a verificação LLM não foi dispensada; permitido em `VERIFICACAO_FINAL` e em `CICLO_FORNECEDOR` (encerrar caso travado) | `api/v1/endpoints/verificacao.py` |
| **R4/W7** revisão de spec | diff cenários A/B/C; **A** fica no ponto (sem regredir), **B/C** → `CICLO_FORNECEDOR`; removidos → `requisito.ativo=False` + item `DESATIVADO` (nunca apaga); alterados → `reabrir_revisao_spec` + `marcacao_revisao='ALTERADO'`; novos → `marcacao_revisao='NOVO'`; respeita o **escopo** (não marca como "novo" seção fora dos requisitos atuais) | `services/spec_diff.py`, `api/v1/endpoints/revisao_spec.py` |

Máquina de estados do **item** (`state_machine.py` `_TRANSITIONS`):
```
ABERTO --classificar_aprovado--> ACEITO          (W2, status A)
ABERTO --classificar_nao_aprovado--> PENDENTE_FORNECEDOR
PENDENTE_FORNECEDOR --fornecedor_respondeu--> EM_REAVALIACAO   (W3)
EM_REAVALIACAO --decidir_aceitar--> ACEITO        (W4)
EM_REAVALIACAO --decidir_esclarecer/rejeitar--> PENDENTE_FORNECEDOR
EM_REAVALIACAO --decidir_reprovar_caso--> REPROVADO
(não-DESATIVADO) --reabrir_revisao_spec--> ABERTO  (W7)
(qualquer) --desativar--> DESATIVADO               (W7)
Terminais: ACEITO, REPROVADO, DESATIVADO
```

## Procedimento

1. **Leia `state_machine.py` inteiro** e confira o grafo do item + as transições de
   fase + `compute_avanco_automatico` + `todos_aceitos` contra o canônico acima.
   Qualquer transição faltando, a mais, ou com destino errado = desvio.
2. **Para cada gate da tabela**, abra o(s) arquivo(s) e confirme a invariante.
   Procure especialmente por: guard de fase certo, transição/evento certo, e o
   efeito colateral (carimbo, desfecho, auto-avanço, dispatch da próxima etapa).
3. **Confirme as REMOÇÕES** (não podem existir como código vivo):
   `grep -rn "ESCALONADO\|escalonar\|status_global\|rodada_atual\|preview-itens"`
   em `services/patec-backend/app/` — só comentários são aceitáveis. E
   `itens_aprovados` não pode estar em `app/api/` nem `app/schemas/` (é interno do
   analyzer).
4. **Cache da análise:** confirme que `PROMPT_VERSION` (em `services/tasks.py`) entra
   no hash de `CacheAnalise`. (Lembrete: ao mudar prompt/lógica de análise, o número
   tem que ter sido incrementado — senão a re-análise devolve o resultado velho.)
5. **Cross-check do frontend** (`src/components/parecer-tecnico/derive-step.ts`): a
   ordem de precedência do `deriveStep` deve espelhar a máquina de estados do
   backend. Checagens críticas:
   - SETUP: extração de requisitos só precisa do doc de engenharia → o passo de
     extração vem ANTES de pedir a proposta do fornecedor (o fornecedor só é exigido
     na fase ANALISE, antes do R1). *(Foi exatamente aqui que morou um bug.)*
   - Rascunho de requisitos (`requisitosDraft`) tem prioridade sobre `total_itens`
     na fase ANALISE (reabertura de requisitos).
   - A revisão de spec (`spec.*`) precede tudo quando há versão em andamento.
6. **Conversa JulIA** (`services/chat.py`): confirme que a IA NUNCA tem instrução de
   despejar JSON/tabela do parecer no chat no fluxo conversacional (toda mutação por
   bloco `<acao>`); o modo de gerar tabela JSON só vale no caminho legado `regenerar=true`.

## Saída (relatório)

Produza:
1. Uma **tabela por gate**: `Gate | Invariante | Encontrado | ✅ fiel / ⚠️ desvio`.
2. Uma seção **"Desvios"** listando cada divergência com arquivo + o que está
   errado + o que o canônico manda (sem corrigir, a menos que peçam).
3. Um **veredito final**: "fiel" ou "N desvio(s) — ver acima".

Se não houver desvio, diga claramente que a varredura passou e cite quantos gates +
transições foram conferidos.
