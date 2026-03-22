(() => {
  const WHATSAPP_NUMBER = "5517996657737";
  const BILLING_ENABLED = false;
  const PLAN_SELECTION_ENABLED = false;
  const STORAGE_KEYS = {
    suppliers: "cotai_suppliers",
    materials: "cotai_materials",
    requests: "cotai_requests",
    settings: "cotai_settings",
    seq: "cotai_seq",
    theme: "cotai_theme_preference"
  };

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  const BOXICONS_STYLESHEET_ID = "cotai-boxicons-stylesheet";
  const SIDEBAR_ICON_MAP = {
    dashboard: "bx-grid-alt",
    analytics: "bx-bar-chart-alt-2",
    alerts: "bx-bell",
    new: "bx-bot",
    requests: "bx-receipt",
    approvals: "bx-check-shield",
    comparisons: "bx-git-compare",
    suppliers: "bx-store-alt",
    materials: "bx-cube-alt",
    "price-book": "bx-line-chart",
    plans: "bx-layer",
    settings: "bx-cog"
  };
  const ACTION_ICON_MAP = {
    sidebarToggle: "bx-menu-alt-left",
    sidebarCollapse: "bx-chevrons-left",
    newSupplierBtn: "bx-plus",
    newMaterialBtn: "bx-plus"
  };

  const getClientSidebarMarkup = () => `
    <div class="side-shell-head dashboard-brand-head">
      <a class="brand dashboard-brand" href="dashboard.html">
        <span class="brand-mark"><i class="bx bx-bolt-circle" aria-hidden="true"></i></span>
        <span class="brand-copy">
          <span class="brand-name">Cotai</span>
          <span class="brand-meta">Dashboard</span>
        </span>
      </a>
      <button class="btn btn-ghost side-collapse-btn" type="button" id="sidebarCollapse" aria-label="Colapsar menu" aria-expanded="true" data-icon-only="true">
        <span class="collapse-arrow" aria-hidden="true"></span>
      </button>
    </div>

    <div class="dashboard-nav-group">
      <p class="dashboard-nav-title">Overview</p>
      <nav class="app-nav" id="appNav">
        <div class="side-indicator" id="sideIndicator" aria-hidden="true"></div>
        <a class="side-link" data-nav="dashboard" href="dashboard.html" title="Dashboard"><span class="left"><span class="nav-label">Dashboard</span></span></a>
        <a class="side-link" data-nav="analytics" href="analytics.html" title="Analytics"><span class="left"><span class="nav-label">Analytics</span></span></a>
        <a class="side-link" data-nav="alerts" href="alerts.html" title="Alertas"><span class="left"><span class="nav-label">Alertas</span></span></a>
      </nav>
    </div>

    <div class="dashboard-nav-group">
      <p class="dashboard-nav-title">Procurement</p>
      <nav class="app-nav">
        <a class="side-link" data-nav="requests" href="requests.html" title="Pedidos"><span class="left"><span class="nav-label">Pedidos</span></span></a>
        <a class="side-link" data-nav="approvals" href="approvals.html" title="Aprovacoes"><span class="left"><span class="nav-label">Aprovacoes</span></span></a>
        <a class="side-link" data-nav="comparisons" href="comparisons.html" title="Comparativos"><span class="left"><span class="nav-label">Comparativos</span></span></a>
      </nav>
    </div>

    <div class="dashboard-nav-group">
      <p class="dashboard-nav-title">Base</p>
      <nav class="app-nav">
        <a class="side-link" data-nav="suppliers" href="suppliers.html" title="Fornecedores"><span class="left"><span class="nav-label">Fornecedores</span></span></a>
        <a class="side-link" data-nav="materials" href="materials.html" title="Materiais"><span class="left"><span class="nav-label">Materiais</span></span></a>
        <a class="side-link" data-nav="price-book" href="price-book.html" title="Tabela de precos"><span class="left"><span class="nav-label">Tabela de precos</span></span></a>
      </nav>
    </div>

    <div class="dashboard-nav-group">
      <p class="dashboard-nav-title">Commerce</p>
      <nav class="app-nav dashboard-subnav">
        <a class="side-link" data-nav="new" href="new-request.html" title="Cota"><span class="left"><span class="nav-label">Cota</span></span><span class="mini-badge">IA</span></a>
        ${BILLING_ENABLED || PLAN_SELECTION_ENABLED ? '<a class="side-link" data-nav="plans" href="plans.html" title="Planos"><span class="left"><span class="nav-label">Planos</span></span></a>' : ""}
        <a class="side-link" data-nav="settings" href="settings.html" title="Configuracoes"><span class="left"><span class="nav-label">Configuracoes</span></span></a>
      </nav>
    </div>

    <div class="dashboard-sidebar-divider"></div>

    <div class="dashboard-sidebar-profile">
      <div class="dashboard-avatar">CO</div>
      <div>
        <strong>Cotai</strong>
        <span>Equipe de compras</span>
      </div>
      <a class="dashboard-profile-link" href="settings.html" aria-label="Abrir perfil"><i class="bx bx-log-in-circle" aria-hidden="true"></i></a>
    </div>
  `;

  const ensureBoxicons = () => {
    if (document.getElementById(BOXICONS_STYLESHEET_ID)) return;
    const link = document.createElement("link");
    link.id = BOXICONS_STYLESHEET_ID;
    link.rel = "stylesheet";
    link.href = "https://unpkg.com/boxicons@2.1.4/css/boxicons.min.css";
    document.head.appendChild(link);
  };

  const decorateSidebarNav = (nav) => {
    if (!nav) return;
    nav.querySelectorAll(".side-link").forEach((link) => {
      if (link.querySelector(".side-link-icon")) return;
      const navKey = link.dataset.nav || "";
      const iconName = SIDEBAR_ICON_MAP[navKey] || "bx-circle";
      const left = $(".left", link);
      if (!left) return;
      const icon = document.createElement("i");
      icon.className = `bx ${iconName} side-link-icon`;
      icon.setAttribute("aria-hidden", "true");
      left.prepend(icon);
    });
  };

  const decorateAllSidebarNavs = (sidebar) => {
    if (!sidebar) return;
    sidebar.querySelectorAll(".app-nav").forEach((nav) => decorateSidebarNav(nav));
  };

  const decorateActionButtons = () => {
    Object.entries(ACTION_ICON_MAP).forEach(([id, iconName]) => {
      const element = document.getElementById(id);
      if (!element || element.querySelector(".btn-icon")) return;
      const iconOnly = element.classList.contains("side-collapse-btn");
      const label = iconOnly ? "" : element.textContent.trim();
      element.innerHTML = label
        ? `<i class="bx ${iconName} btn-icon" aria-hidden="true"></i><span>${label}</span>`
        : `<i class="bx ${iconName} btn-icon" aria-hidden="true"></i>`;
    });

    $$("[data-close-modal]").forEach((button) => {
      if (button.dataset.apexIconized === "true") return;
      button.dataset.apexIconized = "true";
      button.innerHTML = '<i class="bx bx-x" aria-hidden="true"></i>';
    });
  };

  const normalizePageShell = () => {
    const appMain = $(".app-main");
    if (!appMain) return;

    const topbar = appMain.querySelector(":scope > .app-topbar");
    if (!topbar || appMain.querySelector(":scope > .page")) return;

    const page = document.createElement("main");
    page.className = "page";

    while (topbar.nextSibling) {
      page.appendChild(topbar.nextSibling);
    }

    appMain.appendChild(page);
  };

  const standardizeSidebarMarkup = (sidebar) => {
    if (!sidebar) return;
    sidebar.classList.add("dashboard-apex-sidebar");
    sidebar.innerHTML = getClientSidebarMarkup();
  };

  const storage = {
    get(key, fallback) {
      try {
        const raw = localStorage.getItem(key);
        return raw ? JSON.parse(raw) : fallback;
      } catch (_) {
        return fallback;
      }
    },
    set(key, value) {
      localStorage.setItem(key, JSON.stringify(value));
    }
  };

  const seedIfNeeded = () => {
    if (!localStorage.getItem(STORAGE_KEYS.suppliers)) {
      storage.set(STORAGE_KEYS.suppliers, [
        {
          id: cryptoRandomId(),
          name: "Depósito Nova Obra",
          contact: "Carlos Mendes",
          channel: "(17) 99665-7737",
          tags: "cimento, bloco",
          active: true,
          createdAt: new Date().toISOString()
        },
        {
          id: cryptoRandomId(),
          name: "Aço Forte Distribuidora",
          contact: "Fernanda Silva",
          channel: "vendas@acoforte.com",
          tags: "aço, vergalhão",
          active: true,
          createdAt: new Date().toISOString()
        }
      ]);
    }

    if (!localStorage.getItem(STORAGE_KEYS.materials)) {
      storage.set(STORAGE_KEYS.materials, [
        {
          id: cryptoRandomId(),
          name: "Cimento CP-II",
          unit: "saco 50kg",
          category: "Cimento",
          notes: "Entrega diária",
          createdAt: new Date().toISOString()
        },
        {
          id: cryptoRandomId(),
          name: "Vergalhão CA-50 10mm",
          unit: "barra 12m",
          category: "Aço",
          notes: "Pedido mínimo 30 barras",
          createdAt: new Date().toISOString()
        }
      ]);
    }

    if (!localStorage.getItem(STORAGE_KEYS.requests)) {
      storage.set(STORAGE_KEYS.requests, [
        {
          id: "CT-0001",
          company: "Construtora Horizonte",
          requester: "Ana Paula",
          delivery: "São José do Rio Preto - Vila Imperial",
          deadline: "48h",
          status: "Em cotação",
          items: ["Cimento CP-II - 150 sacos", "Areia média - 12 m³"],
          notes: "Com nota fiscal",
          createdAt: new Date(Date.now() - 86400000).toISOString(),
          message: ""
        }
      ]);
      localStorage.setItem(STORAGE_KEYS.seq, "2");
    }

    if (!localStorage.getItem(STORAGE_KEYS.seq)) {
      localStorage.setItem(STORAGE_KEYS.seq, "2");
    }

    if (!localStorage.getItem(STORAGE_KEYS.settings)) {
      storage.set(STORAGE_KEYS.settings, {
        company: "Cotai Demo",
        responsible: "",
        whatsapp: "",
        email: "",
        city: "",
        notifications: true
      });
    }
  };

  const cryptoRandomId = () => {
    if (window.crypto?.randomUUID) return window.crypto.randomUUID();
    return `id-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  };

  const formatDate = (iso) => {
    if (!iso) return "-";
    const d = new Date(iso);
    return d.toLocaleDateString("pt-BR") + " " + d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  };

  const openWhatsApp = (text) => {
    const url = `https://wa.me/${WHATSAPP_NUMBER}?text=${encodeURIComponent(text)}`;
    window.open(url, "_blank");
  };

  const getThemePreference = () => {
    const stored = String(localStorage.getItem(STORAGE_KEYS.theme) || "system").trim().toLowerCase();
    return ["system", "light", "dark"].includes(stored) ? stored : "system";
  };

  const getResolvedTheme = (preference = getThemePreference()) => {
    if (preference === "system") {
      return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    }
    return preference;
  };

  const applyTheme = (preference = getThemePreference()) => {
    const resolved = getResolvedTheme(preference);
    document.documentElement.dataset.theme = resolved;
    document.documentElement.dataset.themePreference = preference;
    document.documentElement.style.colorScheme = resolved;
    document.body?.setAttribute("data-theme", resolved);
    document.body?.setAttribute("data-theme-preference", preference);

    const label = $(".theme-switcher [data-theme-current]");
    if (label) {
      const labels = { light: "Claro", dark: "Escuro", system: "Sistema" };
      label.textContent = `${labels[preference]} (${labels[resolved]})`;
    }

    $$(".theme-option").forEach((button) => {
      const active = button.dataset.themeOption === preference;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-pressed", active ? "true" : "false");
    });
  };

  const initThemeSystem = () => {
    ensureBoxicons();
    applyTheme();

    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
      if (getThemePreference() === "system") {
        applyTheme("system");
      }
    });
  };

  const nextRequestId = () => {
    const current = Number(localStorage.getItem(STORAGE_KEYS.seq) || "1");
    localStorage.setItem(STORAGE_KEYS.seq, String(current + 1));
    return `CT-${String(current).padStart(4, "0")}`;
  };

  const initSidebar = () => {
    const page = document.body.dataset.page;
    const navKeyMap = {
      "new-request": "new"
    };
    const current = navKeyMap[page] || page;

    const sidebar = $("#appSidebar");
    const collapseStorageKey = "cotai_sidebar_collapsed";
    const mobileBreakpoint = window.matchMedia("(max-width: 920px)");

    standardizeSidebarMarkup(sidebar);
    const nav = $("#appNav");
    const indicator = $("#sideIndicator");
    const toggle = $("#sidebarToggle");
    const collapseBtn = $("#sidebarCollapse");
    const overlay = $("#appDrawerOverlay");
    if (!sidebar || !nav) return;
    decorateAllSidebarNavs(sidebar);
    decorateActionButtons();
    normalizePageShell();

    const active = current ? $(`.side-link[data-nav='${current}']`, sidebar) : null;
    if (active) active.classList.add("active");

    const moveIndicator = () => {
      if (!indicator || !active) return;
      const navRect = nav.getBoundingClientRect();
      const activeRect = active.getBoundingClientRect();
      const top = activeRect.top - navRect.top;
      indicator.style.transform = `translateY(${Math.round(top)}px)`;
      indicator.style.height = `${Math.round(activeRect.height)}px`;
      indicator.style.opacity = "1";
    };

    const setDrawerState = (isOpen) => {
      document.body.classList.toggle("drawer-open", isOpen);
      const expanded = isOpen ? "true" : "false";
      if (toggle) toggle.setAttribute("aria-expanded", expanded);
    };

    const setCollapsedState = (isCollapsed) => {
      if (mobileBreakpoint.matches) return;
      document.body.classList.toggle("sidebar-collapsed", isCollapsed);
      sidebar.classList.toggle("is-collapsed", isCollapsed);
      localStorage.setItem(collapseStorageKey, isCollapsed ? "1" : "0");
      if (collapseBtn) {
        collapseBtn.setAttribute("aria-expanded", isCollapsed ? "false" : "true");
        collapseBtn.setAttribute("aria-label", isCollapsed ? "Expandir menu" : "Colapsar menu");
      }
      requestAnimationFrame(moveIndicator);
    };

    const savedCollapsed = localStorage.getItem(collapseStorageKey) === "1";
    setCollapsedState(savedCollapsed);

    if (collapseBtn) {
      collapseBtn.addEventListener("click", () => {
        const next = !sidebar.classList.contains("is-collapsed");
        setCollapsedState(next);
      });
    }

    if (toggle) {
      toggle.addEventListener("click", () => {
        if (mobileBreakpoint.matches) {
          const shouldOpen = !document.body.classList.contains("drawer-open");
          setDrawerState(shouldOpen);
          return;
        }
        const next = !sidebar.classList.contains("is-collapsed");
        setCollapsedState(next);
      });
    }

    if (overlay) {
      overlay.addEventListener("click", () => setDrawerState(false));
    }

    window.addEventListener("resize", () => {
      if (mobileBreakpoint.matches) {
        document.body.classList.remove("sidebar-collapsed");
        sidebar.classList.remove("is-collapsed");
        if (collapseBtn) {
          collapseBtn.setAttribute("aria-expanded", "true");
          collapseBtn.setAttribute("aria-label", "Colapsar menu");
        }
      } else {
        setDrawerState(false);
        setCollapsedState(localStorage.getItem(collapseStorageKey) === "1");
      }
      requestAnimationFrame(moveIndicator);
    });

    nav.addEventListener("click", (e) => {
      const link = e.target.closest(".side-link");
      if (!link) return;
      if (mobileBreakpoint.matches) setDrawerState(false);
    });

    setTimeout(moveIndicator, 20);
    window.addEventListener("load", moveIndicator, { once: true });
  };

  const initModalSystem = () => {
    $$('[data-open-modal]').forEach((button) => {
      button.addEventListener('click', () => {
        const target = button.getAttribute('data-open-modal');
        const modal = document.getElementById(target);
        if (!modal) return;
        modal.classList.add('show');
        document.body.style.overflow = 'hidden';
      });
    });

    $$('[data-close-modal]').forEach((button) => {
      button.addEventListener('click', () => closeClosestModal(button));
    });

    $$('.app-modal').forEach((modal) => {
      modal.addEventListener('click', (e) => {
        if (e.target.classList.contains('app-modal-backdrop')) {
          modal.classList.remove('show');
          document.body.style.overflow = '';
        }
      });
    });
  };

  const closeClosestModal = (el) => {
    const modal = el.closest('.app-modal');
    if (!modal) return;
    modal.classList.remove('show');
    document.body.style.overflow = '';
  };

  const setupDashboard = () => {
    if (document.body.dataset.page !== 'dashboard') return;

    const suppliers = storage.get(STORAGE_KEYS.suppliers, []);
    const materials = storage.get(STORAGE_KEYS.materials, []);
    const requests = storage.get(STORAGE_KEYS.requests, []);

    const openRequests = requests.filter((r) => r.status === 'Em cotação' || r.status === 'Novo').length;

    setText('#metricRequests', String(requests.length));
    setText('#metricOpenRequests', String(openRequests));
    setText('#metricSuppliers', String(suppliers.length));
    setText('#metricMaterials', String(materials.length));

    const latest = [...requests].sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt)).slice(0, 5);
    const tbody = $('#dashboardRecentBody');
    if (!tbody) return;

    if (!latest.length) {
      tbody.innerHTML = `<tr><td colspan="4" class="app-empty">Nenhum pedido ainda.</td></tr>`;
      return;
    }

    tbody.innerHTML = latest.map((item) => `
      <tr>
        <td>${item.id}</td>
        <td>${item.company}</td>
        <td><span class="app-badge ${item.status === 'Concluído' ? 'is-success' : 'is-warning'}">${item.status}</span></td>
        <td>${formatDate(item.createdAt)}</td>
      </tr>
    `).join('');
  };

  const setupRequests = () => {
    if (document.body.dataset.page !== 'requests') return;

    const tbody = $('#requestsTableBody');
    const count = $('#requestsCount');
    const data = [...storage.get(STORAGE_KEYS.requests, [])].sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt));

    if (count) count.textContent = `${data.length} pedidos`;

    if (!tbody) return;
    if (!data.length) {
      tbody.innerHTML = `<tr><td colspan="6" class="app-empty">Nenhum pedido encontrado.</td></tr>`;
      return;
    }

    tbody.innerHTML = data.map((item) => `
      <tr>
        <td>${item.id}</td>
        <td>${item.company}</td>
        <td>${item.requester || '-'}</td>
        <td>${item.deadline || '-'}</td>
        <td><span class="app-badge ${item.status === 'Concluído' ? 'is-success' : 'is-warning'}">${item.status}</span></td>
        <td>${formatDate(item.createdAt)}</td>
      </tr>
    `).join('');
  };

  const setupNewRequest = () => {
    if (document.body.dataset.page !== 'new-request') return;

    const form = $('#newRequestForm');
    const result = $('#requestResult');
    const messageEl = $('#requestMessage');
    const idEl = $('#generatedRequestId');
    const copyBtn = $('#copyRequestMessage');
    const openBtn = $('#openRequestWhats');

    if (!form) return;

    let lastMessage = '';

    form.addEventListener('submit', (e) => {
      e.preventDefault();
      const data = new FormData(form);

      const company = String(data.get('company') || '').trim();
      const requester = String(data.get('requester') || '').trim();
      const delivery = String(data.get('delivery') || '').trim();
      const deadline = String(data.get('deadline') || '').trim();
      const notes = String(data.get('notes') || '').trim();
      const itemsRaw = String(data.get('items') || '').split('\n').map((line) => line.trim()).filter(Boolean);

      if (!company || !delivery || !deadline || !itemsRaw.length) {
        alert('Preencha empresa, itens, local de entrega e prazo.');
        return;
      }

      const requestId = nextRequestId();
      const lines = itemsRaw.map((item, index) => `${index + 1}) ${item}`);
      const message = `#COTAI\n` +
        `PedidoID: ${requestId}\n` +
        `Empresa: ${company}\n` +
        `Solicitante: ${requester || '-'}\n` +
        `Itens:\n${lines.join('\n')}\n` +
        `Prazo desejado: ${deadline}\n` +
        `Local de entrega: ${delivery}\n` +
        `${notes ? `Observações: ${notes}\n` : ''}` +
        `Retornar com melhor preço e prazo.`;

      const requests = storage.get(STORAGE_KEYS.requests, []);
      requests.push({
        id: requestId,
        company,
        requester,
        delivery,
        deadline,
        status: 'Novo',
        items: itemsRaw,
        notes,
        message,
        createdAt: new Date().toISOString()
      });
      storage.set(STORAGE_KEYS.requests, requests);

      lastMessage = message;
      if (result) result.classList.remove('hidden');
      if (messageEl) messageEl.textContent = message;
      if (idEl) idEl.textContent = requestId;

      form.reset();
    });

    if (copyBtn) {
      copyBtn.addEventListener('click', async () => {
        if (!lastMessage) return;
        try {
          await navigator.clipboard.writeText(lastMessage);
          copyBtn.textContent = 'Copiado';
          setTimeout(() => (copyBtn.textContent = 'Copiar'), 1200);
        } catch (_) {
          alert('Não foi possível copiar.');
        }
      });
    }

    if (openBtn) {
      openBtn.addEventListener('click', () => {
        if (!lastMessage) return;
        openWhatsApp(lastMessage);
      });
    }
  };

  const setupSuppliers = () => {
    if (document.body.dataset.page !== 'suppliers') return;

    const tableBody = $('#suppliersTableBody');
    const form = $('#supplierForm');
    const modal = $('#supplierModal');
    const title = $('#supplierModalTitle');
    let editingId = null;

    const render = () => {
      const rows = storage.get(STORAGE_KEYS.suppliers, []);
      if (!tableBody) return;

      if (!rows.length) {
        tableBody.innerHTML = `<tr><td colspan="6" class="app-empty">Nenhum fornecedor cadastrado.</td></tr>`;
        return;
      }

      tableBody.innerHTML = rows.map((item) => `
        <tr>
          <td>${item.name}</td>
          <td>${item.contact || '-'}</td>
          <td>${item.channel || '-'}</td>
          <td>${item.tags || '-'}</td>
          <td><span class="app-badge ${item.active ? 'is-success' : 'is-muted'}">${item.active ? 'Ativo' : 'Inativo'}</span></td>
          <td class="app-actions">
            <button class="btn btn-ghost" data-action="edit" data-id="${item.id}">Editar</button>
            <button class="btn btn-ghost" data-action="delete" data-id="${item.id}">Excluir</button>
          </td>
        </tr>
      `).join('');
    };

    const resetForm = () => {
      form?.reset();
      editingId = null;
      if (title) title.textContent = 'Novo fornecedor';
      const idInput = $('#supplierId');
      if (idInput) idInput.value = '';
    };

    if (form) {
      form.addEventListener('submit', (e) => {
        e.preventDefault();
        const data = new FormData(form);
        const payload = {
          id: editingId || cryptoRandomId(),
          name: String(data.get('name') || '').trim(),
          contact: String(data.get('contact') || '').trim(),
          channel: String(data.get('channel') || '').trim(),
          tags: String(data.get('tags') || '').trim(),
          active: String(data.get('active') || 'true') === 'true',
          createdAt: new Date().toISOString()
        };

        if (!payload.name) {
          alert('Informe o nome do fornecedor.');
          return;
        }

        const items = storage.get(STORAGE_KEYS.suppliers, []);
        const idx = items.findIndex((it) => it.id === payload.id);

        if (idx >= 0) {
          items[idx] = { ...items[idx], ...payload };
        } else {
          items.push(payload);
        }

        storage.set(STORAGE_KEYS.suppliers, items);
        render();
        resetForm();
        if (modal) {
          modal.classList.remove('show');
          document.body.style.overflow = '';
        }
      });
    }

    if (tableBody) {
      tableBody.addEventListener('click', (e) => {
        const button = e.target.closest('button[data-action]');
        if (!button) return;

        const action = button.dataset.action;
        const id = button.dataset.id;
        const items = storage.get(STORAGE_KEYS.suppliers, []);
        const found = items.find((it) => it.id === id);

        if (!found) return;

        if (action === 'delete') {
          if (!confirm(`Excluir fornecedor "${found.name}"?`)) return;
          storage.set(STORAGE_KEYS.suppliers, items.filter((it) => it.id !== id));
          render();
          return;
        }

        editingId = id;
        if (title) title.textContent = 'Editar fornecedor';
        setField('#supplierId', found.id);
        setField('#supplierName', found.name);
        setField('#supplierContact', found.contact);
        setField('#supplierChannel', found.channel);
        setField('#supplierTags', found.tags);
        setField('#supplierActive', String(found.active));
        modal?.classList.add('show');
        document.body.style.overflow = 'hidden';
      });
    }

    const openBtn = $('#newSupplierBtn');
    if (openBtn) {
      openBtn.addEventListener('click', () => {
        resetForm();
        modal?.classList.add('show');
        document.body.style.overflow = 'hidden';
      });
    }

    render();
  };

  const setupMaterials = () => {
    if (document.body.dataset.page !== 'materials') return;

    const tableBody = $('#materialsTableBody');
    const form = $('#materialForm');
    const modal = $('#materialModal');
    const title = $('#materialModalTitle');
    let editingId = null;

    const render = () => {
      const rows = storage.get(STORAGE_KEYS.materials, []);
      if (!tableBody) return;

      if (!rows.length) {
        tableBody.innerHTML = `<tr><td colspan="5" class="app-empty">Nenhum material cadastrado.</td></tr>`;
        return;
      }

      tableBody.innerHTML = rows.map((item) => `
        <tr>
          <td>${item.name}</td>
          <td>${item.unit || '-'}</td>
          <td>${item.category || '-'}</td>
          <td>${item.notes || '-'}</td>
          <td class="app-actions">
            <button class="btn btn-ghost" data-action="edit" data-id="${item.id}">Editar</button>
            <button class="btn btn-ghost" data-action="delete" data-id="${item.id}">Excluir</button>
          </td>
        </tr>
      `).join('');
    };

    const resetForm = () => {
      form?.reset();
      editingId = null;
      if (title) title.textContent = 'Novo material';
      setField('#materialId', '');
    };

    if (form) {
      form.addEventListener('submit', (e) => {
        e.preventDefault();
        const data = new FormData(form);
        const payload = {
          id: editingId || cryptoRandomId(),
          name: String(data.get('name') || '').trim(),
          unit: String(data.get('unit') || '').trim(),
          category: String(data.get('category') || '').trim(),
          notes: String(data.get('notes') || '').trim(),
          createdAt: new Date().toISOString()
        };

        if (!payload.name) {
          alert('Informe o nome do material.');
          return;
        }

        const items = storage.get(STORAGE_KEYS.materials, []);
        const idx = items.findIndex((it) => it.id === payload.id);

        if (idx >= 0) {
          items[idx] = { ...items[idx], ...payload };
        } else {
          items.push(payload);
        }

        storage.set(STORAGE_KEYS.materials, items);
        render();
        resetForm();
        if (modal) {
          modal.classList.remove('show');
          document.body.style.overflow = '';
        }
      });
    }

    if (tableBody) {
      tableBody.addEventListener('click', (e) => {
        const button = e.target.closest('button[data-action]');
        if (!button) return;

        const action = button.dataset.action;
        const id = button.dataset.id;
        const items = storage.get(STORAGE_KEYS.materials, []);
        const found = items.find((it) => it.id === id);

        if (!found) return;

        if (action === 'delete') {
          if (!confirm(`Excluir material "${found.name}"?`)) return;
          storage.set(STORAGE_KEYS.materials, items.filter((it) => it.id !== id));
          render();
          return;
        }

        editingId = id;
        if (title) title.textContent = 'Editar material';
        setField('#materialId', found.id);
        setField('#materialName', found.name);
        setField('#materialUnit', found.unit);
        setField('#materialCategory', found.category);
        setField('#materialNotes', found.notes);
        modal?.classList.add('show');
        document.body.style.overflow = 'hidden';
      });
    }

    const openBtn = $('#newMaterialBtn');
    if (openBtn) {
      openBtn.addEventListener('click', () => {
        resetForm();
        modal?.classList.add('show');
        document.body.style.overflow = 'hidden';
      });
    }

    render();
  };

  const setupSettings = () => {
    if (document.body.dataset.page !== 'settings') return;

    const form = $('#settingsForm');
    const status = $('#settingsStatus');
    if (!form) return;

    const current = storage.get(STORAGE_KEYS.settings, {});
    setField('#setCompany', current.company || '');
    setField('#setResponsible', current.responsible || '');
    setField('#setWhatsapp', current.whatsapp || '');
    setField('#setEmail', current.email || '');
    setField('#setCity', current.city || '');
    const notif = $('#setNotifications');
    if (notif) notif.checked = Boolean(current.notifications);

    form.addEventListener('submit', (e) => {
      e.preventDefault();
      const data = new FormData(form);
      const payload = {
        company: String(data.get('company') || '').trim(),
        responsible: String(data.get('responsible') || '').trim(),
        whatsapp: String(data.get('whatsapp') || '').trim(),
        email: String(data.get('email') || '').trim(),
        city: String(data.get('city') || '').trim(),
        notifications: data.get('notifications') === 'on'
      };
      storage.set(STORAGE_KEYS.settings, payload);
      if (status) {
        status.textContent = 'Configurações salvas com sucesso.';
      }
    });
  };

  const setText = (selector, value) => {
    const el = $(selector);
    if (el) el.textContent = value;
  };

  const setField = (selector, value) => {
    const el = $(selector);
    if (el) el.value = value;
  };

  document.addEventListener('DOMContentLoaded', () => {
    seedIfNeeded();
    initThemeSystem();
    initSidebar();
    initModalSystem();

    setupDashboard();
    setupRequests();
    setupNewRequest();
    setupSuppliers();
    setupMaterials();
    setupSettings();
  });
})();
