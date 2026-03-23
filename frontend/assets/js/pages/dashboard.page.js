import { LOGIN_PATH } from "../config.js";
import { getAdminProfile, getCompanyDisplayName, requireAuth, signOut } from "../auth.js";
import { showAdminShortcut } from "../adminPage.js";
import { formatCurrencyBRL } from "../adminCommon.js";
import { fetchProcurementOverview } from "../procurementData.js";
import {
  formatDateTime,
  initSidebar,
  qs,
  runPageBoot,
  setAccentPreference,
  setDensityPreference,
  setHTML,
  setText,
  setThemePreference,
  showFeedback
} from "../ui.js";

const STATUS_LABELS = {
  DONE: "Concluido",
  ERROR: "Erro",
  PROCESSING: "Em andamento",
  PENDING_QUOTE: "Pendente",
  AWAITING_CONFIRMATION: "Aguardando confirmacao",
  AWAITING_APPROVAL: "Aguardando aprovacao",
  DRAFT: "Rascunho"
};

const CHAT_BACKGROUND_STORAGE_KEY = "cotai_chat_background_preference";

function getStoredChatBackgroundPreference() {
  const stored = String(window.localStorage.getItem(CHAT_BACKGROUND_STORAGE_KEY) || "glow").trim().toLowerCase();
  return ["glow", "grid", "plain"].includes(stored) ? stored : "glow";
}

function setChatBackgroundPreference(backgroundPreference) {
  const nextPreference = ["glow", "grid", "plain"].includes(backgroundPreference) ? backgroundPreference : "glow";
  window.localStorage.setItem(CHAT_BACKGROUND_STORAGE_KEY, nextPreference);
  document.documentElement.dataset.chatBackground = nextPreference;
  document.body?.setAttribute("data-chat-background", nextPreference);
  return nextPreference;
}

function badgeClass(status) {
  const value = String(status || "").toUpperCase();
  if (value === "DONE") return "is-success";
  if (value === "ERROR") return "is-danger";
  if (["PROCESSING", "PENDING_QUOTE", "AWAITING_CONFIRMATION", "AWAITING_APPROVAL"].includes(value)) return "is-warning";
  return "is-muted";
}

function formatStatus(status) {
  const key = String(status || "").toUpperCase();
  return STATUS_LABELS[key] || status || "-";
}

function getInitials(value, fallback = "CO") {
  const parts = String(value || "")
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2);
  if (!parts.length) return fallback;
  return parts.map((part) => part[0]?.toUpperCase() || "").join("");
}

function relativeTimeFromNow(value) {
  const date = value ? new Date(value) : null;
  if (!(date instanceof Date) || Number.isNaN(date.getTime())) return "Agora";
  const diffMs = Date.now() - date.getTime();
  const diffMinutes = Math.max(0, Math.round(diffMs / 60000));
  if (diffMinutes < 1) return "Agora";
  if (diffMinutes < 60) return `Ha ${diffMinutes} min`;
  const diffHours = Math.round(diffMinutes / 60);
  if (diffHours < 24) return `Ha ${diffHours}h`;
  const diffDays = Math.round(diffHours / 24);
  return `Ha ${diffDays}d`;
}

