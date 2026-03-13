# Go-Live Comercial Cotai

Checklist objetivo para deixar a Cotai demonstravel com seguranca comercial.

## 1. Ambiente minimo obrigatorio

- [ ] Aplicar todas as migrations do Supabase, com foco em `supplier_price_snapshots`
- [ ] Confirmar `SUPABASE_URL`, `SUPABASE_ANON_KEY` e `SUPABASE_SERVICE_ROLE_KEY`
- [ ] Subir backend FastAPI
- [ ] Subir worker Python
- [ ] Validar acesso do frontend ao projeto Supabase correto

## 2. Fluxo principal que precisa passar sem erro

- [ ] Login
- [ ] Dashboard carregar
- [ ] Nova cotacao enviar mensagem
- [ ] Confirmacao do pedido
- [ ] Worker processar request
- [ ] Resultado aparecer no chat
- [ ] Historico de pedidos listar request
- [ ] Admin abrir snapshots de preco

## 3. Dados minimos para demo comercial

- [ ] 30+ materiais
- [ ] 10+ fornecedores
- [ ] snapshots recentes de preco
- [ ] 3 a 5 pedidos com historico coerente
- [ ] 1 conta demo pronta para apresentacao

## 4. Sinais visuais que nao podem aparecer

- [ ] `TODO`
- [ ] mensagens tecnicas de tabela ausente na area do cliente
- [ ] telas vazias sem contexto
- [ ] cards com metrica quebrada
- [ ] erro de encoding

## 5. Fallback aceito para vender como piloto

- [ ] dashboard com modo demonstracao coerente
- [ ] admin com modo demonstracao coerente
- [ ] billing com modo demonstracao coerente
- [ ] worker com modo demonstracao coerente

## 6. Antes da reuniao de venda

- [ ] abrir landing, login, dashboard, nova cotacao e admin
- [ ] confirmar tema claro/escuro/system
- [ ] validar CTA de demonstração
- [ ] preparar roteiro de demo de 5 minutos
- [ ] deixar uma aba com snapshots e outra com nova cotacao

## Estado atual deste repositório

- modo demonstracao adicionado para dashboard, admin overview, worker e billing
- sinais visiveis de `TODO` removidos das telas principais de admin
- mensagens do motor de cotacao tornadas mais comerciais
- testes backend principais passando
