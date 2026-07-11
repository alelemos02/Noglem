# Backlog de problemas — Parecer Técnico

> Lista de bugs/ajustes encontrados no uso do **Parecer Técnico**, para serem
> corrigidos **em lote** quando o Alexandre der o comando. Enquanto isso: apenas
> registrar e propor direção de solução — **não executar nada**.
>
> Hipóteses marcadas com _(a confirmar)_ ainda não foram validadas no código.
>
> **Status geral:** #1, #2 e #3 **APLICADOS na v3.1.1** (2026-07-11) — aguardando
> deploy (Vercel frontend + Railway PATEC backend).

---

## Bug #1 — Erro falso ao excluir parecer

- **Status:** aberto
- **Onde:** Dashboard do Parecer Técnico (lista de pareceres) — `src/app/dashboard/parecer-tecnico/`
- **Sintoma:** ao excluir um parecer, aparece o aviso vermelho
  _"1 parecer(es) não puderam ser excluídos."_ com botão "Tentar novamente".
  Porém, **após atualizar a página (F5), o parecer aparece corretamente excluído** —
  o erro se resolve sozinho.
- **Frequência:** toda vez que exclui.
- **Impacto:** baixo-médio (a exclusão funciona; o problema é o feedback falso de erro,
  que assusta o usuário).
- **Hipótese _(a confirmar)_:** o backend **exclui de fato**, mas o frontend reporta
  erro. Como o item some no refresh, a persistência está OK — o bug está no
  feedback/refetch do cliente. Causas prováveis:
  1. Exclusão tratada de forma otimista/assíncrona e a checagem imediata ainda "vê" o
     item (corrida entre o DELETE e o refetch da lista).
  2. O endpoint DELETE responde `200/204` **sem corpo**, e o handler interpreta a
     ausência de payload esperado como falha.
  3. Exclusão em lote que conta como "não excluído" um item cuja confirmação chega
     depois (ex.: soft-delete + mudança de `fase_caso` processada async no PATEC).
- **Direção de correção _(a confirmar)_:**
  - Revisar o handler de exclusão no frontend: só marcar erro em falha real (status de
    erro), e refazer o refetch **após** a confirmação do DELETE, não em paralelo.
  - Conferir o status code / corpo do endpoint DELETE no PATEC e a API Route do Next.
  - Se houver estado otimista, garantir rollback só em erro real.
- **Arquivos prováveis (validar via grafo `graphify query` antes de ler):**
  - Frontend: página/lista do parecer-tecnico + hook de exclusão.
  - API Route: `src/app/api/parecer-tecnico/.../route.ts` (DELETE).
  - Backend PATEC: endpoint de exclusão de caso/parecer.

---

## Ajuste #2 — Voz da JulIA: humana e em 1ª pessoa (a engenheira, não uma "assistente robô")

- **Status:** aberto
- **Tipo:** mudança de tom/persona — **transversal** (afeta TODA a comunicação com o
  usuário no fluxo, não é um texto isolado).
- **Onde:** todas as mensagens da JulIA no fluxo conversacional do Parecer Técnico
  (recebimento de documento, extração de requisitos, ciclo com fornecedor, verificação,
  fechamento, mensagens de erro).
- **Pedido:** a JulIA deve soar como uma **pessoa** — a **engenheira de instrumentação**
  que vai conduzir o parecer, não uma assistente/sistema. Calorosa, natural, em primeira
  pessoa, e **pode chamar o usuário pelo nome**. O usuário tem que sentir que está
  falando com uma pessoa.
- **Exemplo (tela atual → desejado):**
  - _Atual (cara de sistema):_ "Documento principal recebido. ✅ Antes de eu ler e
    extrair os requisitos: você tem documentos complementares..."
  - _Desejado (voz da JulIA):_ "Oi Alexandre, obrigada por me mandar o documento! Antes
    de eu mergulhar nos requisitos — você tem algum documento complementar (norma,
    referência) pra me passar? Se não tiver, é só falar que eu já começo."
