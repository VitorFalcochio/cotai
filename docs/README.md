# Cotai

Hub inteligente de compras para construcao civil, evoluido sobre a base original de cotacao com frontend estatico, Supabase, FastAPI e worker Python.

## Arquitetura atual

- `frontend/`: app estatico em HTML/CSS/JS
- `backend/api/`: API FastAPI do chatbot interno
- `backend/worker/`: motor de cotacao
- `supabase/`: migrations e schema principal
- `data/catalog.json`: catalogo local para cotacao
- `data/price_sources.json`: watchlist automatica de consultas de preco

## Fluxo principal

1. Usuario autentica via Supabase.
2. Abre `frontend/pages/new-request.html`.
3. Conversa com o chatbot interno da Cotai.
4. A API interpreta a mensagem, extrai itens e pede confirmacao.
5. Ao confirmar, a API cria `requests` e `request_items` direto no Supabase.
6. O coletor abastece `supplier_price_snapshots` com capturas automatizadas e o worker busca requests pendentes, cota os itens, enriquece `quote_results`, atualiza fornecedores, registra `price_history` e persiste `request_quotes`.
7. O resultado final volta para o proprio chat e tambem aparece no historico/admin, com comparador inteligente, economia potencial e exportacao.

## Prioridade de produto agora

O Cotai entrou em modo de consolidacao.

O objetivo principal e fazer muito bem a tarefa central:

- cotar materiais com clareza
- comparar fornecedores com rapidez
- registrar historico util para decisao

Por isso, o foco principal agora esta nas telas:

- `frontend/pages/dashboard.html`
- `frontend/pages/new-request.html`
- `frontend/pages/requests.html`
- `frontend/pages/admin-dashboard.html`
- `frontend/pages/admin-requests.html`
- `frontend/pages/admin-worker.html`

## Capacidades adicionadas

- Comparador inteligente por cotacao com melhor preco, prazo e melhor opcao geral.
- Dashboard de valor com economia estimada, tempo ganho, fornecedores consultados e projetos ativos.
- Historico inteligente com top materiais, fornecedores recorrentes, tendencia inicial de preco e comparacao entre pedidos.
- Base de fornecedores estruturada com rollups, reviews e participacao em cotacoes.
- Avaliacao de fornecedores por preco, prazo, atendimento e confiabilidade.
- Exportacao profissional via CSV e layout de impressao para PDF.
- Assistente de cotacao orientado a tarefa no fluxo `new-request`.
- Estimativa inicial de materiais para piso, parede, laje e area.
- Preparacao para planejamento por obra/projeto e historico de precos.
- Admin mais estrategico com alertas, SLA, duplicidade, taxa de sucesso, fornecedores mapeados e volume por empresa.

## Como rodar

### 1. Frontend

```bash
python -m http.server 5500
```

Abra:

```text
http://localhost:5500/frontend/pages/login.html
```

### 2. API do chatbot

```bash
python -m uvicorn backend.api.main:app --reload --host 127.0.0.1 --port 8000
```

### 3. Worker

```bash
python -m backend.worker.main
```

### 4. Bootstrap do worker

```bash
python -m backend.worker.bootstrap
```

## Configuracao do frontend

Edite `frontend/assets/js/config.js`:

- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `API_BASE_URL`

## Configuracao do backend

Variaveis em `config/.env`.

Principais:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `GROQ_API_KEY`
- `API_HOST`
- `API_PORT`
- `API_BASE_URL`

## Migrations obrigatorias

Aplique em ordem:

- `supabase/migrations/20260306_001_request_quotes_and_worker_processed_messages.sql`
- `supabase/migrations/20260306_002_core_saas_schema.sql`
- `supabase/migrations/20260306_003_admin_audit_logs.sql`
- `supabase/migrations/20260306_004_internal_chatbot.sql`
- `supabase/migrations/20260307_005_request_ops_upgrade.sql`
- `supabase/migrations/20260307_006_procurement_intelligence.sql`

## Tabelas principais

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
- `chat_threads`
- `chat_messages`
- `suppliers`
- `supplier_reviews`
- `projects`
- `project_materials`
- `price_history`
- `supplier_price_snapshots`

## Modulos e telas-chave

- `frontend/pages/dashboard.html`: dashboard executivo do cliente.
- `frontend/pages/new-request.html`: assistente interno de cotacao, estimativa e confirmacao.
- `frontend/pages/requests.html`: historico inteligente, comparador e reviews.
- `frontend/pages/suppliers.html`: base estruturada de fornecedores.
- `frontend/pages/admin-dashboard.html`: operacao e inteligencia da plataforma.
- `frontend/assets/js/procurementData.js`: agregacao de dados de compras, economia e tendencias.
- `frontend/assets/js/quoteExport.js`: exportacao CSV e relatorio para impressao/PDF.

## Testes

```bash
python -m unittest backend.tests.test_worker backend.tests.test_api
```

## Observacoes

- O worker foi refatorado para atuar como motor de cotacao.
- O painel admin e o historico continuam baseados nas mesmas tabelas principais, agora enriquecidas com inteligencia operacional.
- O PDF atual usa layout de impressao do navegador; a base ficou pronta para evoluir depois para geracao server-side.
- As tabelas novas sao opcionais em desenvolvimento local, mas devem existir para liberar a experiencia completa.

## Despriorizado temporariamente

As areas abaixo continuam disponiveis, mas nao devem disputar foco com o nucleo do produto nesta fase:

- `alerts`
- `analytics`
- `approvals`
- `comparisons`
- `price-book`
- widgets e paines secundarios fora do fluxo principal
