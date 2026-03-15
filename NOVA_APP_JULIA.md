# Como Criar e Subir uma Nova App no Julia

Este guia mostra o fluxo padrão para adicionar uma nova aplicação ao Julia (como hoje já existe para Tradutor, Extrator de Tabelas e PDF para Word).

---

## Visão rápida da arquitetura

O Julia suporta **dois padrões** de backend, dependendo da complexidade da app:

### Padrão A — Router no backend central (apps simples)

Para apps leves (tradução, extração, conversão) que não precisam de banco próprio nem fila de tarefas:

```
Browser → Next.js Page (src/app/dashboard/<slug>/page.tsx)
              ↓ fetch("/api/<slug>")
         Next.js API Route (src/app/api/<slug>/route.ts)   ← Clerk auth + proxy seguro
              ↓ fetch(API_URL) com X-Internal-API-Key + X-User-Id
         FastAPI Backend (backend/app/routers/<modulo>.py)  ← require_internal_api_key
              ↓
         Service (backend/app/services/<modulo>_service.py)
```

**Exemplos**: Tradutor AI, Extrator de Tabelas, PDF para Word

### Padrão B — Microserviço separado (apps complexas)

Para apps que precisam de infraestrutura própria (PostgreSQL, Redis, Celery, migrations):

```
Browser → Next.js Page (src/app/dashboard/<slug>/page.tsx)
              ↓ fetch("/api/<slug>")
         Next.js API Route (src/app/api/<slug>/[...path]/route.ts)  ← Clerk auth + catch-all proxy
              ↓ fetch(SERVICE_URL) com X-Internal-API-Key + X-User-Id
         Microserviço (services/<nome>-backend/)  ← require_internal_api_key + banco próprio
```

**Exemplos**: Parecer Técnico (PATEC)

**Quando usar o Padrão B:**
- A app precisa de banco de dados relacional próprio (PostgreSQL)
- A app precisa de fila de tarefas assíncrona (Celery + Redis)
- A app tem mais de ~5 endpoints e domínio complexo
- A app já existia como sistema independente e está sendo integrada

### Elementos comuns a ambos os padrões

- Frontend (Next.js) renderiza a página em `src/app/dashboard/...`
- Frontend chama uma rota interna em `src/app/api/...` (proxy seguro)
- Rota interna valida o usuário com Clerk e envia para o Backend com:
  - `X-Internal-API-Key` (chave compartilhada entre front e back)
  - `X-User-Id` (ID do Clerk)
- Backend valida a chave, processa e responde
- O layout do dashboard é gerenciado pelo `Shell` (`src/components/layout/shell.tsx`), que inclui Header + Sidebar + conteúdo
- Ferramentas são registradas no `tools-registry.ts` (centraliza sidebar + dashboard + status)

---

## Checklist completo para nova app

## 1) Definir nome e rotas

Escolha um slug único para a nova app. Exemplo: `ocr`.

- Tela: `/dashboard/ocr`
- API interna Next.js: `/api/ocr`
- API backend: `/api/ocr` (ou `/api/nome-do-modulo`)

---

## 2) Backend (FastAPI)

### Padrão A — Router no backend central

#### 2.1 Criar/atualizar schemas

Arquivo: `backend/app/models/schemas.py`

Adicione o request/response da nova app com Pydantic. Exemplo:

```python
class OcrRequest(BaseModel):
    language: str = "pt"

class OcrResponse(BaseModel):
    text: str
    confidence: float
```

#### 2.2 Criar service

Pasta: `backend/app/services/`

Crie um service para a lógica de negócio (ex: `ocr_service.py`). Siga o padrão dos existentes:
- `backend/app/services/gemini_service.py` (tradução)
- `backend/app/services/pdf_extract_service.py` (extração PDF)
- `backend/app/services/pdf_convert_service.py` (conversão PDF)

#### 2.3 Criar router

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

#### 2.4 Criar rate limit (se necessário)

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

#### 2.5 Registrar router no app principal

Arquivo: `backend/app/main.py`

```python
from app.routers import translate, pdf, ocr

app.include_router(ocr.router, prefix="/api/ocr", tags=["OCR"])
```

#### 2.6 Dependências Python

Arquivo: `backend/requirements.txt`

Se a nova app precisar de bibliotecas extras, adicione ao `requirements.txt` seguindo o padrão de agrupamento com comentários:

```
# OCR Processing
pytesseract>=0.3.10
Pillow>=10.0.0
```

#### 2.7 Variáveis de ambiente

