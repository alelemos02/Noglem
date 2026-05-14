---
name: levantamento-quantitativos
description: Levantamento de Quantitativos — extrai geometria e calcula quantitativos de fundação de tanques Petrobras N-381
metadata:
  type: project
---

# Levantamento de Quantitativos

**Status:** Beta  
**Categoria:** Civil

## O que faz

Processa desenhos de fundação de tanques em PDF (padrão Petrobras N-381) e extrai automaticamente geometria (raio, altura, diâmetro, escavação) e calcula quantitativos de obra: concreto estrutural (m³), formas in situ (m²), grout (m³), concreto magro (m³), escavação (m³), reaterro (m³), bota-fora (m³) e estacas (m). Exporta planilha Excel com totais por tanque e total geral.

## Arquivos principais

### Frontend
- Página: `src/app/dashboard/levantamento-quantitativos/page.tsx`

### API Routes
- Preview (JSON): `src/app/api/civil/preview/route.ts`
- Download Excel: `src/app/api/civil/processar/route.ts`

### Backend
- Router: `backend/app/routers/civil.py`
- Pipeline (em `backend/app/services/civil/`):
  - `pdf_extractor.py` — extração do PDF (lança `ExtractionError` se não reconhecer)
  - `geometry_parser.py` — parsing da geometria extraída
  - `calculator.py` — cálculo dos quantitativos (`calcular_todos`)
  - `validator.py` — validação de geometria e cálculos com tolerância configurável
  - `excel_generator.py` — geração do `.xlsx` (`gerar_excel_bytes`)
  - `models.py` — `ConfigProjeto`, `ResultadoQuantitativo`, `ItemQuantitativo`
  - `config/defaults.json` — configuração padrão do projeto (tolerâncias, parâmetros)

## Fluxo de dados

```
Browser (PDF) → POST /api/civil/preview → Backend → extrator→parser→calculator→validator → JSON
Browser (PDF) → POST /api/civil/processar → Backend → extrator→parser→calculator→validator→excel_generator → .xlsx
```

## Validações do backend

O backend valida em duas etapas:
1. **Campos obrigatórios**: se algum campo esperado não for encontrado no PDF, retorna 422 com lista dos campos faltantes
2. **Consistência numérica**: `validar_geometria` + `validar_calculos` com tolerância definida em `defaults.json`

## Resposta de preview

```ts
interface ResultadoPreview {
  documento: string;       // número do documento extraído do carimbo
  tanques: string[];       // IDs dos tanques (ex: ["T-101", "T-102"])
  total_tanques: number;
  fonte_extracao: string;  // método de extração usado
  itens: ItemQuantitativo[];
  total_1_tanque: Record<string, number>;
  total_geral: Record<string, number>;
}
```

## Dependências de backend

- Backend Central (porta 8000, Railway)
- Rate limiting: `enforce_pdf_rate_limit`
- Sem LLM — cálculo determinístico baseado em extração de texto PDF

## Limitações conhecidas

- **Apenas desenhos padrão Petrobras N-381** — outros formatos retornam `ExtractionError`
- O "Baixar Excel" reenvia o PDF para o backend (não cacheia o preview)
- Fonte de extração (`fonte_extracao`) indica qual método foi usado — útil para debug quando o extrator falha
