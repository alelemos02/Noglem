# Como Criar e Subir uma Nova App no Julia

Este guia mostra o fluxo padrão para adicionar uma nova aplicação ao Julia (como hoje já existe para Tradutor, Extrator de Tabelas e PDF para Word).

## Visão rápida da arquitetura

```
Browser → Next.js Page (src/app/dashboard/<slug>/page.tsx)
              ↓ fetch("/api/<slug>")
         Next.js API Route (src/app/api/<slug>/route.ts)   ← Clerk auth + proxy seguro
              ↓ fetch(API_URL) com X-Internal-API-Key + X-User-Id
         FastAPI Backend (backend/app/routers/<modulo>.py)  ← require_internal_api_key
              ↓
         Service (backend/app/services/<modulo>_service.py)
```

- Frontend (Next.js) renderiza a página em `src/app/dashboard/...`
- Frontend chama uma rota interna em `src/app/api/...` (proxy seguro)
- Rota interna valida o usuário com Clerk e envia para o Backend (FastAPI) com:
  - `X-Internal-API-Key` (chave compartilhada entre front e back)
  - `X-User-Id` (ID do Clerk)
- Backend valida a chave, processa e responde
- O layout do dashboard é gerenciado pelo `Shell` (`src/components/layout/shell.tsx`), que inclui Header + Sidebar + conteúdo

## Checklist completo para nova app

## 1) Definir nome e rotas

Escolha um slug único para a nova app. Exemplo: `ocr`.

- Tela: `/dashboard/ocr`
- API interna Next.js: `/api/ocr`
- API backend: `/api/ocr` (ou `/api/nome-do-modulo`)

---

## 2) Backend (FastAPI)

### 2.1 Criar/atualizar schemas

Arquivo: `backend/app/models/schemas.py`

Adicione o request/response da nova app com Pydantic. Exemplo:

```python
class OcrRequest(BaseModel):
    language: str = "pt"

class OcrResponse(BaseModel):
    text: str
    confidence: float
```

### 2.2 Criar service

Pasta: `backend/app/services/`

Crie um service para a lógica de negócio (ex: `ocr_service.py`). Siga o padrão dos existentes:
- `backend/app/services/gemini_service.py` (tradução)
- `backend/app/services/pdf_extract_service.py` (extração PDF)
- `backend/app/services/pdf_convert_service.py` (conversão PDF)

### 2.3 Criar router

Pasta: `backend/app/routers/`

Crie um arquivo de router (ex: `ocr.py`). Padrão obrigatório:

```python
from fastapi import APIRouter, Depends
from app.dependencies.security import require_internal_api_key
from app.dependencies.rate_limit import enforce_ocr_rate_limit  # criar se necessário
from app.models.schemas import OcrRequest, OcrResponse
from app.services.ocr_service import OcrService

router = APIRouter(dependencies=[Depends(require_internal_api_key)])

@router.post("/", response_model=OcrResponse)
async def process_ocr(
    request: OcrRequest,
    _: None = Depends(enforce_ocr_rate_limit),
):
    service = OcrService()
    return await service.process(request)
```

### 2.4 Criar rate limit (se necessário)

Arquivo: `backend/app/dependencies/rate_limit.py`

Adicione uma nova função seguindo o padrão existente:

```python
async def enforce_ocr_rate_limit(
    request: Request,
    x_user_id: str | None = Header(default=None),
):
    user = _identity(request, x_user_id)
    allowed, retry_after = limiter.allow(
        key=f"ocr:{user}",
        limit=settings.RATE_LIMIT_OCR_PER_MIN,
        window_seconds=60,
    )
    if not allowed:
        _raise_limit_exceeded(retry_after)
```

E adicione a configuração em `backend/app/config.py`:

```python
RATE_LIMIT_OCR_PER_MIN = int(os.getenv("RATE_LIMIT_OCR_PER_MIN", "10"))
```

### 2.5 Registrar router no app principal

Arquivo: `backend/app/main.py`

```python
from app.routers import translate, pdf, ocr

app.include_router(ocr.router, prefix="/api/ocr", tags=["OCR"])
```

### 2.6 Dependências Python

Arquivo: `backend/requirements.txt`