function buildNotifications(overview) {
  const pendingApprovals = overview.requests.filter((request) => String(request.approval_status || "").toUpperCase() === "PENDING");
  const processingRequests = overview.requests.filter((request) => ["PROCESSING", "PENDING_QUOTE"].includes(String(request.status || "").toUpperCase()));
  const errorRequests = overview.requests.filter((request) => String(request.status || "").toUpperCase() === "ERROR");
  const finishedRequests = overview.requests.filter((request) => String(request.status || "").toUpperCase() === "DONE").slice(0, 2);
  const notifications = [];

  if (pendingApprovals.length) {
    notifications.push({
      tone: "is-warning",
      icon: "bx-check-shield",
      title: `${pendingApprovals.length} pedido(s) aguardando aprovacao`,
      description: "A equipe precisa validar as proximas compras antes de seguir para cotacao.",
      meta: relativeTimeFromNow(pendingApprovals[0]?.updated_at || pendingApprovals[0]?.created_at),
      href: "requests.html"
    });
  }

  if (processingRequests.length) {
    notifications.push({
      tone: "is-success",
      icon: "bx-loader-circle",
      title: `${processingRequests.length} cotacao(oes) em andamento`,
      description: "A Cota esta comparando preco, prazo e melhor fornecedor.",
      meta: relativeTimeFromNow(processingRequests[0]?.updated_at || processingRequests[0]?.created_at),
      href: "requests.html"
    });
  }

  if (errorRequests.length) {
    notifications.push({
      tone: "is-danger",
      icon: "bx-error-circle",
      title: `${errorRequests.length} pedido(s) com falha`,
      description: "Algumas cotacoes precisam de revisao antes de prosseguir.",
      meta: relativeTimeFromNow(errorRequests[0]?.updated_at || errorRequests[0]?.created_at),
      href: "requests.html"
    });
  }

  finishedRequests.forEach((request) => {
    notifications.push({
      tone: "is-success",
      icon: "bx-badge-check",
      title: `${request.request_code || "Pedido"} concluido`,
      description: `Melhor fornecedor: ${request.best_supplier_name || "Cotacao finalizada"}.`,
      meta: relativeTimeFromNow(request.updated_at || request.created_at),
      href: "requests.html"
    });
  });

  overview.notices.slice(0, 2).forEach((notice) => {
    notifications.push({
      tone: "is-warning",
      icon: "bx-info-circle",
      title: "Aviso do sistema",
      description: notice,
      meta: "Ambiente",
      href: "settings.html"
    });
  });

  return notifications.slice(0, 7);
}

function renderNotifications(items) {
  if (!items.length) {
    return '<div class="dashboard-notification-empty">Nenhuma notificacao nova por agora.</div>';
  }

  return items
    .map(
      (item) => `
        <a class="dashboard-notification-item ${item.tone}" href="${item.href}">
          <span class="dashboard-notification-icon"><i class="bx ${item.icon}" aria-hidden="true"></i></span>
          <span class="dashboard-notification-copy">
            <strong>${item.title}</strong>
            <p>${item.description}</p>
            <span>${item.meta}</span>
          </span>
        </a>
      `
    )
    .join("");
}

function initNotifications(items) {
  const panel = qs("#dashboardNotifications");
  const toggle = qs("#dashboardNotificationsToggle");
  const close = qs("#dashboardNotificationsClose");
  const dot = qs("#dashboardBellDot");
  if (!panel || !toggle) return;

  setHTML("#dashboardNotificationsList", renderNotifications(items));
  setText("#dashboardNotificationsMeta", `${items.length} atualizacao(oes)`);
  dot?.classList.toggle("hidden", items.length === 0);

  const closePanel = () => {
    panel.classList.add("hidden");
    toggle.setAttribute("aria-expanded", "false");
  };

  const openPanel = () => {
    panel.classList.remove("hidden");
    toggle.setAttribute("aria-expanded", "true");
    dot?.classList.add("hidden");
  };

  toggle.addEventListener("click", (event) => {
    event.stopPropagation();
    if (panel.classList.contains("hidden")) {
      openPanel();
      return;
    }
    closePanel();
  });

  close?.addEventListener("click", closePanel);
  document.addEventListener("click", (event) => {
    if (panel.classList.contains("hidden")) return;
    if (panel.contains(event.target) || toggle.contains(event.target)) return;
    closePanel();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closePanel();
  });
}

function syncCustomizerState() {
  const themePreference = document.documentElement.dataset.themePreference || "system";
  const accentPreference = document.documentElement.dataset.accent || "emerald";
  const densityPreference = document.documentElement.dataset.density || "comfortable";
  const backgroundPreference = document.documentElement.dataset.chatBackground || getStoredChatBackgroundPreference();

  document.querySelectorAll("[data-theme-choice]").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.themeChoice === themePreference);
  });

  document.querySelectorAll("[data-accent-choice]").forEach((button) => {
    const swatch = button.querySelector(".swatch");
    if (swatch && button.dataset.swatch) {
      swatch.style.setProperty("--swatch-color", button.dataset.swatch);
    }
    button.classList.toggle("is-active", button.dataset.accentChoice === accentPreference);
  });

  document.querySelectorAll("[data-density-choice]").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.densityChoice === densityPreference);
  });

  document.querySelectorAll("[data-chat-background-choice]").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.chatBackgroundChoice === backgroundPreference);
  });
}

