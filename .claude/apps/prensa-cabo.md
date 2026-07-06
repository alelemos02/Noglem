---
name: prensa-cabo
description: Prensa Cabo Analyzer — seleção de prensa-cabos e geração de BOM via Claude AI, ferramenta HTML estática
metadata:
  type: project
---

# Prensa Cabo Analyzer

**Status:** Beta  
**Categoria:** Instrumentação

## O que faz

Ferramenta de seleção de prensa-cabos para quadros elétricos. Analisa lista de cabos, seleciona os prensa-cabos adequados por tipo/diâmetro e gera BOM (Bill of Materials).

## Arquitetura — diferente das outras ferramentas

Esta ferramenta é um **HTML estático** embutido em iframe — não usa React/Next.js diretamente. A IA é chamada via Claude API (Anthropic) direto, sem passar pelo backend FastAPI.

```
Browser → <iframe src="/tools/prensa-cabo.html"> → interação client-side
HTML estático → POST /api/prensa-cabo/extract-catalog → Anthropic API direta
```

## Arquivos principais

- Frontend (wrapper): `src/app/dashboard/prensa-cabo/page.tsx` — apenas renderiza o iframe
- Ferramenta real: `public/tools/prensa-cabo.html` — toda a lógica UI + JS está aqui
- API Route: `src/app/api/prensa-cabo/extract-catalog/route.ts`

## API Route — sem autenticação Clerk

```ts
// Chama Anthropic API diretamente com ANTHROPIC_API_KEY
// Usa anthropic-beta: "pdfs-2024-09-25" (suporte a PDF nativo)
POST https://api.anthropic.com/v1/messages
```

**Atenção:** esta rota **não valida Clerk auth** — qualquer um que conheça a URL pode chamar. Diferente de todas as outras ferramentas.

## Dependências

- `ANTHROPIC_API_KEY` (variável de ambiente no Railway/Vercel)
- Claude API (Anthropic) — modelo definido no HTML estático
- Sem backend FastAPI

## Como modificar

- Mudanças de UI/lógica: editar `public/tools/prensa-cabo.html`
- Mudanças de modelo ou prompt: editar o HTML ou a API Route
- Para adicionar auth: adicionar `auth()` do Clerk na API Route

## Quirks

- O iframe ocupa 100% da viewport (`h-[calc(100vh-4rem)]`)
- Comunicação entre o iframe e o Next.js é via `window.postMessage` se necessário
- Não compartilha tokens de design system com o resto do app (HTML puro)

## Redesign v3 (2026-07)

UI migrada para o design system v3 "instrumento de precisão" (ver `.claude/rules/design-system-conventions.md`):
- Header via `<PageHeader tool="{id}">` — nome/descrição/badge vêm do `tools-registry.ts`
- Upload via `<Dropzone>` compartilhado; loading via `<Spinner>`/`Button loading`
- Erros persistentes em `<Alert>`; sucesso/erro transiente via `toast` (sonner); ações destrutivas via `useConfirm()`
- Tokens novos: canvas/surface-1..3, edge, fg-*, accent azure — zero cores Tailwind literais
- Endpoints e lógica de negócio inalterados
