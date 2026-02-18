# Instrucoes para LLM - Projeto JulIA

Voce esta trabalhando em um projeto que faz parte do ecossistema **JulIA** (Julia + IA).
Siga TODAS as convencoes abaixo. Sem excecao.

## Design System

O design system de referencia fica em `src/design-system/`.
Os componentes ativos ficam em `src/components/ui/` e ja integram o design system.
Tokens CSS ficam em `src/app/globals.css` (registrados via `@theme inline` para Tailwind v4).

### Imports obrigatorios

```tsx
// Componentes
import { Button } from '@/components/ui/button'
import { Card, CardHeader, CardContent, CardFooter } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Logo } from '@/components/ui/logo'
import { Skeleton } from '@/components/ui/skeleton'

// Utilitario de classes
import { cn } from '@/lib/utils'
```

### Regras visuais

1. **Cores:** usar APENAS os tokens CSS definidos em `globals.css`. Nunca hardcodar cores (nada de `bg-blue-500`, `text-green-500` etc.).
   - Semanticas: `bg-info-muted text-info`, `bg-success-muted text-success`, `bg-warning-muted text-warning`, `bg-error-muted text-error`
   - Surface: `bg-surface`, `bg-surface-hover`, `bg-surface-active`
   - Background: `bg-bg-primary`, `bg-bg-secondary`, `bg-bg-tertiary`
   - Text: `text-text-primary`, `text-text-secondary`, `text-text-tertiary`
   - Accent: `bg-accent`, `text-accent`, `bg-accent-muted`
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

- `Button` - variantes: default/primary, secondary/outline, ghost, danger/destructive, link | tamanhos: sm, default/md, lg, icon | prop: loading, asChild
- `Input` - props: label, error, hint
- `Card`, `CardHeader`, `CardContent`, `CardFooter`, `CardTitle`, `CardDescription`, `CardAction` - prop: interactive
- `Badge` - variantes: default, success, warning, error, info, secondary, outline | prop: dot, asChild
- `Logo` - variantes: full ("Jul/IA"), compact ("J/"), tagline | tamanhos: sm, md, lg
- `Skeleton` - shimmer loader

### Stack

- Next.js 16+ (App Router)
- React 19+
- TypeScript strict
- Tailwind CSS v4 com tokens JulIA via @theme

### Tom

- Tecnico, direto, preciso
- Interface de engenharia, nao marketing
- Nunca usar linguagem infantilizada ou excessivamente casual