function initCustomizer() {
  const panel = qs("#dashboardCustomizePanel");
  const toggle = qs("#dashboardCustomizeToggle");
  const close = qs("#dashboardCustomizeClose");
  if (!panel || !toggle) return;

  const closePanel = () => {
    panel.classList.add("hidden");
    toggle.classList.remove("is-active");
    toggle.setAttribute("aria-expanded", "false");
  };

  const openPanel = () => {
    panel.classList.remove("hidden");
    toggle.classList.add("is-active");
    toggle.setAttribute("aria-expanded", "true");
    syncCustomizerState();
  };

  toggle.addEventListener("click", (event) => {
    event.stopPropagation();
    if (panel.classList.contains("hidden")) {
      openPanel();
      return;
    }
    closePanel();
  });

  close?.addEventListener("click", closePanel);

  panel.querySelectorAll("[data-theme-choice]").forEach((button) => {
    button.addEventListener("click", () => {
      setThemePreference(button.dataset.themeChoice);
      syncCustomizerState();
    });
  });

  panel.querySelectorAll("[data-accent-choice]").forEach((button) => {
    button.addEventListener("click", () => {
      setAccentPreference(button.dataset.accentChoice);
      syncCustomizerState();
    });
  });

  panel.querySelectorAll("[data-density-choice]").forEach((button) => {
    button.addEventListener("click", () => {
      setDensityPreference(button.dataset.densityChoice);
      syncCustomizerState();
    });
  });

  panel.querySelectorAll("[data-chat-background-choice]").forEach((button) => {
    button.addEventListener("click", () => {
      setChatBackgroundPreference(button.dataset.chatBackgroundChoice);
      syncCustomizerState();
    });
  });

  document.addEventListener("click", (event) => {
    if (panel.classList.contains("hidden")) return;
    if (panel.contains(event.target) || toggle.contains(event.target)) return;
    closePanel();
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closePanel();
  });

  syncCustomizerState();
}

