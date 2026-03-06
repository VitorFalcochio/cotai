# Cotai

Projeto reorganizado para separar frontend, backend, configuracao, dados e documentacao.

## Estrutura

```text
backend/
  agent.py
  state.json
  worker/
  waha/

frontend/
  pages/
    index.html
    login.html
    signup.html
    dashboard.html
    new-request.html
    requests.html
    suppliers.html
    materials.html
    plans.html
    settings.html
  assets/
    css/
      styles.css
    js/
      app.js
      script.js
      config.js
      auth.js
      requests.js
      supabaseClient.js
      ui.js
      pages/
        login.page.js
        signup.page.js
        dashboard.page.js
        new-request.page.js
        requests.page.js

config/
  .env
  .env.example

data/
  catalog.json
  state.json

docs/
  README.md

requirements.txt
.gitignore
```

## Como rodar

Frontend:

```bash
python -m http.server 5500
```

Abra:

```text
http://localhost:5500/frontend/pages/login.html
```

Backend:

```bash
python backend/agent.py
```

Bootstrap do worker:

```bash
python -m backend.worker.bootstrap
```

## Configuracao do frontend

Edite [config.js](/c:/Users/vitin/Desktop/cotai/cotaiedit/frontend/assets/js/config.js):

```js
export const SUPABASE_URL = "https://SEU_PROJECT_REF.supabase.co";
export const SUPABASE_ANON_KEY = "SUA_CHAVE_PUBLICA";
```

Use apenas `SUPABASE_URL` e `SUPABASE_ANON_KEY` no frontend.

## Configuracao do backend

As variaveis do backend ficam em [config/.env](/c:/Users/vitin/Desktop/cotai/cotaiedit/config/.env). O `agent.py` agora carrega esse arquivo diretamente.

Documentacao especifica do worker:

- [backend/worker/README.md](/c:/Users/vitin/Desktop/cotai/cotaiedit/backend/worker/README.md)
- Migration principal do worker:
  [supabase/migrations/20260306_001_request_quotes_and_worker_processed_messages.sql](/c:/Users/vitin/Desktop/cotai/cotaiedit/supabase/migrations/20260306_001_request_quotes_and_worker_processed_messages.sql)

Arquivos de runtime:

- Estado principal do agente: [backend/state.json](/c:/Users/vitin/Desktop/cotai/cotaiedit/backend/state.json)
- Dados/catalogo: [data/catalog.json](/c:/Users/vitin/Desktop/cotai/cotaiedit/data/catalog.json)
- Copia de estado em dados: [data/state.json](/c:/Users/vitin/Desktop/cotai/cotaiedit/data/state.json)

## Ajustes de caminho feitos

- HTML movido para `frontend/pages`
- CSS movido para `frontend/assets/css/styles.css`
- JS compartilhado movido para `frontend/assets/js`
- Scripts de pagina movidos para `frontend/assets/js/pages`
- `agent.py` movido para `backend/agent.py`
- `.env` e `.env.example` movidos para `config`
- Migrations Supabase em `supabase/migrations`

## Redirecionamentos

Os redirecionamentos `login.html -> dashboard.html` continuam relativos dentro de `frontend/pages`, entao seguem funcionando sem alteracao de comportamento.

## Supabase schema

Para o painel admin e o worker funcionarem com o schema esperado, aplique:

- [20260306_001_request_quotes_and_worker_processed_messages.sql](/c:/Users/vitin/Desktop/cotai/cotaiedit/supabase/migrations/20260306_001_request_quotes_and_worker_processed_messages.sql)
- [20260306_002_core_saas_schema.sql](/c:/Users/vitin/Desktop/cotai/cotaiedit/supabase/migrations/20260306_002_core_saas_schema.sql)
- [20260306_003_admin_audit_logs.sql](/c:/Users/vitin/Desktop/cotai/cotaiedit/supabase/migrations/20260306_003_admin_audit_logs.sql)

A segunda migration cria ou completa as tabelas principais:

- `companies`
- `profiles`
- `requests`
- `request_items`
- `quote_results`
- `request_quotes`
- `worker_processed_messages`
- `worker_heartbeats`
- `billing_subscriptions`
- `admin_audit_logs`
