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