Arquivos:
- `backend/.env.example` — adicione as novas vars com valor placeholder
- `backend/.env` — configure com valores reais
- `backend/app/config.py` — adicione à classe `Settings`

---

### Padrão B — Microserviço separado

Para apps complexas com infraestrutura própria. Siga este padrão quando a app precisar de banco, fila, ou já existir como sistema independente.

#### 2B.1 Criar pasta do serviço

```
services/<nome>-backend/
├── app/
│   ├── main.py
│   ├── core/
│   │   ├── config.py          ← Settings com INTERNAL_API_KEY
│   │   ├── deps.py            ← require_internal_api_key + get_current_user com X-User-Id
│   │   ├── database.py
│   │   └── security.py
│   ├── api/v1/
│   │   ├── router.py          ← dependencies=[Depends(require_internal_api_key)]
│   │   └── endpoints/
│   ├── models/
│   ├── schemas/
│   └── services/
├── alembic/                   ← migrations (se usar banco)
├── Dockerfile
├── pyproject.toml
└── .env.example
```

#### 2B.2 Segurança obrigatória

O microserviço **deve** validar `X-Internal-API-Key` para não ficar exposto. No `config.py`:

```python
class Settings(BaseSettings):
    INTERNAL_API_KEY: str = ""  # Shared with Next.js proxy
    # ...
```

No `deps.py`:

```python
async def require_internal_api_key(request: Request) -> None:
    if not settings.INTERNAL_API_KEY:
        return  # Skip in local dev

    api_key = request.headers.get("x-internal-api-key", "")
    if api_key != settings.INTERNAL_API_KEY:
        raise HTTPException(status_code=403, detail="API Key inválida")
```

No `router.py`:

```python
api_router = APIRouter(dependencies=[Depends(require_internal_api_key)])
```

#### 2B.3 Mapeamento de usuário Clerk

O microserviço precisa mapear o `X-User-Id` do Clerk para um usuário local. No `deps.py`:

```python
async def get_current_user(
    x_user_id: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> Usuario:
    # 1. Try Clerk X-User-Id (from Noglem proxy)
    if x_user_id:
        return await _get_or_create_clerk_user(x_user_id, db)
    # 2. Fallback for local dev
    return await _get_or_create_direct_access_user(db)
```

#### 2B.4 Variáveis de ambiente no Railway

Configure no serviço do Railway:

```bash
railway service <nome>-api
railway variables --set "INTERNAL_API_KEY=<mesma chave do frontend>"
railway variables --set "DATABASE_URL=${{Postgres.DATABASE_URL}}"
# ... outras vars específicas
```

#### 2B.5 Variável de URL no frontend (Vercel)

Configure na Vercel:

```
<NOME>_API_URL=https://<nome>-api-production-xxx.up.railway.app
```

E no proxy do Next.js, use essa variável:

```typescript
const SERVICE_URL = process.env.<NOME>_API_URL || "http://localhost:8000";
```

---

## 3) Frontend (Next.js)

### 3.1 Registrar no tools-registry

Arquivo: `src/lib/tools-registry.ts`

Adicione a nova ferramenta ao array `tools`:

```typescript
{
  id: "ocr",
  title: "OCR",
  description: "Extraia texto de imagens com IA",
  icon: ScanText,             // do lucide-react
  href: "/dashboard/ocr",
  category: "documentacao",   // documentacao | conhecimento | analise | instrumentacao
  status: "beta",             // live | beta | coming_soon
},
```

Isso automaticamente:
- Adiciona ao menu lateral (sidebar)
- Adiciona ao dashboard com badge de status
- Desabilita o link se `coming_soon`

### 3.2 Criar rota API interna (proxy)

#### Padrão A — Proxy simples

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

#### Padrão B — Proxy catch-all (microserviço)

Arquivo: `src/app/api/<slug>/[...path]/route.ts`

Para serviços com muitas rotas, use um catch-all que redireciona tudo:

