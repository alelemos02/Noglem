# Guia de Logs e Analytics — JulIA

## O que temos implementado

### 1. PostHog (comportamento do usuário no frontend)

**O que captura:**
- Pageviews — toda página visitada
- `tool_clicked` — toda vez que alguém clica em uma ferramenta no dashboard
  - `tool_id`, `tool_title`, `tool_category` em cada evento

**Onde ver:** [posthog.com](https://posthog.com) → seu projeto → aba *Activity*

**Hook disponível para uso nas páginas de ferramentas:**
```ts
import { useAnalytics } from "@/hooks/use-analytics";

const { trackToolStarted, trackToolCompleted, trackToolError } = useAnalytics();
```

---

### 2. Logs estruturados (Railway — backend central)

**O que captura:** cada requisição ao backend central gera uma linha JSON:
```json
{"timestamp":"2026-05-13T17:42:01Z","method":"POST","path":"/api/pid/extract","user_id":"user_abc","status":200,"duration_ms":3821}
```

**Onde ver:** Railway → serviço *Backend Central* → aba *Logs*

**Campos:**
| Campo | Significado |
|-------|-------------|
| `timestamp` | Quando aconteceu |
| `method` | GET, POST etc |
| `path` | Qual endpoint foi chamado |
| `user_id` | ID do usuário (Clerk) |
| `status` | 200 = ok, 4xx = erro do usuário, 5xx = erro no servidor |
| `duration_ms` | Tempo de resposta em milissegundos |

---

## Rotina semanal

### Toda segunda-feira (~10 min)

1. **PostHog → Activity → filtrar por `tool_clicked`**
   - Quais ferramentas foram mais clicadas?
   - Alguma ferramenta não foi clicada nenhuma vez? → problema de descoberta (descrição, ícone)

2. **Railway → Logs → filtrar por `status:500`**
   - Houve erros no servidor? Em qual endpoint?
   - Se sim, abrir o log completo para investigar

---

## Quando um usuário reportar problema

1. Pegue o `user_id` dele (painel do Clerk ou pelo email no PostHog → *Persons*)
2. Railway → Logs → buscar pelo `user_id`
3. Veja a sequência de chamadas que ele fez
4. Identifique: erro de status (4xx/5xx) ou lentidão (duration_ms > 10000)?

---

## Como aprofundar o tracking por ferramenta

Quando quiser entender melhor o uso de uma ferramenta específica, adicione eventos na página dela:

```ts
// No início da análise
trackToolStarted({ tool_id: "pid-extractor", tool_title: "Extrator de P&ID", tool_category: "instrumentacao" });

// Quando concluir com sucesso
trackToolCompleted({ tool_id: "pid-extractor", tool_title: "Extrator de P&ID", tool_category: "instrumentacao", duration_ms: elapsed });

// Quando ocorrer erro
trackToolError({ tool_id: "pid-extractor", tool_title: "Extrator de P&ID", tool_category: "instrumentacao", error: "timeout" });
```

---

## Interpretação rápida

| Sintoma | Possível causa |
|---------|---------------|
| Muitos cliques, poucos `tool_completed` | Ferramenta com UX ruim ou erros silenciosos |
| `duration_ms` > 15000 frequente | Backend lento — verificar logs do Railway |
| `status: 500` repetido | Bug no servidor — verificar stack trace no Railway |
| Ferramenta sem `tool_clicked` | Usuário não encontra ou não entende o valor |
| Um usuário com muitos erros 4xx | Pode estar usando a ferramenta errado — oportunidade de onboarding |
