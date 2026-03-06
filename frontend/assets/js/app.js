(() => {
  const WHATSAPP_NUMBER = "5517996657737";
  const STORAGE_KEYS = {
    suppliers: "cotai_suppliers",
    materials: "cotai_materials",
    requests: "cotai_requests",
    settings: "cotai_settings",
    seq: "cotai_seq"
  };

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

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
    const nav = $("#appNav");
    const indicator = $("#sideIndicator");
    const toggle = $("#sidebarToggle");
    const collapseBtn = $("#sidebarCollapse");
    const overlay = $("#appDrawerOverlay");
    const collapseStorageKey = "cotai_sidebar_collapsed";
    const mobileBreakpoint = window.matchMedia("(max-width: 920px)");

    if (!sidebar || !nav) return;

    const active = current ? $(`.side-link[data-nav='${current}']`, nav) : null;
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
      if (collapseBtn) collapseBtn.textContent = isCollapsed ? "Expand" : "Collapse";
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
        if (collapseBtn) collapseBtn.textContent = "Collapse";
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
