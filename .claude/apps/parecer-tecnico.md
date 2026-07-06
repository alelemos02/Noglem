---
name: parecer-tecnico
description: Parecer Técnico (PATEC) — análise LLM de documentação de engenharia vs fornecedores, microserviço próprio
metadata:
  type: project
---

# Parecer Técnico (PATEC)

**Status:** Beta  
**Categoria:** Análise

## O que faz

Ferramenta de análise comparativa: recebe documentação de engenharia (especificações, datasheets) e documentos de fornecedores, e gera um parecer técnico item a item usando LLM. Cada item recebe um status (A=Aprovado, B=Aprovado com comentários, C=Rejeitado, D=Info ausente, E=Item adicional) e o parecer geral é: APROVADO, APROVADO_COM_COMENTARIOS ou REJEITADO.

## Disciplinas

O usuário seleciona a disciplina ao criar um novo parecer. A disciplina altera o system prompt enviado ao Gemini:

| Disciplina | Status | System prompt |
|------------|--------|---------------|
| `instrumentacao` | Ativo | `SYSTEM_PROMPT_INSTRUMENTACAO` (ISA, IEC 61511, IEC 61508) |
| `eletrico` | Ativo | `SYSTEM_PROMPT_ELETRICO` (NR-10, ABNT NBR 5410, IEC 60364, IEC 60079) |
| `civil`, `mecanico`, `tubulacao` | Em breve (desabilitado na UI) | — |

A lógica de seleção de prompt está em `get_system_prompt(disciplina)` em `llm_prompt.py`. O campo `disciplina` é armazenado no model `Parecer` e exibido como badge na lista.

## Tipos de documentos

| Tipo (`Documento.tipo`) | Papel na análise |
|-------------------------|-----------------|
| `engenharia` | Documento principal de engenharia — especificação técnica a ser verificada |
| `fornecedor` | Proposta técnica do fornecedor — comparada contra a especificação |
| `anexo_engenharia` | Documentos complementares (datasheets de referência, normas internas) — fornecidos como contexto de apoio à IA, não como spec principal |

O upload de `anexo_engenharia` usa o endpoint `POST /pareceres/{id}/documentos/anexo_engenharia`. Anexos são opcionais — a análise só exige `engenharia` + `fornecedor`. No prompt, os anexos aparecem na seção `## DOCUMENTOS COMPLEMENTARES (ENGENHARIA)` entre os docs de engenharia e os do fornecedor.

## Perfis de análise (`perfil_analise`)

| Perfil | Itens | Comportamento |
|--------|-------|---------------|
| `simples` | 10 | Desvios críticos: segurança, rejeições e bloqueios |
| `padrao` | 15 | Cobertura equilibrada dos requisitos críticos e relevantes |
| `completa` | 20 | Análise abrangente cobrindo todos os requisitos de impacto técnico |
| `personalizado` / `custom_N` | N (1-100) | Número exato de itens definido pelo usuário |
| `integral` | sem limite | Analisa TODOS os requisitos da tabela de engenharia na íntegra |

O perfil `integral` usa `PROFILE_INTEGRAL_TEMPLATE` em `llm_prompt.py` (sem cap de itens) e é aceito pelo validator em `analise.py`.

## Arquivos principais

### Frontend
- Lista de pareceres: `src/app/dashboard/parecer-tecnico/page.tsx`
- Criar novo: `src/app/dashboard/parecer-tecnico/novo/page.tsx`
- Detalhe/resultado: `src/app/dashboard/parecer-tecnico/[id]/page.tsx`
- Componentes UI: `src/components/parecer-tecnico/` (status-badge, etc.)
- API client: `src/lib/patec-api.ts`

### API Route
- Proxy catch-all: `src/app/api/parecer-tecnico/[...path]/route.ts`

### Backend
- Microserviço PATEC: `services/patec-backend/` (Railway, porta 8001)
- Variável de ambiente: `PATEC_API_URL` (default: `http://localhost:8000`)

## Fluxo de dados

```
Browser → patecApi.* → /api/parecer-tecnico/* → PATEC microservice
```

O proxy suporta SSE streaming (análise em tempo real), file downloads (PDF/XLSX), e multipart uploads.

## Status de processamento

```
pendente → processando → concluido
                      ↘ erro
```

## Modelo de dados principal (ParecerResponse)

```ts
interface ParecerResponse {
  id: string;
  numero_parecer: string;    // ex: "PT-001"
  projeto: string;
  fornecedor: string;
  revisao: string;
  disciplina: string;        // ex: "instrumentacao" | "eletrico"
  status_processamento: "pendente" | "processando" | "concluido" | "erro";
  parecer_geral: "APROVADO" | "APROVADO_COM_COMENTARIOS" | "REJEITADO" | null;
  total_itens: number;
  total_aprovados: number;
  total_aprovados_comentarios: number;
  total_rejeitados: number;
  total_info_ausente: number;
  total_itens_adicionais: number;
  criado_em: string;
}
```

## Decisões de arquitetura

- PATEC é um microserviço completamente separado com banco próprio e Alembic
- A análise LLM é assíncrona — o frontend lista e refetch para detectar mudança de status
- A página de lista refaz fetch quando a janela recebe foco (para pegar pareceres que terminaram em background)
- O `patec-api.ts` é o único client autorizado — não chame `/api/parecer-tecnico/` diretamente do frontend

## Skill relacionada

Existe a skill `/patec-otimizar` para otimização de prompts e parâmetros do PATEC.

## Redesign v3 (2026-07)

UI migrada para o design system v3 "instrumento de precisão" (ver `.claude/rules/design-system-conventions.md`):
- Header via `<PageHeader tool="{id}">` — nome/descrição/badge vêm do `tools-registry.ts`
- Upload via `<Dropzone>` compartilhado; loading via `<Spinner>`/`Button loading`
- Erros persistentes em `<Alert>`; sucesso/erro transiente via `toast` (sonner); ações destrutivas via `useConfirm()`
- Tokens novos: canvas/surface-1..3, edge, fg-*, accent azure — zero cores Tailwind literais
- Endpoints e lógica de negócio inalterados
