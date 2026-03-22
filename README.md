# Cotai

Software de cotacao e comparacao de materiais com frontend estatico em HTML/CSS/JS, Supabase para auth/dados, API FastAPI e worker Python.

## Prioridade atual

O produto esta em modo de consolidacao. O foco principal agora e:

- cotar materiais com clareza
- comparar fornecedores com rapidez
- dar historico e decisao sem poluicao visual

As telas mais importantes neste momento sao:

- `frontend/pages/dashboard.html`
- `frontend/pages/new-request.html`
- `frontend/pages/requests.html`
- `frontend/pages/admin-dashboard.html`
- `frontend/pages/admin-requests.html`
- `frontend/pages/admin-worker.html`

## Fluxo principal

1. Usuario autentica via Supabase.
2. Abre `frontend/pages/new-request.html`.
3. Descreve o pedido para a Cota em linguagem natural.
4. A API interpreta a mensagem, pede confirmacao e cria `requests` + `request_items`.
5. O worker processa a fila, compara fornecedores e grava resultados.
6. O resultado volta para o chat, historico e admin core.

## Stack

- `frontend/`: HTML, CSS e JavaScript puro
- `backend/api/`: FastAPI
- `backend/worker/`: worker Python
- `supabase/`: schema e migrations
- `data/catalog.json`: catalogo local
- `data/price_sources.json`: watchlist de fontes

## Como rodar

Frontend:

```bash
python -m http.server 5500
```

API:

```bash
python -m uvicorn backend.api.main:app --reload --host 127.0.0.1 --port 8000
```

Worker:

```bash
python -m backend.worker.main
```

Testes:

```bash
python -m unittest discover -s backend\tests -v
```

Checagens urgentes ja tratadas no fluxo principal:

- `request_code` agora usa identificador com sufixo aleatorio e retry em caso de colisao no banco
- o fluxo principal de chat, confirmacao, pedido e worker fica coberto pela suite em `backend/tests`

## Deploy

O caminho recomendado de publicacao hoje esta em:

- [docs/deploy.md](C:/Users/vitin/Desktop/cotai/cotaiedit/docs/deploy.md)

Resumo:

- `frontend` no `Vercel`
- `backend API` no `Railway` com `Dockerfile.api`
- `worker` no `Railway` com `Dockerfile.worker`
- `Supabase` como banco e auth

## O que fica para depois

Modulos laterais continuam existindo, mas estao despriorizados temporariamente:

- alerts
- analytics
- approvals
- comparisons
- price-book
- expansoes visuais e widgets secundarios
