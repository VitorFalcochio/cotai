Para elevar o nível do seu repositório no GitHub, foquei em **hierarquia visual**, **identidade de marca** e **clareza técnica**. Um bom README deve vender a ideia e explicar a execução ao mesmo tempo.

Aqui está a versão otimizada:

---

# <p align="center">🏗️ Cotai – Marketplace & Agente de Cotação</p>

<p align="center">
<img src="[https://img.shields.io/badge/Status-MVP%20Funcional-success?style=for-the-badge](https://www.google.com/search?q=https://img.shields.io/badge/Status-MVP%2520Funcional-success%3Fstyle%3Dfor-the-badge)" alt="Status MVP">
<img src="[https://img.shields.io/badge/Python-3.9+-blue?style=for-the-badge&logo=python](https://www.google.com/search?q=https://img.shields.io/badge/Python-3.9%2B-blue%3Fstyle%3Dfor-the-badge%26logo%3Dpython)" alt="Python Version">
<img src="[https://img.shields.io/badge/Frontend-HTML%20%2F%20CSS%20%2F%20JS-orange?style=for-the-badge](https://www.google.com/search?q=https://img.shields.io/badge/Frontend-HTML%2520%252F%2520CSS%2520%252F%2520JS-orange%3Fstyle%3Dfor-the-badge)" alt="Tech Stack">
</p>

O **Cotai** (anteriormente CotaObra) é um marketplace B2B focado em construtoras de médio porte. O objetivo é centralizar pedidos e agilizar a comunicação com fornecedores locais, eliminando gargalos e variações de preços que atrasam o cronograma da obra.

---

## 🎯 Proposta de Valor

* **Centralização:** Chega de pedidos espalhados em grupos de WhatsApp.
* **Agilidade:** Redução drástica no tempo de resposta das cotações.
* **Padronização:** Comunicação clara e profissional entre obra e fornecedor.
* **Lean Startup:** Validamos o modelo com tecnologia eficiente e baixo custo operacional.

---

## 🧠 Fluxo do Sistema

O ecossistema foi projetado para ser fluido e funcional:

1. **Captura:** Cliente faz o pedido via **Interface Web**.
2. **Registro:** Os dados são salvos automaticamente no **Google Sheets**.
3. **Processamento:** O **Agente Python** identifica novos pedidos (`status = NOVO`).
4. **Ação:** O sistema gera o link de comunicação direta via **WhatsApp (wa.me)**.
5. **Histórico:** Registro de preços e decisões na aba de **COTAÇÕES**.

---

## 🛠️ Stack Tecnológica

| Camada | Tecnologia | Função |
| --- | --- | --- |
| **Frontend** | HTML5, CSS3, JS | Interface de coleta de pedidos |
| **Banco de Dados** | Google Sheets API | Persistência de dados ágil e visual |
| **Automação** | Python (gspread/google-auth) | Agente operacional inteligente |
| **Comunicação** | Protocolo `wa.me` | Mensageria sem custos de API oficial |

---

## 📁 Estrutura do Projeto

```bash
cotai/
├── frontend/             # Interface do cliente
│   ├── index.html
│   ├── styles.css
│   └── script.js
└── agent/                # Núcleo de automação
    ├── agent.py          # Script principal
    ├── requirements.txt  # Dependências
    └── README.md         # Docs específicos do agente

```

---

## ⚙️ Configuração e Instalação

### 1. Requisitos Prévios

* Python 3.9+ instalado.
* Uma conta no Google Cloud com a **Google Sheets API** ativada.
* Arquivo `service_account.json` na pasta `/agent`.

### 2. Instalação das Dependências

```bash
cd agent
pip install -r requirements.txt

```

### 3. Execução

```bash
python agent.py

```

> [!IMPORTANT]
> **Segurança:** Nunca comite o arquivo `service_account.json`. Certifique-se de que ele está no seu `.gitignore`.

---

## 🚀 Roadmap de Evolução

* [x] MVP Funcional com integração Google Sheets.
* [x] Disparo de mensagens automáticas via link.
* [ ] **Next:** Transição automática de status (`NOVO` ➡️ `EM_COTACAO`).
* [ ] **Next:** Painel de BI para comparação de preços histórica.
* [ ] **Future:** Implementação de IA para sugestão de fornecedores por região.

---

## 💡 Filosofia de Desenvolvimento

> "Automatizar apenas o que já foi validado manualmente."

Este projeto prioriza a **resolução do problema real da obra** sobre a complexidade técnica. O uso do WhatsApp via `wa.me` permite escala imediata sem custos fixos iniciais e sem risco de bloqueios por APIs não oficiais.

---

**Autor:** [Vitor Porveiro Falcochio](https://www.google.com/search?q=https://github.com/SEU-USUARIO-AQUI)
*Projeto desenvolvido para validação de mercado e eficiência operacional na construção civil.*

---

**Dica de amigo:** Se você quiser dar um toque final, substitua o link `SEU-USUARIO-AQUI` pelo seu perfil real no GitHub! Gostaria que eu ajustasse mais algum detalhe específico na lógica do script?