Se a nova app precisar de bibliotecas extras, adicione ao `requirements.txt` seguindo o padrão de agrupamento com comentários:

```
# OCR Processing
pytesseract>=0.3.10
Pillow>=10.0.0
```

### 2.7 Variáveis de ambiente

Arquivos:
- `backend/.env.example` — adicione as novas vars com valor placeholder
- `backend/.env` — configure com valores reais
- `backend/app/config.py` — adicione à classe `Settings`

---

## 3) Frontend (Next.js)

### 3.1 Criar rota API interna (proxy)

Arquivo: `src/app/api/<slug>/route.ts`

**Para APIs com JSON (sem upload de arquivo):**

```typescript
import { NextRequest, NextResponse } from "next/server";
import { auth } from "@clerk/nextjs/server";
import { API_URL, buildBackendAuthHeaders } from "@/lib/backend";

export async function POST(request: NextRequest) {
  try {
    const { userId } = await auth();
    if (!userId) {
      return NextResponse.json({ error: "Não autorizado" }, { status: 401 });
    }

    const body = await request.json();

    const response = await fetch(`${API_URL}/api/ocr/`, {
      method: "POST",
      headers: buildBackendAuthHeaders(userId, true), // true = inclui Content-Type: application/json
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "Erro no servidor" }));
      return NextResponse.json(
        { error: error.detail || "Erro no processamento" },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("Erro ao conectar com backend:", error);
    return NextResponse.json(
      { error: "Backend indisponível. Verifique se o servidor está rodando." },
      { status: 503 }
    );
  }
}
```

**Para APIs com upload de arquivo (FormData):**

```typescript
// Mesmo padrão, mas:
const formData = await request.formData();

const response = await fetch(`${API_URL}/api/ocr/`, {
  method: "POST",
  headers: buildBackendAuthHeaders(userId), // SEM true — não define Content-Type (o browser define multipart)
  body: formData,
});
```

**Para APIs que retornam arquivo (blob):**

```typescript
// Após o fetch, verificar content-type:
const contentType = response.headers.get("content-type") || "";

if (contentType.includes("spreadsheetml") || contentType.includes("octet-stream")) {
  const blob = await response.blob();
  return new NextResponse(blob, {
    headers: {
      "Content-Type": contentType,
      "Content-Disposition": response.headers.get("content-disposition") || "attachment",
    },
  });
}
```

### 3.2 Criar página da ferramenta

Pasta: `src/app/dashboard/<slug>/page.tsx`

- Crie o layout e fluxo da tela
- Chame a API interna (`/api/<slug>`) com `fetch` — nunca o backend direto
- O layout (Header + Sidebar) já é aplicado automaticamente pelo `src/app/dashboard/layout.tsx` via `<Shell>`

### 3.3 Publicar no menu e dashboard

**Sidebar** — `src/components/layout/sidebar.tsx`

Adicione um item ao array `menuItems`:

```typescript
const menuItems = [
  // ... itens existentes ...
  {
    title: "OCR",
    href: "/dashboard/ocr",
    icon: ScanText,         // ícone do lucide-react
    badge: "Beta",          // "Live", "Beta" ou omitir
  },
];
```

**Dashboard home** — `src/app/dashboard/page.tsx`

Adicione um item ao array `tools`:

```typescript
const tools = [
  // ... itens existentes ...
  {
    id: "ocr",
    title: "OCR",
    description: "Extraia texto de imagens com IA",
    icon: ScanText,
    href: "/dashboard/ocr",
    status: "beta" as const,           // "live" ou "beta"
    color: "bg-purple-500/10 text-purple-500",
  },
];
```

### 3.4 Variáveis de ambiente (se necessário)

Arquivos:
- `.env.example` (raiz) — adicione novas vars com placeholder
- `.env.local` — configure com valores reais

Env vars já existentes no frontend (não precisa recriar):

```
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...
CLERK_SECRET_KEY=sk_test_...
NEXT_PUBLIC_CLERK_SIGN_IN_URL=/sign-in
NEXT_PUBLIC_CLERK_SIGN_UP_URL=/sign-up
NEXT_PUBLIC_API_URL=http://localhost:8000
INTERNAL_API_KEY=<mesmo valor do backend>
```

---

