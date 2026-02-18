# Instrucoes para LLM - Projeto JulIA

Voce esta trabalhando em um projeto que faz parte do ecossistema **JulIA** (Julia + IA).
Siga TODAS as convencoes abaixo. Sem excecao.

## Design System

O design system compartilhado fica em `_design-system/` (um nivel acima da raiz do projeto, dentro de `01_ACTIVE/`).

### Imports obrigatorios

```tsx
// Componentes
import { Button, Card, Input, Badge, Table, Logo } from '../_design-system/components/ui'

// Utilitario de classes
import { cn } from '../_design-system/lib/utils'
```

### Regras visuais

1. **Cores:** usar APENAS os tokens CSS definidos em `_design-system/tokens/colors.css`. Nunca hardcodar cores.
2. **Accent (#FF4D2D):** usar com moderacao. Apenas para CTAs, links, indicadores criticos.
3. **Numeros:** SEMPRE com `font-mono tabular-nums`. Sem excecao.
4. **Border radius:** maximo `rounded-lg` (8px). NUNCA `rounded-full` em containers.
5. **Animacoes:** apenas `fade-in`, `fade-in-up`, `shimmer`. Nada pulsando sem acao do usuario.
6. **Tipografia:**
   - Logo: `font-brand` (Rajdhani)
   - Headings: `font-heading` (Space Grotesk)
   - Body: `font-body` (Inter)
   - Dados/Codigo: `font-mono` (JetBrains Mono)

### Componentes disponiveis

- `Button` - variantes: primary, secondary, ghost, danger | tamanhos: sm, md, lg | prop: loading
- `Input` - props: label, error, hint
- `Card`, `CardHeader`, `CardContent`, `CardFooter` - prop: interactive
- `Badge` - variantes: default, success, warning, error, info | prop: dot
- `Table`, `TableHeader`, `TableBody`, `TableRow`, `TableHead`, `TableCell`, `TableCellNumeric`
- `Skeleton` - shimmer loader
- `Logo` - variantes: full ("Jul/IA"), compact ("J/"), tagline | tamanhos: sm, md, lg

### Stack

- Next.js 14+ (App Router)
- React 18+
- TypeScript strict
- Tailwind CSS com preset JulIA

### Tom

- Tecnico, direto, preciso
- Interface de engenharia, nao marketing
- Nunca usar linguagem infantilizada ou excessivamente casual
