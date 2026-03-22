# Go-Live MVP Cotai

Checklist objetivo para decidir se o Cotai pode ser publicado como MVP com escopo controlado.

Data desta revisao: `2026-03-22`

## Escopo do MVP

O lancamento deve considerar como produto principal apenas:

- `frontend/pages/login.html`
- `frontend/pages/dashboard.html`
- `frontend/pages/new-request.html`
- `frontend/pages/projects.html`
- `frontend/pages/requests.html`
- `frontend/pages/settings.html`
- `frontend/pages/admin-dashboard.html`
- `frontend/pages/admin-requests.html`
- `frontend/pages/admin-worker.html`

Telas legadas e modulos secundarios devem ficar fora da narrativa de lancamento:

- `analytics`
- `alerts`
- `approvals`
- `comparisons`
- `price-book`
- `suppliers`
- `materials`

## 1. Travas obrigatorias antes de publicar

- [x] Sidebar principal do cliente reduzida ao fluxo central
- [x] Tela de configuracoes alinhada ao novo layout do produto
- [x] Projetos salvos do chat aparecem em tela dedicada
- [x] Retomada de conversa por `thread_id` existe no fluxo principal
- [x] Paginas despriorizadas podem ser marcadas como indisponiveis por `COTAI_CLIENT_DISABLED_PAGES`
- [ ] Confirmar em ambiente de deploy que `COTAI_CLIENT_DISABLED_PAGES=analytics,alerts,approvals,comparisons,price-book`
- [ ] Decidir se `suppliers.html` e `materials.html` ficam publicas no MVP ou tambem saem do ar

## 2. Fluxo principal que precisa passar hoje

- [ ] Fazer login com conta real
- [ ] Abrir `new-request.html`
- [ ] Enviar mensagem no chat da Cota
- [ ] Confirmar criacao do pedido
- [ ] Validar processamento pelo worker
- [ ] Ver resultado voltar para o chat
- [ ] Ver pedido aparecer em `requests.html`
- [ ] Salvar e/ou retomar projeto em `projects.html`
- [ ] Abrir projeto salvo e voltar ao chat correto
- [ ] Salvar configuracoes em `settings.html` e confirmar persistencia

## 3. Infraestrutura minima

- [ ] `Supabase` com migrations obrigatorias aplicadas
- [ ] API respondendo `/health`
- [ ] API respondendo `/ops/overview`
- [ ] Worker rodando com heartbeat recente
- [ ] `CORS_ORIGINS` incluindo o dominio do frontend publicado
- [ ] `COTAI_API_BASE_URL` apontando para a API correta
- [ ] `COTAI_SUPABASE_URL` e `COTAI_SUPABASE_ANON_KEY` validos no frontend
- [ ] `SUPABASE_SERVICE_ROLE_KEY`, `GROQ_API_KEY` e `GEMINI_API_KEY` validas no backend/worker

## 4. UX minima para passar confianca

- [x] Dashboard com busca e navegacao coerentes
- [x] Sidebar colapsada sem sobrepor marca e com tooltips melhores
- [x] Pagina de projetos simplificada e mais alinhada ao fluxo do chat
- [x] Configuracoes redesenhadas em padrao mais premium e minimalista
- [x] Busca de configuracoes com spotlight e destaque visual do bloco encontrado
- [ ] Revisar textos finais de onboarding e empty states nas telas principais
- [ ] Testar mobile real em `dashboard`, `new-request`, `projects` e `settings`
- [ ] Validar tema claro/escuro e densidade em telas centrais

## 5. Riscos aceitos no MVP

Estes pontos nao impedem um MVP fechado, mas precisam estar assumidos conscientemente:

- Preferencias locais em partes do frontend ainda dependem de `localStorage`
- Existem telas legadas no repositorio, mesmo fora do foco principal
- Nao ha evidencias aqui de uma suite frontend cobrindo a jornada visual
- A validacao final ainda depende de smoke test manual em ambiente real

## 6. Recomendacao objetiva de lancamento

Pode publicar como MVP se, no mesmo dia:

1. O fluxo `login -> chat -> confirmacao -> worker -> requests -> projects` passar sem erro.
2. As paginas despriorizadas ficarem explicitamente fora do ar ou fora da navegacao.
3. O deploy estiver com `frontend`, `API`, `worker` e `Supabase` coerentes.
4. Desktop e mobile das telas centrais forem revisados manualmente.

Nao publicar ainda se qualquer um destes falhar:

1. Resultado nao volta para o chat.
2. Pedido nao aparece no historico.
3. Projeto salvo nao retoma a conversa certa.
4. Sessao expirada quebra a navegacao principal.

## 7. Proximo comando recomendado

Rodar a checagem manual de publicacao seguindo:

- [docs/deploy.md](C:/Users/vitin/Desktop/cotai/cotaiedit/docs/deploy.md)

E depois marcar este checklist com base no teste real de ponta a ponta.
