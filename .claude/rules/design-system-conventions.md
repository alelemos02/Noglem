---
description: JulIA design system rules — CSS tokens, typography, components
---

# Design System Conventions (JulIA)

## Regra zero: apenas tokens CSS

**NUNCA use classes Tailwind literais como `bg-blue-500`, `text-green-500`, `text-red-400` etc.**
Use APENAS os tokens definidos em `src/app/globals.css`.

## Tokens disponiveis

### Cores semanticas
- Estado: `bg-info-muted text-info`, `bg-success-muted text-success`, `bg-warning-muted text-warning`, `bg-error-muted text-error`
- Surface: `bg-surface`, `bg-surface-hover`, `bg-surface-active`
- Background: `bg-bg-primary`, `bg-bg-secondary`, `bg-bg-tertiary`
- Texto: `text-text-primary`, `text-text-secondary`, `text-text-tertiary`
- Accent (#FF4D2D): `bg-accent`, `text-accent`, `bg-accent-muted` — apenas CTAs, links e indicadores criticos

## Tipografia

- Logo: `font-brand` (Rajdhani)
- Headings: `font-heading` (Space Grotesk)
- Body: `font-body` (Inter)
- Dados/Codigo: `font-mono` (JetBrains Mono)
- Numeros: SEMPRE `font-mono tabular-nums`

## Regras visuais

- Border radius maximo: `rounded-lg` (8px). NUNCA `rounded-full` em containers
- Animacoes: apenas `fade-in`, `fade-in-up`, `shimmer`. Nada pulsando sem acao do usuario

## Componentes disponiveis (importar de `@/components/ui/`)

```tsx
import { Button } from '@/components/ui/button'
// variantes: default/primary, secondary/outline, ghost, danger/destructive, link
// tamanhos: sm, md, lg, icon | props: loading, asChild

import { Card, CardHeader, CardContent, CardFooter } from '@/components/ui/card'
// prop: interactive

import { Badge } from '@/components/ui/badge'
// variantes: default, success, warning, error, info, secondary, outline | props: dot

import { Input } from '@/components/ui/input'
// props: label, error, hint

import { Logo } from '@/components/ui/logo'
// variantes: full, compact, tagline | tamanhos: sm, md, lg

import { Skeleton } from '@/components/ui/skeleton'
// shimmer loader

import { cn } from '@/lib/utils'
```

## Tools Registry

Para adicionar/modificar ferramentas no dashboard, edite APENAS `src/lib/tools-registry.ts`.
Campos obrigatorios: `id`, `name`, `description`, `icon`, `href`, `category`, `status`.