function normalizeText(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

function buildSearchIndex(overview) {
  const staticPages = [
    { label: "Dashboard", subtitle: "Visao geral da operacao", href: "dashboard.html", group: "Paginas", icon: "bx-grid-alt", tag: "Pagina" },
    { label: "Pedidos", subtitle: "Historico e acompanhamento", href: "requests.html", group: "Paginas", icon: "bx-receipt", tag: "Pagina" },
    { label: "Cota", subtitle: "Assistente de compras", href: "new-request.html", group: "Paginas", icon: "bx-bot", tag: "IA" },
    { label: "Configuracoes", subtitle: "Conta e preferencias", href: "settings.html", group: "Paginas", icon: "bx-cog", tag: "Pagina" }
  ];

  const requests = overview.requests.slice(0, 10).map((request) => ({
    label: request.request_code || "Pedido",
    subtitle: `${request.customer_name || "Sem cliente"} - ${request.delivery_location || "Sem local"}`,
    href: "requests.html",
    group: "Pedidos",
    icon: "bx-receipt",
    tag: String(request.status || "pedido").replaceAll("_", " ")
  }));

  const projects = overview.projects.slice(0, 6).map((project) => ({
    label: project.name || "Projeto",
    subtitle: project.location || "Sem local definido",
    href: "dashboard.html",
    group: "Projetos",
    icon: "bx-building-house",
    tag: "Projeto"
  }));

  return [...staticPages, ...requests, ...projects].map((item) => ({
    ...item,
    searchText: normalizeText(`${item.label} ${item.subtitle} ${item.group} ${item.tag}`)
  }));
}

function renderSearchResults(items) {
  if (!items.length) {
    return '<div class="dashboard-search-empty">Nenhum resultado para essa busca.</div>';
  }

  const grouped = items.reduce((accumulator, item) => {
    const bucket = accumulator.get(item.group) || [];
    bucket.push(item);
    accumulator.set(item.group, bucket);
    return accumulator;
  }, new Map());

  return [...grouped.entries()]
    .map(
      ([group, entries]) => `
        <section class="dashboard-search-group">
          <div class="dashboard-search-group-label">${group}</div>
          ${entries
            .map(
              (item, index) => `
                <button class="dashboard-search-item${index === 0 ? " is-active" : ""}" type="button" data-search-href="${item.href}">
                  <span class="dashboard-search-item-icon"><i class="bx ${item.icon}" aria-hidden="true"></i></span>
                  <span class="dashboard-search-item-copy">
                    <strong>${item.label}</strong>
                    <span>${item.subtitle}</span>
                  </span>
                  <span class="dashboard-search-item-tag">${item.tag}</span>
                </button>
              `
            )
            .join("")}
        </section>
      `
    )
    .join("");
}

function initDashboardSearch(overview) {
  const input = qs("#dashboardSearch");
  const results = qs("#dashboardSearchResults");
  if (!input || !results) return;

  const searchPool = buildSearchIndex(overview);
  let activeIndex = 0;

  const getButtons = () => [...results.querySelectorAll(".dashboard-search-item")];

  const syncActiveItem = () => {
    getButtons().forEach((button, index) => {
      button.classList.toggle("is-active", index === activeIndex);
    });
  };

  const closeResults = () => {
    results.classList.add("hidden");
    activeIndex = 0;
  };

  const openResults = () => {
    results.classList.remove("hidden");
  };

  const bindButtons = () => {
    getButtons().forEach((button) => {
      button.addEventListener("click", () => {
        const href = button.dataset.searchHref;
        if (href) window.location.href = href;
      });
    });
  };

  const runSearch = () => {
    const query = normalizeText(input.value);
    const matched = query
      ? searchPool.filter((item) => item.searchText.includes(query)).slice(0, 8)
      : searchPool.slice(0, 8);
    setHTML(results, renderSearchResults(matched));
    activeIndex = 0;
    syncActiveItem();
    openResults();
    bindButtons();
  };

  input.addEventListener("focus", runSearch);
  input.addEventListener("input", runSearch);

  input.addEventListener("keydown", (event) => {
    const buttons = getButtons();
    if (!buttons.length) return;

    if (event.key === "ArrowDown") {
      event.preventDefault();
      activeIndex = (activeIndex + 1) % buttons.length;
      syncActiveItem();
      return;
    }

    if (event.key === "ArrowUp") {
      event.preventDefault();
      activeIndex = (activeIndex - 1 + buttons.length) % buttons.length;
      syncActiveItem();
      return;
    }

    if (event.key === "Enter") {
      event.preventDefault();
      buttons[activeIndex]?.click();
      return;
    }

    if (event.key === "Escape") {
      closeResults();
    }
  });

  document.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      input.focus();
      input.select();
      runSearch();
    }
  });

  document.addEventListener("click", (event) => {
    if (results.classList.contains("hidden")) return;
    if (results.contains(event.target) || input.contains(event.target)) return;
    closeResults();
  });
}

function renderRecentRequests(rows) {
  if (!rows.length) {
    return '<tr><td colspan="4" class="app-empty">Nenhum pedido recente ainda. Abra a Cota para criar a primeira cotacao e acompanhar a fila por aqui.</td></tr>';
  }

  return rows
    .slice(0, 6)
    .map(
      (row) => `
        <tr>
          <td><div class="table-entity-meta"><strong>${row.request_code || row.id}</strong><small>${row.customer_name || "Pedido sem cliente"}</small></div></td>
          <td><span class="app-badge ${badgeClass(row.status)}">${formatStatus(row.status)}</span></td>
          <td>${row.best_supplier_name || "-"}</td>
          <td>${formatDateTime(row.updated_at || row.created_at)}</td>
        </tr>
      `
    )
    .join("");
}

function renderRecentRequestsMobile(rows) {
  if (!rows.length) {
    return `
      <article class="dashboard-recent-mobile-card dashboard-recent-mobile-card-empty">
        <div class="entity-list-copy">
          <p>Sem pedidos recentes</p>
          <strong>Abra a Cota para criar a primeira cotacao e acompanhar a fila por aqui.</strong>
        </div>
        <span class="app-badge is-muted">INFO</span>
      </article>
    `;
  }

  return rows
    .slice(0, 5)
    .map(
      (row) => `
        <article class="dashboard-recent-mobile-card">
          <div class="dashboard-recent-mobile-head">
            <div class="entity-list-copy">
              <p>${row.customer_name || "Pedido sem cliente"}</p>
              <strong>${row.request_code || row.id}</strong>
            </div>
            <span class="app-badge ${badgeClass(row.status)}">${formatStatus(row.status)}</span>
          </div>
          <div class="dashboard-recent-mobile-meta">
            <span><strong>Fornecedor:</strong> ${row.best_supplier_name || "-"}</span>
            <span><strong>Atualizado:</strong> ${formatDateTime(row.updated_at || row.created_at)}</span>
          </div>
          <div class="dashboard-recent-mobile-actions">
            <a class="btn btn-ghost" href="requests.html">Abrir comparador</a>
            <a class="btn btn-ghost" href="new-request.html">Ir para a Cota</a>
          </div>
        </article>
      `
    )
    .join("");
}