```typescript
import { NextRequest, NextResponse } from "next/server";
import { auth } from "@clerk/nextjs/server";

const SERVICE_URL = process.env.<NOME>_API_URL || "http://localhost:8000";
const INTERNAL_API_KEY = process.env.INTERNAL_API_KEY || "";

async function handler(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  try {
    const { userId } = await auth();
    if (!userId) {
      return NextResponse.json({ error: "Não autorizado" }, { status: 401 });
    }

    const { path: pathSegments } = await params;
    const path = pathSegments.join("/");
    const searchParams = request.nextUrl.searchParams.toString();
    const url = `${SERVICE_URL}/api/${path}${searchParams ? `?${searchParams}` : ""}`;

    const headers: Record<string, string> = {
      "X-User-Id": userId,
      ...(INTERNAL_API_KEY && { "X-Internal-API-Key": INTERNAL_API_KEY }),
    };

    const contentType = request.headers.get("content-type");
    if (contentType && !contentType.includes("multipart/form-data")) {
      headers["Content-Type"] = contentType;
    }

    const response = await fetch(url, {
      method: request.method,
      headers,
      body: request.method !== "GET" && request.method !== "HEAD" ? request.body : undefined,
    });

    // Handle SSE streaming
    if (response.headers.get("content-type")?.includes("text/event-stream")) {
      return new NextResponse(response.body, {
        headers: { "Content-Type": "text/event-stream", "Cache-Control": "no-cache", Connection: "keep-alive" },
      });
    }

    // Handle file downloads
    const respContentType = response.headers.get("content-type") || "";
    if (respContentType.includes("application/pdf") || respContentType.includes("application/vnd.openxmlformats") || respContentType.includes("application/octet-stream")) {
      return new NextResponse(response.body, {
        headers: { "Content-Type": respContentType, "Content-Disposition": response.headers.get("Content-Disposition") || "attachment" },
      });
    }

    if (response.status === 204) return new NextResponse(null, { status: 204 });
    if (!response.ok) {
      const errorText = await response.text();
      try { return NextResponse.json(JSON.parse(errorText), { status: response.status }); }
      catch { return NextResponse.json({ detail: errorText }, { status: response.status }); }
    }

    return NextResponse.json(await response.json());
  } catch (error) {
    console.error(`Proxy Error [${request.method}]:`, error);
    return NextResponse.json({ error: "Erro de comunicação com o backend." }, { status: 503 });
  }
}

export { handler as GET, handler as POST, handler as PUT, handler as DELETE };
```

#### Padrão B — API Client (opcional, recomendado)

Para microserviços com muitas rotas, crie um client tipado em `src/lib/<nome>-api.ts`:

```typescript
async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/<slug>${endpoint}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...options.headers },
  });
  if (!response.ok) throw new Error(`Erro ${response.status}`);
  return response.json();
}

export const myApi = {
  items: {
    list: () => request<Item[]>("/v1/items"),
    get: (id: string) => request<Item>(`/v1/items/${id}`),
    create: (data: CreateItem) => request<Item>("/v1/items", { method: "POST", body: JSON.stringify(data) }),
  },
};
```

### 3.3 Criar página da ferramenta

Pasta: `src/app/dashboard/<slug>/page.tsx`

- Crie o layout e fluxo da tela
- Chame a API interna (`/api/<slug>`) com `fetch` — nunca o backend direto
- O layout (Header + Sidebar) já é aplicado automaticamente pelo `src/app/dashboard/layout.tsx` via `<Shell>`

#### Componentes específicos (se necessário)

Para apps complexas, crie uma pasta de componentes dedicada:

```
src/components/<slug>/
├── workspace-context.tsx    ← state management centralizado
├── workspace-layout.tsx     ← layout principal
├── item-list-panel.tsx      ← painéis específicos
└── ...
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
- **Padrão A**: O helper `buildBackendAuthHeaders` (em `src/lib/backend.ts`) monta os headers:
  - `X-Internal-API-Key` — chave compartilhada
  - `X-User-Id` — ID do Clerk
  - `Content-Type: application/json` — apenas quando `includeJsonContentType = true`
- **Padrão B**: Construa os headers manualmente no catch-all proxy, incluindo `X-Internal-API-Key` e `X-User-Id`
- `INTERNAL_API_KEY` deve ser **o mesmo valor** no frontend e em todos os backends/serviços
- Todos os backends devem validar `X-Internal-API-Key` antes de processar requisições da API

---

## 5) Teste local antes de deploy

Frontend:

```bash
npm run dev
```

Backend (Padrão A):

```bash
cd backend
uvicorn app.main:app --reload
```

Backend (Padrão B):

```bash
cd services/<nome>-backend
# Iniciar PostgreSQL + Redis (docker-compose ou local)
uvicorn app.main:app --reload --port 8001
# Se usar Celery: celery -A app.worker worker --loglevel=info
```

Teste mínimo:
- A nova tela abre em `/dashboard/<slug>`
- Aparece no menu lateral (sidebar) e na home do dashboard (via tools-registry)
- O botão/ação chama `/api/<slug>`
- API interna chama backend sem erro 401/403
- Rate limit responde 429 quando excedido (se aplicável)
- Resultado final aparece na UI

---

## 6) Deploy (Vercel + Railway)

### Padrão A:
1. Commit/push da branch com as mudanças
2. Verifique se Railway fez deploy do backend
3. Verifique se Vercel fez deploy do frontend
4. Se criou env vars novas, configurar:
   - Railway (backend)
   - Vercel (frontend)
5. Teste em produção

### Padrão B:
1. Commit/push da branch com as mudanças
2. No Railway, criar novo projeto para o microserviço:
   ```bash
   cd services/<nome>-backend
   railway init --name "<nome>-backend"
   railway add -d postgres    # se precisar de banco
   railway add -d redis       # se precisar de fila
   railway add -s "<nome>-api"
   railway service <nome>-api
   railway variables --set "INTERNAL_API_KEY=<mesma chave>" \
     --set "DATABASE_URL=${{Postgres.DATABASE_URL}}" \
     --set "REDIS_URL=${{Redis.REDIS_URL}}"
   railway up                 # deploy via Dockerfile
   ```
3. Copiar a URL pública do serviço no Railway
4. Na Vercel, adicionar a env var: `<NOME>_API_URL=https://...railway.app`
5. Verifique se Vercel fez deploy do frontend
6. Teste em produção

