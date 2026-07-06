---
description: JulIA design system rules — CSS tokens, typography, components
---

# Design System Conventions (JulIA v3 — "instrumento de precisão")

## Regra zero: apenas tokens CSS

**NUNCA use classes Tailwind literais como `bg-blue-500`, `text-green-500`, `text-red-400` etc.**
Use APENAS os tokens definidos em `src/app/globals.css`. Referência viva: `/dashboard/styleguide` (admin).

## Tokens disponíveis

### Superfícies e texto
- Fundo do app: `bg-canvas`
- Superfícies em camadas: `bg-surface-1` (painéis/cards) → `bg-surface-2` (inputs/hover) → `bg-surface-3` (popover/elevado)
- Overlay de modal: `bg-overlay`
- Bordas: `border-edge`, `border-edge-strong`
- Texto: `text-fg`, `text-fg-muted`, `text-fg-subtle`, `text-fg-disabled`, `text-fg-inverse`

### Accent (azure técnico #4BA4EE)
`bg-accent`, `text-accent`, `bg-accent-subtle`, `text-accent-fg` (texto sobre accent),
`hover:bg-accent-hover`, `active:bg-accent-active` — apenas CTAs, links, estado ativo e
indicadores críticos. `info` colapsa no accent por design.

### Estados semânticos
`success` / `warning` / `danger` / `info` — cada um com `-subtle` (fundo translúcido) e
`-text` (variante clara para texto). Ex: `bg-danger-subtle text-danger`, `text-warning-text`.

## Tipografia

- Interface e headings: `font-sans` (IBM Plex Sans) — headings com `font-semibold tracking-tight`
- Dados/código/tags: `font-mono` (IBM Plex Mono)
- Números: SEMPRE `font-mono tabular-nums`
- Microlabels (categorias, eyebrows, labels de dados): classe **`microlabel`**
- Fontes via `next/font` em `src/lib/fonts.ts` — nunca `@import` de fontes no CSS

## Regras visuais

- Border radius: escala 2/3/4/6/8px (`rounded-xs`…`rounded-xl`). NUNCA `rounded-full` em containers
- Animações: apenas `fade-in`, `fade-in-up`, `shimmer`. Nada pulsando sem ação do usuário
- Z-index: use os tokens `z-(--z-dropdown)`, `z-(--z-modal)` etc.

## Padrões obrigatórios de UX

- **Header de página:** `<PageHeader tool="{id}" />` — nome/descrição/badge vêm do registry
- **Upload:** `<Dropzone />` — nunca reimplemente dropzone por página
- **Loading:** `<Spinner />` / `<LoadingBlock />` ou prop `loading` do Button — nunca `Loader2` ou divs `animate-spin`
- **Feedback transiente:** `toast.success/error(...)` de `@/components/ui/toast`
- **Aviso persistente:** `<Alert variant="...">`
- **Ação destrutiva:** `useConfirm()` — NUNCA `confirm()`/`alert()` nativos
- **Estado vazio:** `<EmptyState icon título descrição action? />`

## Componentes disponíveis (importar de `@/components/ui/`)

```tsx
import { Button } from '@/components/ui/button'
// variantes: default/primary, secondary/outline, ghost, danger/destructive, link
// tamanhos: sm, md, lg, icon | props: loading, asChild

import { Card, CardHeader, CardContent, CardFooter } from '@/components/ui/card'   // prop: interactive
import { Badge } from '@/components/ui/badge'          // chip mono/uppercase; variantes: default, success, warning, error, info, secondary, outline | prop: dot
import { Input } from '@/components/ui/input'          // props: label, error, hint
import { Textarea } from '@/components/ui/textarea'    // props: label, error, hint
import { PageHeader } from '@/components/ui/page-header'
import { Dropzone } from '@/components/ui/dropzone'
import { Alert } from '@/components/ui/alert'
import { EmptyState } from '@/components/ui/empty-state'
import { Progress } from '@/components/ui/progress'
import { Spinner, LoadingBlock } from '@/components/ui/spinner'
import { toast } from '@/components/ui/toast'
import { useConfirm } from '@/components/ui/confirm-dialog'
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { Checkbox } from '@/components/ui/checkbox'
import { Logo } from '@/components/ui/logo'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'
```

## Tools Registry

Para adicionar/modificar ferramentas no dashboard, edite APENAS `src/lib/tools-registry.ts`.
Campos obrigatórios: `id`, `name`, `description`, `icon`, `href`, `category`, `status`.
O `PageHeader` e a navegação consomem o registry — o nome lá é o nome canônico em todo lugar.