function renderTodayPriorityList(rows) {
  const priorityRows = [...rows]
    .sort((left, right) => {
      const getRank = (status) => {
        const normalized = String(status || "").toUpperCase();
        if (normalized === "ERROR") return 0;
        if (normalized === "AWAITING_APPROVAL") return 1;
        if (normalized === "PROCESSING") return 2;
        if (normalized === "PENDING_QUOTE") return 3;
        if (normalized === "DONE") return 4;
        return 5;
      };

      const rankDiff = getRank(left.status) - getRank(right.status);
      if (rankDiff !== 0) return rankDiff;
      return new Date(right.updated_at || right.created_at || 0) - new Date(left.updated_at || left.created_at || 0);
    })
    .slice(0, 4);

  if (!priorityRows.length) {
    return `
      <article class="dashboard-today-card dashboard-today-card-empty">
        <div class="entity-list-copy">
          <p>Nada critico por agora</p>
          <strong>Quando houver pedidos com risco, aprovacao pendente ou falha, eles aparecem aqui.</strong>
        </div>
        <span class="app-badge is-success">ESTAVEL</span>
      </article>
    `;
  }

  return priorityRows
    .map((row) => {
      const status = String(row.status || "").toUpperCase();
      const tone = badgeClass(status);
      const actionLabel =
        status === "ERROR"
          ? "Revisar cotacao"
          : status === "AWAITING_APPROVAL"
            ? "Liberar compra"
            : status === "DONE"
              ? "Fechar decisao"
              : "Acompanhar pedido";
      const detail =
        status === "ERROR"
          ? (row.last_error || "O pedido travou e pede nova tentativa ou ajuste.")
          : status === "AWAITING_APPROVAL"
            ? "Existe comparacao pronta aguardando decisao administrativa."
            : status === "DONE"
              ? `Melhor fornecedor: ${row.best_supplier_name || "definido"}.`
              : "A Cota ainda esta consolidando preco, prazo e melhor opcao.";

      return `
        <article class="dashboard-today-card">
          <div class="dashboard-today-card-head">
            <div class="entity-list-copy">
              <p>${row.customer_name || "Pedido sem cliente"}</p>
              <strong>${row.request_code || row.id}</strong>
            </div>
            <span class="app-badge ${tone}">${formatStatus(row.status)}</span>
          </div>
          <p class="dashboard-today-card-detail">${detail}</p>
          <div class="dashboard-today-card-meta">
            <span>${row.delivery_location || "Local pendente"}</span>
            <span>${formatDateTime(row.updated_at || row.created_at)}</span>
          </div>
          <div class="dashboard-today-card-actions">
            <a class="btn btn-primary" href="requests.html">${actionLabel}</a>
            <a class="btn btn-ghost" href="new-request.html">Abrir Cota</a>
          </div>
        </article>
      `;
    })
    .join("");
}

function renderStatusList(rows) {
  const grouped = [
    {
      label: "Em andamento",
      value: rows.filter((row) => ["PROCESSING", "PENDING_QUOTE"].includes(String(row.status || "").toUpperCase())).length,
      tone: "is-warning",
      copy: "Pedidos que ainda dependem do worker ou de resposta final."
    },
    {
      label: "Aguardando aprovacao",
      value: rows.filter((row) => String(row.status || "").toUpperCase() === "AWAITING_APPROVAL").length,
      tone: "is-warning",
      copy: "Pedidos parados por decisao administrativa."
    },
    {
      label: "Concluidos",
      value: rows.filter((row) => String(row.status || "").toUpperCase() === "DONE").length,
      tone: "is-success",
      copy: "Cotacoes que ja viraram comparacao fechada."
    },
    {
      label: "Com erro",
      value: rows.filter((row) => String(row.status || "").toUpperCase() === "ERROR").length,
      tone: "is-danger",
      copy: "Pedidos que precisam de nova tentativa ou ajuste no input."
    }
  ];

  return grouped
    .map(
      (item) => `
        <article class="dashboard-status-item">
          <header>
            <strong>${item.label}</strong>
            <span class="app-badge ${item.tone}">${item.value}</span>
          </header>
          <p>${item.copy}</p>
        </article>
      `
    )
    .join("");
}

