---
description: Q-shortcuts for JulIA — type a short code to trigger a structured workflow
---

# Shortcuts

Digite o codigo abaixo a qualquer momento para acionar um fluxo estruturado.

---

**`qplan`**
```
Analise as partes relevantes do codebase antes de propor qualquer mudanca.
Verifique se o plano:
- E consistente com o restante do projeto
- Introduz o minimo de mudancas necessarias
- Reutiliza codigo existente (components, hooks, services, helpers)
Apresente o plano e aguarde confirmacao antes de codar.
```

---

**`qcode`**
```
Implemente o plano confirmado.
Apos implementar:
- Rode tsc --noEmit e corrija todos os erros de TypeScript
- Verifique se as regras do design system foram seguidas (tokens CSS, componentes)
- Confirme que nenhuma chamada direta ao backend foi introduzida no browser
```

---

**`qcheck`**
```
Voce e um engenheiro senior cetico revisando o codigo.
Para cada mudanca relevante que foi introduzida, verifique:
1. Seguranca: auth headers presentes, nenhum segredo exposto, backends nao chamados diretamente do browser
2. Design system: apenas tokens CSS, nenhuma cor Tailwind literal
3. TypeScript: sem any implicito, import type usado para tipos
4. Convencoes: nada refatorado alem do pedido, sem helpers criados para uso unico
Aponte problemas por categoria. Separe blockers de warnings.
```

---

**`qux`**
```
Voce e um testador humano da feature que acabou de ser implementada.
Liste os cenarios que testaria, ordenados por prioridade:
- Caminho feliz (golden path)
- Casos de borda
- Erros esperados (upload invalido, timeout, sem permissao)
- Regressoes em features adjacentes
```

---

**`qdeploy`**
```
Revise todas as mudancas pendentes.
Faca commit seguindo Conventional Commits (feat/fix/refactor/chore).
Inclua Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com> no commit.
Faca push para origin main.
Confirme quais servicos serao redeploy automaticamente (Vercel / Railway).
```
