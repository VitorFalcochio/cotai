# 🏗️ CotaObra – Marketplace & Agente de Cotação de Materiais

CotaObra é um **MVP de marketplace B2B para materiais de construção**, focado em **construtoras de médio porte**, que centraliza pedidos, agiliza cotações com fornecedores locais e reduz atrasos de obra causados por falta de material ou variação de preços.

Este projeto combina:
- 🌐 **Site (HTML/CSS/JS)** para coleta de pedidos
- 📊 **Google Sheets** como banco de dados inicial
- 🤖 **Agente em Python** para automação operacional
- 💬 **WhatsApp (wa.me)** para comunicação rápida, sem API paga

---

## 🎯 Objetivo do MVP

- Centralizar pedidos de materiais
- Reduzir tempo de resposta na cotação
- Padronizar comunicação com clientes
- Validar o modelo antes de automações mais complexas (API oficial, IA, etc.)

---

## 🧠 Fluxo do Sistema

Cliente → Site → WhatsApp
↓
Google Sheets (PEDIDOS)
↓
Agente Python
↓
WhatsApp (Confirmação)
↓
Google Sheets (COTAÇÕES)


---

## 📁 Estrutura do Projeto

cotaobra-site/
│
├── frontend/ # Site (cliente)
│ ├── index.html
│ ├── styles.css
│ └── script.js
│
└── agent/ # Automação (operacional)
├── agent.py
├── service_account.json
├── requirements.txt
└── README.md


---

## 🗂️ Modelo de Dados (Google Sheets)

### Aba: `PEDIDOS` (entrada do sistema)

| Coluna     | Descrição |
|-----------|-----------|
| id        | ID único do pedido |
| data      | Data/hora do pedido |
| cliente   | Nome do cliente |
| whatsapp  | WhatsApp com DDI |
| local     | Local da obra |
| prazo     | Prazo desejado |
| itens     | Lista de materiais |
| status    | NOVO / EM_COTACAO / FECHADO |

> ⚠️ O agente Python **só lê pedidos com `status = NOVO`**

---

### Aba: `COTAÇÕES` (histórico e comparação)
Usada para registrar:
- fornecedores
- preços
- prazos
- decisão final

---

## 🤖 Agente Python (agent.py)

### Funções principais:
- Conecta ao Google Sheets
- Lê pedidos com status `NOVO`
- Abre o WhatsApp com mensagem automática:
  > “Recebido, vou cotar…”
- Evita retrabalho e pedidos duplicados

### Executar o agente:
```bash
cd agent
python agent.py
📦 Dependências
Instale com:

python -m pip install -r requirements.txt
Conteúdo do requirements.txt:

gspread
google-auth
🔐 Credenciais (Google Cloud)
O arquivo service_account.json deve ficar na pasta agent/

Nunca versionar ou compartilhar esse arquivo

A planilha precisa ser compartilhada com o e-mail da Service Account

💬 Comunicação com Cliente
O envio de mensagens é feito via wa.me, evitando:

custos com API

risco de bloqueio

complexidade desnecessária no MVP

🚀 Status do Projeto
✔ MVP funcional
✔ Em uso manual assistido
🔜 Próximos passos planejados:

Atualizar status automaticamente (NOVO → EM_COTACAO)

Geração automática de linhas em COTAÇÕES

Inteligência de preços por histórico

API oficial do WhatsApp (fase futura)

⚠️ Observação Importante
Este projeto segue a filosofia:

Automatizar apenas o que já foi validado manualmente

A prioridade é resolver o problema real da obra, não criar complexidade técnica desnecessária.

📌 Autor: Vitor Porveiro Falcochio
Projeto desenvolvido como MVP para validação de mercado no setor de construção civil, focado em agilidade, clareza e eficiência operacional.