function renderTopMaterials(items) {
  if (!items.length) {
    return '<article class="entity-list-item"><div class="entity-list-copy"><p>Sem demanda recente</p><strong>Os materiais entram aqui assim que os primeiros pedidos ou projetos forem registrados.</strong></div><span class="app-badge is-muted">INFO</span></article>';
  }

  return items
    .slice(0, 5)
    .map(
      (item) => `
        <article class="entity-list-item">
          <div class="entity-list-copy">
            <p>${item.name}</p>
            <strong>${item.count} cotacao(oes)</strong>
          </div>
          <span class="app-badge is-muted">MATERIAL</span>
        </article>
      `
    )
    .join("");
}

function renderActivity(rows) {
  const items = rows
    .slice(0, 6)
    .map((row) => {
      const status = String(row.status || "").toUpperCase();
      const tone = badgeClass(status);
      const title =
        status === "DONE"
          ? `${row.request_code || "Pedido"} concluido`
          : status === "ERROR"
            ? `${row.request_code || "Pedido"} com erro`
            : `${row.request_code || "Pedido"} em movimento`;
      const detail =
        status === "DONE"
          ? `Melhor fornecedor: ${row.best_supplier_name || "em definicao"}.`
          : status === "ERROR"
            ? "Vale revisar o pedido no historico para tentar novamente."
            : "A Cota ainda esta montando a comparacao final.";
      return { title, detail, tone, updatedAt: row.updated_at || row.created_at };
    });

  if (!items.length) {
    return '<article class="dashboard-status-item"><header><strong>Sem atividade recente</strong><span class="app-badge is-muted">INFO</span></header><p>Quando a equipe iniciar pedidos ou retomar projetos salvos, a linha do tempo operacional aparece aqui.</p></article>';
  }

  return items
    .map(
      (item) => `
        <article class="dashboard-status-item">
          <header>
            <strong>${item.title}</strong>
            <span class="app-badge ${item.tone}">${formatDateTime(item.updatedAt)}</span>
          </header>
          <p>${item.detail}</p>
        </article>
      `
    )
    .join("");
}

function renderSummaryList(overview, inFlightCount) {
  const items = [
    {
      label: "Fornecedor recorrente",
      value: overview.metrics.bestRecurringSupplier || "-",
      copy: "Bom sinal para negociar recorrencia ou consolidar volume."
    },
    {
      label: "Projetos ativos",
      value: String(overview.metrics.activeProjects || 0),
      copy: "Ajuda a medir a pressao de compra em aberto."
    },
    {
      label: "Tempo economizado",
      value: `${overview.metrics.estimatedTimeSavedHours || 0}h`,
      copy: "Estimativa operacional gerada pelo fluxo automatizado."
    },
    {
      label: "Fila viva",
      value: `${inFlightCount} pedido(s)`,
      copy: "Se esse numero subir, vale olhar worker e aprovacoes."
    }
  ];

  return items
    .map(
      (item) => `
        <article class="dashboard-status-item">
          <header>
            <strong>${item.label}</strong>
            <span class="app-badge is-muted">${item.value}</span>
          </header>
          <p>${item.copy}</p>
        </article>
      `
    )
    .join("");
}

