# Worker COTAI

Worker Python do COTAI preparado para operacao SaaS com Supabase, WAHA e fallback local para IA/busca.

## Diagnostico do worker legado

- Configs sensiveis e operacionais misturadas em um arquivo monolitico.
- Dedupe dependente de `state.json`, sem fonte de verdade no banco.
- Polling do WAHA sem rastreamento completo de execucao.
- Sem tabela de execucao de cotacao; historico ficava misturado com estado local.
- Google Sheets e dependencias do MVP antigo ainda apareciam como heranca operacional.
- Falta de health check, bootstrap e verificacao de schema antes de rodar em producao.

## Estrutura

```text
backend/worker/
  bootstrap.py
  config.py
  main.py
  README.md
  services/
    ai_service.py
    dedupe_service.py
    search_service.py
    supabase_service.py
    whatsapp.py
    whatsapp_service.py
  utils/
    hashing.py
    logger.py
    retry.py
```

## Fluxo operacional

1. O worker le mensagens do WAHA.
2. Extrai `message_id` e valida dedupe em `worker_processed_messages`.
3. Registra ou atualiza o `request` no Supabase.
4. Insere o dedupe persistente da mensagem.
5. Busca requests pendentes (`NEW` e `RECEIVED`).
6. Faz claim do request e cria uma execucao em `request_quotes`.
7. Busca resultados em catalogo local e Mercado Livre como fallback.
8. Grava resultados individuais em `quote_results`.
9. Atualiza a execucao em `request_quotes`.
10. Envia a resposta consolidada no WhatsApp.
11. Atualiza o request para `DONE` ou `ERROR`.

## Modelagem operacional

### `request_quotes`

Representa uma execucao/tentativa de cotacao.

- Nao guarda itens individuais.
- Guarda status da execucao, resposta consolidada, erro e timestamps.
- Um mesmo `request` pode ter varias execucoes ao longo do tempo.

### `quote_results`

Representa resultados individuais encontrados para cada item.

- Preco
- titulo
- fornecedor
- link
- source
- metadados crus

### `worker_processed_messages`

Fonte de verdade do dedupe do bot.

- Um `message_id` nao deve ser processado duas vezes.
- `processing_status` indica `PROCESSED`, `IGNORED` ou `FAILED`.

## Tabelas esperadas

Obrigatorias:

- `requests`
- `request_items`
- `quote_results`
- `request_quotes`
- `worker_processed_messages`

## Variaveis de ambiente

Veja [config/.env.example](/c:/Users/vitin/Desktop/cotai/cotaiedit/config/.env.example).

Principais:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `WAHA_BASE_URL`
- `WAHA_SESSION`
- `WAHA_API_KEY`
- `GROQ_API_KEY`
- `DEBUG`
- `POLL_SECONDS`
- `REQUEST_TIMEOUT_SECONDS`
- `RETRY_ATTEMPTS`
- `RETRY_BACKOFF_SECONDS`
- `HEARTBEAT_SECONDS`

## Comandos

Bootstrap:

```bash
python -m backend.worker.bootstrap
```

Worker:

```bash
python backend/agent.py
```

Health check:

```bash
python backend/agent.py healthcheck
```

Teste local do parser:

```bash
TEST_MODE=1 python backend/agent.py
```

Testes locais do worker:

```bash
python -m unittest backend.tests.test_worker
```

## Dedupe

- O worker consulta `worker_processed_messages` antes de processar uma nova mensagem.
- A chave de dedupe e `message_id`.
- O registro fica persistido no Supabase, nao apenas em arquivo local.

## Bootstrap

O bootstrap valida:

- envs obrigatorias
- conexao com Supabase
- conexao com WAHA
- existencia das tabelas:
  - `requests`
  - `request_items`
  - `quote_results`
  - `request_quotes`
  - `worker_processed_messages`

## Checklist de producao

- Aplicar a migration em `supabase/migrations/20260306_001_request_quotes_and_worker_processed_messages.sql`
- Aplicar tambem `supabase/migrations/20260306_002_core_saas_schema.sql` para tabelas core do SaaS/admin
- Garantir que `quote_results` tenha suporte a `request_quote_id`
- Adicionar indices/constraints se o schema atual de `quote_results` ainda nao tiver
- Configurar observabilidade externa para logs JSON
- Definir alertas para requests em `ERROR`
- Garantir backup e retention no Supabase
- Rodar bootstrap no deploy antes de subir o worker
- Revisar politicas RLS existentes de `requests` e `quote_results`
