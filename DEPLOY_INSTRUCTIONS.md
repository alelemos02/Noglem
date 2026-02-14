# Deploy Instructions - Julia v2

Essas instruções foram geradas automaticamente para facilitar o deploy da aplicação.

## 1. Segurança e Rotação de Chaves

**IMPORTANTE:** O arquivo `.env.local` foi removido do Git, mas suas versões anteriores contendo chaves reais ainda estão no histórico.

**Ação Necessária:**
1. Acesse o painel do [Clerk Dashboard](https://dashboard.clerk.com/) e gere novas chaves (`Publishable Key` e `Secret Key`) para o ambiente de Produção.
2. Acesse o [Google AI Studio](https://aistudio.google.com/) e gere uma nova API Key.
3. Use a `INTERNAL_API_KEY` gerada abaixo para a comunicação segura entre Frontend e Backend.

### Chave Interna Gerada Segura
Copie este valor exato para ambos os ambientes (Vercel e Railway):
```
a1246d7e32ca34a567882f833f13c2c48a22d49d575319b3c20b897883a2b432
```

---

## 2. Configuração do Backend (Railway)

1. Crie um novo projeto no [Railway](https://railway.app/).
2. Conecte ao seu repositório GitHub.
3. Configure o diretório raiz (Root Directory) como `backend`.
4. Configure as Variáveis de Ambiente:

| Variável | Valor | Descrição |
|---|---|---|
| `GOOGLE_API_KEY` | *(Sua nova chave do Google)* | API do Gemini |
| `INTERNAL_API_KEY` | `a1246d7e32ca34a567882f833f13c2c48a22d49d575319b3c20b897883a2b432` | Chave de segurança interna |
| `UPLOAD_DIR` | `/tmp/julia-uploads` | Diretório temporário |
| `OUTPUT_DIR` | `/tmp/julia-outputs` | Diretório temporário |
| `RATE_LIMIT_TRANSLATE_PER_MIN` | `30` | Limite de traduções |
| `RATE_LIMIT_PDF_PER_MIN` | `5` | Limite de processamento de PDF |
| `PORT` | `8000` | Porta do serviço |

5. O deploy deve iniciar automaticamente.
6. **Copie a URL pública do serviço** (ex: `https://julia-backend-production.up.railway.app`).

---

## 3. Configuração do Frontend (Vercel)

1. Crie um novo projeto na [Vercel](https://vercel.com/).
2. Importe o mesmo repositório GitHub.
3. Certifique-se de que o **Root Directory** está como `./` (raiz).
4. O **Framework Preset** deve ser `Next.js`.
5. Configure as Variáveis de Ambiente:

| Variável | Valor | Descrição |
|---|---|---|
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | `pk_test_cHJlc2VudC1nYXJmaXNoLTgzLmNsZXJrLmFjY291bnRzLmRldiQ` | Chave pública (Dev) |
| `CLERK_SECRET_KEY` | `sk_test_xPXCwykExEY05CSIhAc5aYc6YJ8tPE3lXC0dw8gOpj` | Chave secreta (Dev) |
| `NEXT_PUBLIC_CLERK_SIGN_IN_URL` | `/sign-in` | Rota de login |
| `NEXT_PUBLIC_CLERK_SIGN_UP_URL` | `/sign-up` | Rota de cadastro |
| `NEXT_PUBLIC_API_URL` | *(URL do Railway, sem a barra final)* | Ex: `https://julia-backend.up.railway.app` |
| `INTERNAL_API_KEY` | `a1246d7e32ca34a567882f833f13c2c48a22d49d575319b3c20b897883a2b432` | Chave de segurança interna |

6. Faça o Deploy.

---

## 4. Configuração de DNS (Após Deploys com Sucesso)

No painel do seu registrador de domínio (`noglem.com.br`):

1. **Frontend (www):**
   - Tipo: `CNAME`
   - Nome: `www`
   - Valor: `cname.vercel-dns.com`

2. **Backend (api):**
   - Tipo: `CNAME`
   - Nome: `api`
   - Valor: *(URL do Railway sem https://)* (Ex: `julia-backend.up.railway.app`)
   - *Nota: Você precisará configurar o domínio customizado (api.noglem.com.br) no painel do Railway primeiro.*

3. **Raiz (@):**
   - Configure um redirecionamento (301) de `noglem.com.br` para `https://www.noglem.com.br`.

---

## 5. Limpeza de Histórico Git (Opcional)

Se desejar remover completamente as chaves antigas do histórico do Git, execute os comandos abaixo no terminal local. **Cuidado: Isso reescreve o histórico.**

```bash
# Cria uma branch temporária órfã (sem histórico)
git checkout --orphan temp_branch

# Adiciona todos os arquivos atuais
git add -A

# Comita o estado atual limpo
git commit -am "Initial commit (Clean history)"

# Deleta a branch main antiga
git branch -D main

# Renomeia a branch atual para main
git branch -m main

# Força o envio para o GitHub (sobrescreve o histórico remoto)
git push -f origin main
```
