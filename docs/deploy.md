# Deploy do Cotai

Este guia sobe o Cotai com:

- `frontend` no `Vercel`
- `backend API` no `Railway`
- `worker` no `Railway`
- `Supabase` como banco e auth

## Arquitetura recomendada

- `Vercel`
  Hospeda o frontend estatico gerado em `frontend-dist/`.

- `Railway service 1`
  Roda a API FastAPI com `Dockerfile.api`.

- `Railway service 2`
  Roda o worker com `Dockerfile.worker`.

- `Supabase`
  Continua como origem de dados, auth e snapshots.

## 1. Preparar secrets

Antes de publicar, tenha em maos:

- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `GROQ_API_KEY`
- `GEMINI_API_KEY`
- `WORKER_COMPANY_ID`

Se a chave do Gemini usada no projeto foi exposta fora do ambiente seguro, gere outra antes do deploy.

## 2. Subir o backend no Railway

Crie um novo projeto no Railway e conecte este repositorio.

### Service: API

Configure o service para usar o arquivo:

- `Dockerfile.api`

Defina estas variaveis:

```env
DEBUG=0
API_HOST=0.0.0.0
API_PORT=8000
SUPABASE_URL=...
SUPABASE_SERVICE_ROLE_KEY=...
SUPABASE_SCHEMA=public
GROQ_API_KEY=...
GROQ_MODEL=llama-3.1-8b-instant
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-2.5-flash
SEARCH_CACHE_TTL_SECONDS=86400
SCRAPING_HEADLESS=1
SCRAPING_TIMEOUT_MS=20000
SCRAPING_MAX_OFFERS_PER_STORE=6
CORS_ORIGINS=https://SEU-FRONTEND.vercel.app,http://localhost:5500
```

Depois do deploy, anote a URL publica da API, por exemplo:

- `https://cotai-api-production.up.railway.app`

### Service: Worker

No mesmo projeto Railway, crie outro service apontando para o mesmo repositorio.

Configure para usar:

- `Dockerfile.worker`

Defina estas variaveis:

```env
DEBUG=0
SUPABASE_URL=...
SUPABASE_SERVICE_ROLE_KEY=...
SUPABASE_SCHEMA=public
WORKER_COMPANY_ID=...
API_BASE_URL=https://cotai-api-production.up.railway.app
GROQ_API_KEY=...
GROQ_MODEL=llama-3.1-8b-instant
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-2.5-flash
POLL_SECONDS=10
REQUESTS_PER_CYCLE=10
HEARTBEAT_SECONDS=60
SCRAPING_HEADLESS=1
SCRAPING_TIMEOUT_MS=20000
SCRAPING_MAX_OFFERS_PER_STORE=6
```

## 3. Subir o frontend no Vercel

Crie um projeto no Vercel conectado ao mesmo repositorio.

O projeto ja tem:

- `vercel.json`
- `scripts/write-runtime-config.mjs`
- `scripts/build-frontend-dist.mjs`

Esses arquivos geram o build estatico pronto para publicacao.

### Variaveis de ambiente do Vercel

Defina:

```env
COTAI_API_BASE_URL=https://cotai-api-production.up.railway.app
COTAI_SUPABASE_URL=https://SEU-PROJETO.supabase.co
COTAI_SUPABASE_ANON_KEY=...
COTAI_WHATSAPP_NUMBER=5517996657737
```

O build do Vercel vai escrever esses valores em:

- `frontend/assets/js/runtime-config.js`

## 4. Validar em producao

Depois dos 3 deploys:

1. Abra o frontend no Vercel.
2. Faca login.
3. Teste o health da API:
   - `https://SUA-API/health`
4. Envie uma mensagem no chat da Cota.
5. Verifique se o worker esta consumindo a fila.
6. Valide:
   - nova cotacao
   - modo construcao
   - pedidos
   - suppliers
   - materials

## 5. Checklist minimo

- `Supabase` com migrations aplicadas
- `API` respondendo `/health`
- `Worker` rodando sem erro de environment
- `Vercel` com `COTAI_API_BASE_URL` correto
- `CORS_ORIGINS` da API incluindo o dominio do frontend
- `GEMINI_API_KEY` e `GROQ_API_KEY` validas

## 6. Comandos uteis locais

Gerar config de frontend:

```bash
node scripts/write-runtime-config.mjs
```

Gerar dist estatica:

```bash
node scripts/build-frontend-dist.mjs
```

Testar backend principal:

```bash
python -m unittest backend.tests.test_construction_mode_service backend.tests.test_parametric_budget_service backend.tests.test_dynamic_quote_service backend.tests.test_dynamic_search_engine backend.tests.test_collect_prices backend.tests.test_worker
```

## Observacoes

- O scraping com Playwright nunca e imune a mudancas de layout dos sites externos.
- O worker deve ficar separado da API para nao competir por CPU e memoria.
- Se quiser um deploy ainda mais robusto depois, o proximo passo natural e migrar `API + worker` para um VPS Linux com observabilidade e processo supervisor.