- **Impacto:** experiência/produto (não é bug funcional).
- **Direção de correção _(a confirmar)_:**
  1. Descobrir **onde a copy nasce**: provável que seja texto estático nos widgets/steps.
     Pistas do grafo — comunidades _"Parecer Conversation Widgets"_ (`ComplementaresWidget`,
     `ExtrairRequisitosWidget`, `RetryAnaliseWidget`, `RodadaErroWidget`) e
     _"Conversation Step Logic"_ (`derive-step.ts`, `ConversationStep`). Confirmar via
     `graphify query` se é template fixo ou texto gerado por LLM.
  2. **Se estático:** reescrever as strings com a voz da JulIA e **injetar o primeiro
     nome** do usuário (Clerk). Definir fallback sem nome (ex.: "Oi!").
  3. **Se gerado por LLM:** ajustar o system prompt / persona para essa voz.
  4. **Recomendado:** centralizar a persona/voz num único lugar (guia de voz + helper de
     saudação com nome) para manter consistência em TODAS as mensagens e não espalhar
     tom por arquivo.
- **Diretrizes de voz (DECIDIDAS):**
  - **Nome do usuário:** usar **quando a JulIA julgar oportuno/importante** — não em toda
    interação (cansa/robotiza), mas também **não** só na saudação. Ela sente o momento
    certo, **sem exagero**. Efeito de uma pessoa que te chama pelo nome quando faz
    sentido (ênfase, retomada, notícia relevante).
  - **Emojis:** só em **ocasião muito especial** (ex.: fechamento/entrega do parecer).
    No dia a dia, **sem emoji** para não parecer infantil — cortar os `✅` e decorativos
    das mensagens de rotina.
  - **Tratamento:** informal ("você"), primeira pessoa, tom de engenheira de
    instrumentação que conduz o trabalho — nunca "assistente/sistema".
  - **A fazer junto:** escrever um **guia de voz da JulIA** curto que consolide essas
    regras e sirva de referência única para reescrever todas as mensagens do fluxo de
    forma consistente.

---

## Ajuste #3 — Resposta sobre um item: humana, não "ficha de campos"

- **Status:** aberto
- **Tipo:** mesma família do **Ajuste #2** (voz/persona), aplicada à resposta quando o
  usuário pergunta sobre um item específico do parecer ("me fale o item 7"). Reusar as
  mesmas diretrizes de voz do #2.
- **Onde:** resposta do chat da JulIA ao **detalhar um item/requisito** do parecer.
- **Problema:** hoje a resposta é um **despejo de campos rígido** — `Item 7:` /
  `Categoria` / `Descrição do Requisito` / `Valor Requerido` / `Valor Fornecedor` /
  `Status` / `Justificativa Técnica` / `Ação Requerida` / `Prioridade`. Parece um
  registro de banco impresso, não uma pessoa explicando. Robótico.
- **Desejado:** a JulIA explica o item como uma **engenheira de verdade explicaria pra um
  colega** — em prosa natural, conectando com o usuário, **sem perder a precisão
  técnica** (valores req/forn, status, conformidade, ação). Técnica **e** humana.
- **Exemplo (atual → desejado):**
  - _Atual:_ lista de campos ("Categoria: Hardware / Valor Requerido: 8 SET… / Status: A…").
  - _Desejado:_ "O item 7 é o fornecimento dos painéis remotos — e esse ficou redondo. A
    gente pediu 8 conjuntos em AISI316, IP-65 no mínimo, SIL 2 e arquitetura hot-hot, pra
    aguentar o ambiente costeiro não condicionado. O fornecedor atendeu certinho e ainda
    detalhou: 8 conjuntos pro DCS e 8 pro SIS, todos redundantes, no mesmo padrão. Por
    isso aprovei sem ressalvas (status A) — nenhuma ação necessária da sua parte. Como é
    prioridade alta, ainda bem que já está resolvido."
- **Direção de correção _(a confirmar)_:**
  - Descobrir se essa resposta é **gerada por LLM** (a partir dos campos do `ItemParecer`)
    ou montada por **template fixo**. Confirmar via `graphify`/código (provável
    `chat.py` do PATEC + dados de `ItemParecer`).
  - **Se LLM:** ajustar o prompt para, ao explicar um item, escrever em **prosa natural**
    (não lista de campos), mantendo todos os fatos.
  - **Se template:** trocar o dump de campos por geração em prosa (idealmente via LLM com
    os dados estruturados como contexto).
  - **Cuidado:** não perder rigor — deve continuar dizendo valores, status e ação, só que
    embutidos numa explicação humana, não numa ficha.
- **Observação de produto:** equilibrar com o AGENTS.md ("tom técnico, direto, preciso").
  Alvo = "engenheira sênior explicando pra um colega": humana e calorosa, **mas rigorosa**
  — nunca marketing, nunca infantil.

---