---

## 7) Modelos de referência

### Padrão A — Apps simples (router no backend central)

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

### Padrão B — Apps complexas (microserviço separado)

**Parecer Técnico (PATEC) — workspace 3-painéis, chat IA, PostgreSQL + Celery:**
- Front pages: `src/app/dashboard/parecer-tecnico/` (listagem, novo, workspace `[id]`)
- Front components: `src/components/parecer-tecnico/` (~20 componentes)
- API client: `src/lib/patec-api.ts` (client tipado com todos os endpoints)
- API proxy: `src/app/api/parecer-tecnico/[...path]/route.ts` (catch-all)
- Back: `services/patec-backend/` (FastAPI completo com Dockerfile)
- Infra: PostgreSQL + Redis no Railway (projeto separado)
- Env var Vercel: `PATEC_API_URL`

---

## 8) Estrutura de arquivos resumida

```
enghub-v2/
├── src/
│   ├── app/
│   │   ├── api/
│   │   │   ├── <slug>/route.ts                  ← proxy simples (Padrão A)
│   │   │   └── <slug>/[...path]/route.ts        ← proxy catch-all (Padrão B)
│   │   ├── dashboard/
│   │   │   ├── layout.tsx                        ← aplica <Shell> automaticamente (não mexer)
│   │   │   ├── page.tsx                          ← home do dashboard (não mexer — usa tools-registry)
│   │   │   └── <slug>/page.tsx                   ← página da ferramenta (criar)
│   │   └── layout.tsx                            ← root layout com ClerkProvider (não mexer)
│   ├── components/
│   │   ├── layout/
│   │   │   ├── shell.tsx                         ← wrapper Header+Sidebar+Content (não mexer)
│   │   │   ├── header.tsx                        ← header com menu mobile + UserButton (não mexer)
│   │   │   └── sidebar.tsx                       ← menu lateral (não mexer — usa tools-registry)
│   │   └── <slug>/                               ← componentes específicos da app (Padrão B)
│   └── lib/
│       ├── backend.ts                            ← API_URL + buildBackendAuthHeaders (Padrão A)
│       ├── tools-registry.ts                     ← registro centralizado de ferramentas (adicionar aqui)
│       └── <slug>-api.ts                         ← API client tipado (Padrão B)
├── backend/                                      ← backend central (Padrão A)
│   ├── app/
│   │   ├── main.py                               ← registrar router (include_router)
│   │   ├── config.py                             ← Settings com env vars
│   │   ├── models/schemas.py                     ← todos os schemas Pydantic
│   │   ├── routers/<modulo>.py                   ← router da nova app (criar)
│   │   ├── services/<modulo>_service.py          ← lógica de negócio (criar)
│   │   └── dependencies/
│   │       ├── security.py                       ← require_internal_api_key (não mexer)
│   │       └── rate_limit.py                     ← adicionar enforce_<slug>_rate_limit
│   ├── requirements.txt                          ← adicionar dependências Python
│   └── .env.example                              ← adicionar novas env vars
├── services/                                     ← microserviços separados (Padrão B)
│   └── <nome>-backend/
│       ├── app/                                  ← estrutura FastAPI completa
│       ├── alembic/                              ← migrations
│       ├── Dockerfile                            ← deploy independente
│       └── pyproject.toml
├── .env.example                                  ← env vars do frontend
└── Dockerfile (backend central)
```
