# Worker COTAI

Worker Python da Cotai preparado para operar com requests internos persistidos no Supabase.

## Papel atual do worker

O worker nao depende mais do WhatsApp como fluxo principal.

Responsabilidades atuais:

1. Buscar requests pendentes no banco.
2. Fazer claim seguro da execucao.
3. Criar e atualizar `request_quotes`.
4. Buscar ofertas via snapshots persistidos, catalogo local e Mercado Livre.
5. Salvar `quote_results`.
6. Consolidar resposta final com Groq ou fallback local.
7. Atualizar status do request.
8. Publicar resposta final em `chat_messages` quando o request vier do chatbot interno.

## Comandos

Bootstrap:

```bash
python -m backend.worker.bootstrap
```

Worker:

```bash
python -m backend.worker.main
```

Coletor de precos:

```bash
python -m backend.worker.collect_prices
```

Health check:

```bash
python -m backend.worker.main healthcheck
```

Teste local:

```bash
python -m unittest backend.tests.test_worker
```
