---
description: Code quality rules for JulIA — TypeScript conventions, function quality checklist, commit format
---

# Code Quality Conventions

## TypeScript

- Use `import type { … }` para imports que sao apenas tipos — nunca importe tipos como valores
- Prefira `type` sobre `interface` — use `interface` apenas quando precisar de merging ou for mais legivel
- Use branded types para IDs — evita misturar IDs de entidades diferentes:
  ```ts
  type UserId = string & { readonly _brand: 'UserId' }     // ✅
  type UserId = string                                       // ❌
  ```

## Funcoes — checklist antes de finalizar

Antes de considerar uma funcao pronta, verifique:

1. Voce consegue ler a funcao e entender facilmente o que ela faz? Se sim, pode parar aqui.
2. Ha muitos `if/else` aninhados (alta complexidade ciclomatica)? Se sim, provavelmente precisa ser simplificada.
3. Existe alguma estrutura de dados ou algoritmo que tornaria isso mais claro e robusto?
4. Ha parametros que nao sao usados?
5. Ha type casts desnecessarios que poderiam ir para os argumentos da funcao?
6. A funcao e testavel sem precisar mockar coisas core (banco, redis)? Se nao, pode ser testada como integration test?
7. Ha dependencias ocultas que poderiam ser fatoradas como argumentos?
8. Pense em 3 nomes melhores e veja se o nome atual e o melhor, consistente com o restante do codebase.

**Nao extraia uma funcao separada sem necessidade real:**
- A funcao refatorada sera reutilizada em outro lugar, OU
- E a unica forma de testar logica que nao pode ser testada de outra forma, OU
- A funcao original e extremamente dificil de seguir

## Commits — Conventional Commits

Formato obrigatorio para todas as mensagens de commit:

```
<tipo>[escopo opcional]: <descricao curta>

[corpo opcional]
```

Tipos:
- `feat:` — nova funcionalidade
- `fix:` — correcao de bug
- `refactor:` — refatoracao sem mudar comportamento
- `chore:` — tooling, dependencias, configuracao
- `docs:` — documentacao
- `style:` — formatacao, sem mudanca de logica
- `perf:` — melhoria de performance

Exemplos:
```
feat(parecer-tecnico): add PDF comparison endpoint
fix(rag): correct embedding dimension mismatch on upload
chore: update FastAPI to 0.115
```