## 4) Segurança (obrigatório)

- **Nunca** chame o backend direto do browser — sempre passe pelo proxy `src/app/api/...`
- O helper `buildBackendAuthHeaders` (em `src/lib/backend.ts`) monta os headers:
  - `X-Internal-API-Key` — chave compartilhada
  - `X-User-Id` — ID do Clerk
  - `Content-Type: application/json` — apenas quando `includeJsonContentType = true`
- `INTERNAL_API_KEY` deve ser **o mesmo valor** no frontend e no backend
- No backend, `require_internal_api_key` (em `backend/app/dependencies/security.py`) valida a chave

---

## 5) Teste local antes de deploy

Frontend:

```bash
npm run dev
```

Backend:

```bash
cd backend
uvicorn app.main:app --reload
```

Teste mínimo:
- A nova tela abre em `/dashboard/<slug>`
- Aparece no menu lateral (sidebar) e na home do dashboard
- O botão/ação chama `/api/<slug>`
- API interna chama backend sem erro 401/403
- Rate limit responde 429 quando excedido
- Resultado final aparece na UI

---

## 6) Deploy (Vercel + Railway)

1. Commit/push da branch com as mudanças
2. Verifique se Railway fez deploy do backend
3. Verifique se Vercel fez deploy do frontend
4. Se criou env vars novas, configurar:
   - Railway (backend)
   - Vercel (frontend)
5. Teste em produção:
   - Tela nova no dashboard
   - Fluxo completo funcionando

---

## 7) Modelo base para copiar

Use estas implementações como referência:

**Tradutor (JSON simples, sem upload):**
- Front: `src/app/dashboard/translate/page.tsx`
- API interna: `src/app/api/translate/route.ts`
- Back router: `backend/app/routers/translate.py`
- Back service: `backend/app/services/gemini_service.py`

**Extrator de Tabelas (upload de arquivo + download de Excel):**
- Front: `src/app/dashboard/pdf-extractor/page.tsx`
- API interna: `src/app/api/pdf/extract/route.ts`
- Back router: `backend/app/routers/pdf.py`
- Back service: `backend/app/services/pdf_extract_service.py`

**PDF para Word (upload + download de arquivo):**
- Front: `src/app/dashboard/pdf-converter/page.tsx`
- API interna: `src/app/api/pdf/convert/route.ts`
- Back router: `backend/app/routers/pdf.py`
- Back service: `backend/app/services/pdf_convert_service.py`

---

## 8) Estrutura de arquivos resumida

```
enghub-v2/
├── src/
│   ├── app/
│   │   ├── api/<slug>/route.ts          ← proxy seguro (criar)
│   │   ├── dashboard/
│   │   │   ├── layout.tsx               ← aplica <Shell> automaticamente (não mexer)
│   │   │   ├── page.tsx                 ← home do dashboard (adicionar ao array tools)
│   │   │   └── <slug>/page.tsx          ← página da ferramenta (criar)
│   │   └── layout.tsx                   ← root layout com ClerkProvider (não mexer)
│   ├── components/layout/
│   │   ├── shell.tsx                    ← wrapper Header+Sidebar+Content (não mexer)
│   │   ├── header.tsx                   ← header com menu mobile + UserButton (não mexer)
│   │   └── sidebar.tsx                  ← menu lateral (adicionar ao array menuItems)
│   └── lib/
│       └── backend.ts                   ← API_URL + buildBackendAuthHeaders (não mexer)
├── backend/
│   ├── app/
│   │   ├── main.py                      ← registrar router (include_router)
│   │   ├── config.py                    ← Settings com env vars
│   │   ├── models/schemas.py            ← todos os schemas Pydantic
│   │   ├── routers/<modulo>.py          ← router da nova app (criar)
│   │   ├── services/<modulo>_service.py ← lógica de negócio (criar)
│   │   └── dependencies/
│   │       ├── security.py              ← require_internal_api_key (não mexer)
│   │       └── rate_limit.py            ← adicionar enforce_<slug>_rate_limit
│   ├── requirements.txt                 ← adicionar dependências Python
│   └── .env.example                     ← adicionar novas env vars
├── .env.example                         ← env vars do frontend
└── Dockerfile (backend)
```
