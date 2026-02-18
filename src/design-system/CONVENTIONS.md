# JulIA Design System - Convencoes Obrigatorias

Este documento define as regras visuais e tecnicas que TODOS os projetos dentro do ecossistema JulIA devem seguir. Sem excecao.

## 1. Identidade Visual

- Referencia: tipografia angular do logo APX GP (filme F1, Brad Pitt)
- Sensacao: precisao, engenharia, cockpit tecnico
- Tom de texto: direto, tecnico, sem linguagem infantilizada

## 2. Paleta de Cores

- Theme primario: Dark mode
- Accent: `#FF4D2D` (dark) / `#D93A1F` (light) - vermelho/laranja racing
- Accent e SEMPRE usado com moderacao: CTAs principais, indicadores criticos, a "/" do logo
- NUNCA usar accent como background de areas grandes
- Tokens de cor ficam em `_design-system/tokens/colors.css`

## 3. Tipografia

| Contexto      | Fonte           | Classe Tailwind  |
|---------------|-----------------|------------------|
| Logo/Branding | Rajdhani        | `font-brand`     |
| Headings      | Space Grotesk   | `font-heading`   |
| Body text     | Inter           | `font-body`      |
| Numeros/Dados | JetBrains Mono  | `font-mono`      |

**Regra absoluta:** Qualquer numero exibido na UI (metricas, valores, IDs, timestamps) DEVE usar `font-mono tabular-nums`.

## 4. Border Radius

- Minimo: 4px (`rounded-md`) ou 8px (`rounded-lg`)
- NUNCA usar `rounded-full` em containers, cards ou botoes
- `rounded-full` e permitido APENAS em avatares e dot indicators

## 5. Animacoes

- Permitido: `fade-in`, `fade-in-up`, `shimmer` (skeleton loading)
- PROIBIDO: elementos pulsando, girando ou se movendo sem acao do usuario
- Transicoes de hover/focus devem usar `duration-fast` (100ms)

## 6. Componentes

- Importar de `_design-system/components/ui`
- Usar a funcao `cn()` de `_design-system/lib/utils` para composicao de classes
- Manter consistencia: nao criar variantes ad-hoc de componentes que ja existem

## 7. Layout

- Sidebar fixa a esquerda (dashboard)
- Content area com max-width e padding consistente
- Spacing segue a escala base-4 definida nos tokens

## 8. Acessibilidade

- Contraste minimo WCAG AA (4.5:1 para texto, 3:1 para UI)
- Todos os elementos interativos devem ter `focus-visible` com ring accent
- Labels obrigatorios em inputs
- Usar `aria-*` adequados

## 9. Nomenclatura de Arquivos

- Componentes: `kebab-case.tsx` (ex: `agent-card.tsx`)
- Hooks: `use-kebab-case.ts` (ex: `use-agent-status.ts`)
- Types: `kebab-case.types.ts`
- Utils: `kebab-case.ts`
