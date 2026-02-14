# Julia v2

Plataforma centralizada de ferramentas de engenharia.

## Stack

- **Frontend:** Next.js 14, React, TypeScript, Tailwind CSS, shadcn/ui
- **Auth:** Clerk
- **Backend:** FastAPI, Python 3.11
- **Deploy:** Vercel (frontend) + Railway (backend)

## Estrutura

```
julia/
├── src/                    # Frontend Next.js
│   ├── app/
│   │   ├── dashboard/      # Páginas protegidas
│   │   ├── sign-in/        # Login (Clerk)
│   │   └── sign-up/        # Cadastro (Clerk)
│   └── components/
│       ├── layout/         # Header, Sidebar, Shell
│       └── ui/             # shadcn/ui components
├── backend/                # API FastAPI
│   ├── app/
│   │   ├── routers/        # Endpoints
│   │   ├── services/       # Lógica de negócio
│   │   └── models/         # Schemas Pydantic
│   ├── Dockerfile
│   └── requirements.txt
└── package.json
```

## Configuração

### 1. Frontend

```bash
# Instalar dependências
npm install

# Configurar variáveis de ambiente
# Edite .env.local com suas chaves do Clerk

# Executar em desenvolvimento
npm run dev
```

### 2. Backend

```bash
cd backend

# Criar ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou: venv\Scripts\activate  # Windows

# Instalar dependências
pip install -r requirements.txt

# Configurar variáveis de ambiente
cp .env.example .env
# Edite .env com sua GOOGLE_API_KEY

# Executar em desenvolvimento
uvicorn app.main:app --reload
```

## Configuração do Clerk

1. Crie uma conta em [clerk.com](https://clerk.com)
2. Crie uma nova aplicação
3. Copie `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` e `CLERK_SECRET_KEY`
4. Cole no arquivo `.env.local`

## Features

| Feature | Status | Descrição |
|---------|--------|-----------|
| Tradutor AI | Live | Tradução com Google Gemini |
| Extrator de Tabelas | Beta | Extrai tabelas de PDFs para Excel |
| PDF para Word | Beta | Converte PDFs para DOCX |
| RAG Chat | Dev | Chat com documentos (em desenvolvimento) |

## Deploy

### Frontend (Vercel)

```bash
vercel deploy
```

### Backend (Railway)

1. Conecte o repositório ao Railway
2. Configure as variáveis de ambiente
3. Deploy automático via push