async function init() {
  const session = await requireAuth(LOGIN_PATH);
  if (!session) return;

  initSidebar();
  setChatBackgroundPreference(getStoredChatBackgroundPreference());

  const companyLabel = getCompanyDisplayName(session.user);
  const companyInitials = getInitials(companyLabel);
  setText("#dashboardUserChip", companyInitials);
  setText("#companyNameSide", companyLabel);
  setText("#dashboardAvatar", companyInitials);
  setText("#dashboardRoleLabel", "Equipe de compras");

  qs("#dashboardLogoutButton")?.addEventListener("click", async () => {
    await signOut();
    window.location.replace(LOGIN_PATH);
  });

  try {
    const adminProfile = await getAdminProfile(session.user.id);
    showAdminShortcut(adminProfile);
  } catch (_) {
    showAdminShortcut(null);
  }

  try {
    const overview = await fetchProcurementOverview();
    const inFlightCount = overview.requests.filter((row) =>
      ["PROCESSING", "PENDING_QUOTE", "AWAITING_CONFIRMATION", "AWAITING_APPROVAL"].includes(String(row.status || "").toUpperCase())
    ).length;

    setText("#dashboardWelcome", `Acompanhe ${overview.requests.length} pedido(s) com foco em comparacao, fila e economia.`);
    setText("#metricRequests", String(overview.metrics.totalRequests));
    setText("#metricMaterialsQuoted", String(overview.metrics.totalMaterialsQuoted));
    setText("#metricSavings", formatCurrencyBRL(overview.metrics.estimatedSavings));
    setText("#metricInFlight", String(inFlightCount));
    setText("#metricRequestsMeta", `${overview.requests.filter((row) => String(row.status || "").toUpperCase() === "DONE").length} concluidos`);
    setText("#metricMaterialsMeta", `${overview.topMaterials[0]?.name || "Sem lideranca"} em destaque`);
    setText("#metricSavingsMeta", `${overview.metrics.suppliersConsulted || 0} fornecedores consultados`);
    setText("#metricInFlightMeta", `${overview.requests.filter((row) => String(row.status || "").toUpperCase() === "ERROR").length} com erro`);
    setText("#dashboardMobileHeroMeta", `${overview.requests.length} pedido(s) ativos ou historicos com leitura rapida para tomada de decisao.`);
    setText("#dashboardMobilePulseValue", `${inFlightCount} pedido(s)`);
    setText(
      "#dashboardMobilePulseMeta",
      `${overview.requests.filter((row) => String(row.status || "").toUpperCase() === "ERROR").length} com erro e ${overview.requests.filter((row) => String(row.status || "").toUpperCase() === "DONE").length} concluidos.`
    );
    setText("#dashboardMobileSupplierValue", overview.metrics.bestRecurringSupplier || "-");
    setText("#dashboardMobileSupplierMeta", `${overview.metrics.suppliersConsulted || 0} fornecedores consultados na base recente.`);

    setHTML("#dashboardTodayPriorityList", renderTodayPriorityList(overview.requests));
    setHTML("#dashboardRequestsTableBody", renderRecentRequests(overview.requests));
    setHTML("#dashboardRecentMobileList", renderRecentRequestsMobile(overview.requests));
    setHTML("#dashboardStatusList", renderStatusList(overview.requests));
    setHTML("#dashboardTopMaterials", renderTopMaterials(overview.topMaterials));
    setHTML("#dashboardActivityList", renderActivity(overview.requests));
    setHTML("#dashboardSummaryList", renderSummaryList(overview, inFlightCount));
    initDashboardSearch(overview);
    initCustomizer();
    initNotifications(buildNotifications(overview));

    if (overview.notices.length) {
      showFeedback("#dashboardFeedback", overview.notices.join(" "));
    }
  } catch (error) {
    showFeedback("#dashboardFeedback", error.message || "Nao foi possivel carregar o dashboard.");
    setHTML("#dashboardTodayPriorityList", '<article class="dashboard-today-card dashboard-today-card-empty"><div class="entity-list-copy"><p>Erro</p><strong>Erro ao carregar as prioridades do dia.</strong></div><span class="app-badge is-danger">ERRO</span></article>');
    setHTML("#dashboardRequestsTableBody", '<tr><td colspan="4" class="app-empty">Erro ao carregar pedidos.</td></tr>');
    setHTML("#dashboardRecentMobileList", '<article class="dashboard-recent-mobile-card dashboard-recent-mobile-card-empty"><div class="entity-list-copy"><p>Erro</p><strong>Erro ao carregar pedidos recentes.</strong></div><span class="app-badge is-danger">ERRO</span></article>');
  }
}

runPageBoot(init, { loadingMessage: "Carregando dashboard principal." }).catch((error) => {
  showFeedback("#dashboardFeedback", error.message || "Erro ao iniciar o dashboard.");
});
