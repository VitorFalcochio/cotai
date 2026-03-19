import { WHATSAPP_NUMBER } from "./config.js";

export const qs = (selector, root = document) => root.querySelector(selector);

const THEME_STORAGE_KEY = "cotai_theme_preference";
const THEME_OPTIONS = ["system", "light", "dark"];
const ACCENT_STORAGE_KEY = "cotai_accent_preference";
const ACCENT_OPTIONS = ["emerald", "blue", "violet", "rose", "orange", "slate"];
const DENSITY_STORAGE_KEY = "cotai_density_preference";
const DENSITY_OPTIONS = ["compact", "comfortable", "spacious"];
const BOXICONS_STYLESHEET_ID = "cotai-boxicons-stylesheet";
let themeControlElement = null;
let themeMediaQuery = null;
let toastStackElement = null;

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
  settings: "bx-cog",
  "admin-dashboard": "bx-home-circle",
  "admin-companies": "bx-buildings",
  "admin-users": "bx-user-circle",
  "admin-requests": "bx-spreadsheet",
  "admin-worker": "bx-bot",
  "admin-snapshots": "bx-line-chart",
  "admin-billing": "bx-wallet",
  "admin-logs": "bx-file"
};

const ACTION_ICON_MAP = {
  sidebarToggle: "bx-menu-alt-left",
  sidebarCollapse: "bx-chevrons-left",
  logoutButton: "bx-log-out",
  backToClientButton: "bx-left-arrow-alt",
  newSupplierBtn: "bx-plus",
  requestsExportCsv: "bx-export"
};

function getClientSidebarMarkup() {
  return `
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
      <p class="dashboard-nav-title">Nucleo</p>
      <nav class="app-nav" id="appNav">
        <div class="side-indicator" id="sideIndicator" aria-hidden="true"></div>
        <a class="side-link" data-nav="dashboard" href="dashboard.html" title="Dashboard"><span class="left"><span class="nav-label">Dashboard</span></span></a>
        <a class="side-link" data-nav="new" href="new-request.html" title="Nova cotacao"><span class="left"><span class="nav-label">Cota</span></span><span class="mini-badge">IA</span></a>
        <a class="side-link" data-nav="requests" href="requests.html" title="Pedidos"><span class="left"><span class="nav-label">Pedidos</span></span></a>
      </nav>
    </div>

    <div class="dashboard-nav-group">
      <p class="dashboard-nav-title">Decisao</p>
      <nav class="app-nav">
        <a class="side-link" data-nav="suppliers" href="suppliers.html" title="Fornecedores"><span class="left"><span class="nav-label">Fornecedores</span></span></a>
        <a class="side-link" data-nav="materials" href="materials.html" title="Materiais"><span class="left"><span class="nav-label">Materiais</span></span></a>
        <a class="side-link" data-nav="price-book" href="price-book.html" title="Tabela de precos"><span class="left"><span class="nav-label">Tabela de precos</span></span></a>
      </nav>
    </div>

    <div class="dashboard-nav-group">
      <p class="dashboard-nav-title">Depois</p>
      <nav class="app-nav">
        <a class="side-link" data-nav="analytics" href="analytics.html" title="Analytics"><span class="left"><span class="nav-label">Analytics</span></span></a>
        <a class="side-link" data-nav="alerts" href="alerts.html" title="Alertas"><span class="left"><span class="nav-label">Alertas</span></span></a>
        <a class="side-link" data-nav="approvals" href="approvals.html" title="Aprovacoes"><span class="left"><span class="nav-label">Aprovacoes</span></span></a>
        <a class="side-link" data-nav="comparisons" href="comparisons.html" title="Comparativos"><span class="left"><span class="nav-label">Comparativos</span></span></a>
        <a class="side-link" data-nav="plans" href="plans.html" title="Planos"><span class="left"><span class="nav-label">Planos</span></span></a>
        <a class="side-link" data-nav="settings" href="settings.html" title="Configuracoes"><span class="left"><span class="nav-label">Configuracoes</span></span></a>
      </nav>
    </div>

    <div class="dashboard-sidebar-divider"></div>

    <div class="dashboard-sidebar-profile">
      <div class="dashboard-avatar" id="dashboardAvatar">CO</div>
      <div>
        <strong id="companyNameSide">Cotai</strong>
        <span id="dashboardRoleLabel">Equipe de compras</span>
      </div>
      <a class="dashboard-profile-link" href="settings.html" aria-label="Abrir perfil"><i class="bx bx-log-in-circle" aria-hidden="true"></i></a>
    </div>
  `;
}

function getAdminSidebarMarkup() {
  return `
    <div class="side-shell-head dashboard-brand-head">
      <a class="brand dashboard-brand" href="admin-dashboard.html">
        <span class="brand-mark"><i class="bx bx-shield-quarter" aria-hidden="true"></i></span>
        <span class="brand-copy">
          <span class="brand-name">Cotai</span>
          <span class="brand-meta">Admin</span>
        </span>
      </a>
      <button class="btn btn-ghost side-collapse-btn" type="button" id="sidebarCollapse" aria-label="Colapsar menu" aria-expanded="true" data-icon-only="true">
        <span class="collapse-arrow" aria-hidden="true"></span>
      </button>
    </div>

    <div class="dashboard-nav-group">
      <p class="dashboard-nav-title">Core</p>
      <nav class="app-nav" id="appNav">
        <div class="side-indicator" id="sideIndicator" aria-hidden="true"></div>
        <a class="side-link" data-nav="admin-dashboard" href="admin-dashboard.html" title="Visao geral"><span class="left"><span class="nav-label">Visao geral</span></span></a>
        <a class="side-link" data-nav="admin-requests" href="admin-requests.html" title="Pedidos"><span class="left"><span class="nav-label">Pedidos</span></span></a>
        <a class="side-link" data-nav="admin-worker" href="admin-worker.html" title="Worker"><span class="left"><span class="nav-label">Worker</span></span></a>
      </nav>
    </div>

    <div class="dashboard-nav-group">
      <p class="dashboard-nav-title">Plataforma</p>
      <nav class="app-nav dashboard-subnav">
        <a class="side-link" data-nav="admin-companies" href="admin-companies.html" title="Empresas"><span class="left"><span class="nav-label">Empresas</span></span></a>
        <a class="side-link" data-nav="admin-users" href="admin-users.html" title="Usuarios"><span class="left"><span class="nav-label">Usuarios</span></span></a>
        <a class="side-link" data-nav="admin-billing" href="admin-billing.html" title="Receita"><span class="left"><span class="nav-label">Receita</span></span></a>
      </nav>
    </div>

    <div class="dashboard-nav-group">
      <p class="dashboard-nav-title">Depois</p>
      <nav class="app-nav dashboard-subnav">
        <a class="side-link" data-nav="admin-snapshots" href="admin-snapshots.html" title="Snapshots"><span class="left"><span class="nav-label">Snapshots</span></span></a>
        <a class="side-link" data-nav="admin-logs" href="admin-logs.html" title="Logs"><span class="left"><span class="nav-label">Logs</span></span></a>
      </nav>
    </div>

    <div class="dashboard-sidebar-divider"></div>

    <div class="dashboard-sidebar-profile">
      <div class="dashboard-avatar">AD</div>
      <div>
        <strong id="adminIdentitySide">Admin Cotai</strong>
        <span>Controle da plataforma</span>
      </div>
      <a class="dashboard-profile-link" href="dashboard.html" aria-label="Voltar ao cliente"><i class="bx bx-right-arrow-alt" aria-hidden="true"></i></a>
    </div>
  `;
}

function standardizeSidebarMarkup(sidebar, page) {
  if (!sidebar) return;
  const isAdminPage = String(page || "").startsWith("admin-");
  sidebar.classList.add("dashboard-apex-sidebar");
  sidebar.innerHTML = isAdminPage ? getAdminSidebarMarkup() : getClientSidebarMarkup();
}

function ensureBoxicons() {
  if (document.getElementById(BOXICONS_STYLESHEET_ID)) return;
  const link = document.createElement("link");
  link.id = BOXICONS_STYLESHEET_ID;
  link.rel = "stylesheet";
  link.href = "https://unpkg.com/boxicons@2.1.4/css/boxicons.min.css";
  document.head.appendChild(link);
}

function decorateSidebarNav(nav) {
  if (!nav) return;
  nav.querySelectorAll(".side-link").forEach((link) => {
    if (link.querySelector(".side-link-icon")) return;
    const navKey = link.dataset.nav || "";
    const iconName = SIDEBAR_ICON_MAP[navKey] || "bx-circle";
    const label = link.querySelector(".nav-label");
    const left = link.querySelector(".left");
    if (!label || !left) return;
    const icon = document.createElement("i");
    icon.className = `bx ${iconName} side-link-icon`;
    icon.setAttribute("aria-hidden", "true");
    left.prepend(icon);
  });
}

function decorateAllSidebarNavs(sidebar) {
  if (!sidebar) return;
  sidebar.querySelectorAll(".app-nav").forEach((nav) => decorateSidebarNav(nav));
}

function decorateActionButtons(root = document) {
  Object.entries(ACTION_ICON_MAP).forEach(([id, iconName]) => {
    const element = root.getElementById ? root.getElementById(id) : qs(`#${id}`, root);
    if (!element || element.querySelector(".btn-icon")) return;
    const iconOnly = element.dataset.iconOnly === "true" || element.classList.contains("side-collapse-btn");
    const label = iconOnly ? "" : element.textContent.trim();
    element.innerHTML = label
      ? `<i class="bx ${iconName} btn-icon" aria-hidden="true"></i><span>${label}</span>`
      : `<i class="bx ${iconName} btn-icon" aria-hidden="true"></i>`;
  });

  root.querySelectorAll('.icon-btn:not([data-apex-iconized]), [data-close-modal]:not([data-apex-iconized])').forEach((button) => {
    button.dataset.apexIconized = "true";
    if (button.dataset.closeModal !== undefined) {
      button.innerHTML = '<i class="bx bx-x" aria-hidden="true"></i>';
    }
  });
}

function getStoredThemePreference() {
  const stored = String(window.localStorage.getItem(THEME_STORAGE_KEY) || "system").trim().toLowerCase();
  return THEME_OPTIONS.includes(stored) ? stored : "system";
}

function getStoredAccentPreference() {
  const stored = String(window.localStorage.getItem(ACCENT_STORAGE_KEY) || "emerald").trim().toLowerCase();
  return ACCENT_OPTIONS.includes(stored) ? stored : "emerald";
}

function getStoredDensityPreference() {
  const stored = String(window.localStorage.getItem(DENSITY_STORAGE_KEY) || "comfortable").trim().toLowerCase();
  return DENSITY_OPTIONS.includes(stored) ? stored : "comfortable";
}

function getSystemTheme() {
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function resolveTheme(themePreference) {
  return themePreference === "system" ? getSystemTheme() : themePreference;
}

function updateThemeControl(themePreference, resolvedTheme) {
  if (!themeControlElement) return;
  const checkbox = qs(".checkbox", themeControlElement);
  if (!checkbox) return;
  checkbox.checked = resolvedTheme === "light";
  checkbox.setAttribute("aria-label", resolvedTheme === "dark" ? "Ativar tema claro" : "Ativar tema escuro");
  checkbox.setAttribute("title", resolvedTheme === "dark" ? "Tema escuro ativo" : "Tema claro ativo");
}

export function applyThemePreference(themePreference = getStoredThemePreference()) {
  const nextPreference = THEME_OPTIONS.includes(themePreference) ? themePreference : "system";
  const resolvedTheme = resolveTheme(nextPreference);

  document.documentElement.dataset.theme = resolvedTheme;
  document.documentElement.dataset.themePreference = nextPreference;
  document.documentElement.style.colorScheme = resolvedTheme;
  document.body?.setAttribute("data-theme", resolvedTheme);
  document.body?.setAttribute("data-theme-preference", nextPreference);
  updateThemeControl(nextPreference, resolvedTheme);

  return { preference: nextPreference, resolvedTheme };
}

export function setThemePreference(themePreference) {
  const nextPreference = THEME_OPTIONS.includes(themePreference) ? themePreference : "system";
  window.localStorage.setItem(THEME_STORAGE_KEY, nextPreference);
  return applyThemePreference(nextPreference);
}

export function applyAccentPreference(accentPreference = getStoredAccentPreference()) {
  const nextPreference = ACCENT_OPTIONS.includes(accentPreference) ? accentPreference : "emerald";
  document.documentElement.dataset.accent = nextPreference;
  document.body?.setAttribute("data-accent", nextPreference);
  return nextPreference;
}

export function setAccentPreference(accentPreference) {
  const nextPreference = ACCENT_OPTIONS.includes(accentPreference) ? accentPreference : "emerald";
  window.localStorage.setItem(ACCENT_STORAGE_KEY, nextPreference);
  return applyAccentPreference(nextPreference);
}

export function applyDensityPreference(densityPreference = getStoredDensityPreference()) {
  const nextPreference = DENSITY_OPTIONS.includes(densityPreference) ? densityPreference : "comfortable";
  document.documentElement.dataset.density = nextPreference;
  document.body?.setAttribute("data-density", nextPreference);
  return nextPreference;
}

export function setDensityPreference(densityPreference) {
  const nextPreference = DENSITY_OPTIONS.includes(densityPreference) ? densityPreference : "comfortable";
  window.localStorage.setItem(DENSITY_STORAGE_KEY, nextPreference);
  return applyDensityPreference(nextPreference);
}

function ensureThemeControl() {
  if (themeControlElement?.isConnected || !document.body) return themeControlElement;
  if (!document.body.classList.contains("landing-page")) return null;
  themeControlElement = qs("#landingThemeSwitcher");
  if (!themeControlElement) return null;

  const checkbox = qs(".checkbox", themeControlElement);
  checkbox?.addEventListener("change", () => {
    setThemePreference(checkbox.checked ? "light" : "dark");
  });

  const { preference, resolvedTheme } = applyThemePreference();
  updateThemeControl(preference, resolvedTheme);
  return themeControlElement;
}

export function initThemeSystem() {
  if (!themeMediaQuery) {
    themeMediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
    themeMediaQuery.addEventListener("change", () => {
      if (getStoredThemePreference() === "system") {
        applyThemePreference("system");
      }
    });
  }

  applyThemePreference();
  applyAccentPreference();
  applyDensityPreference();
  ensureBoxicons();

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => ensureThemeControl(), { once: true });
  } else {
    ensureThemeControl();
  }
}

initThemeSystem();

let appBootElement = null;
let appBootStartedAt = 0;

function ensureAppBootElement() {
  if (appBootElement?.isConnected) return appBootElement;

  appBootElement = document.createElement("div");
  appBootElement.className = "app-boot";
  appBootElement.setAttribute("aria-live", "polite");
  appBootElement.innerHTML = `
    <div class="app-boot-card" role="status">
      <div class="app-boot-loader" aria-hidden="true">
        <div class="loader">
          <div class="loader__bar"></div>
          <div class="loader__bar"></div>
          <div class="loader__bar"></div>
          <div class="loader__bar"></div>
          <div class="loader__bar"></div>
          <div class="loader__ball"></div>
        </div>
      </div>
      <div class="app-boot-copy">
        <strong id="appBootTitle">Carregando Cotai</strong>
        <span id="appBootMessage">Preparando a interface.</span>
      </div>
    </div>
  `;
  document.body.appendChild(appBootElement);
  return appBootElement;
}

export function startAppBoot(message = "Preparando a interface.") {
  const boot = ensureAppBootElement();
  appBootStartedAt = Date.now();
  document.body.classList.add("app-booting");
  boot.classList.remove("is-hidden", "is-error");
  const messageEl = qs("#appBootMessage", boot);
  if (messageEl) messageEl.textContent = message;
}

export function updateAppBoot(message = "Carregando.") {
  const boot = ensureAppBootElement();
  const messageEl = qs("#appBootMessage", boot);
  if (messageEl) messageEl.textContent = message;
}

export async function finishAppBoot(minDurationMs = 450) {
  const boot = ensureAppBootElement();
  const elapsed = Date.now() - appBootStartedAt;
  const waitMs = Math.max(0, minDurationMs - elapsed);
  if (waitMs) {
    await new Promise((resolve) => window.setTimeout(resolve, waitMs));
  }
  boot.classList.add("is-hidden");
  document.body.classList.remove("app-booting");
}

export function failAppBoot(message = "Não foi possível concluir o carregamento.") {
  const boot = ensureAppBootElement();
  boot.classList.add("is-error");
  const titleEl = qs("#appBootTitle", boot);
  const messageEl = qs("#appBootMessage", boot);
  if (titleEl) titleEl.textContent = "Inicializacao incompleta";
  if (messageEl) messageEl.textContent = message;
  window.setTimeout(() => {
    boot.classList.add("is-hidden");
    document.body.classList.remove("app-booting");
  }, 1200);
}

export async function runPageBoot(init, options = {}) {
  const { loadingMessage = "Preparando a interface." } = options;
  startAppBoot(loadingMessage);
  try {
    const result = await init();
    await finishAppBoot();
    return result;
  } catch (error) {
    failAppBoot(String(error?.message || error || "Erro de inicializacao."));
    throw error;
  }
}

export function setText(selector, value) {
  const element = typeof selector === "string" ? qs(selector) : selector;
  if (element) element.textContent = value;
}

export function setHTML(selector, value) {
  const element = typeof selector === "string" ? qs(selector) : selector;
  if (element) element.innerHTML = value;
}

export function toggleHidden(selector, shouldHide) {
  const element = typeof selector === "string" ? qs(selector) : selector;
  if (!element) return;
  element.classList.toggle("hidden", shouldHide);
}

export function showFeedback(selector, message = "", isError = true) {
  const element = typeof selector === "string" ? qs(selector) : selector;
  if (!element) return;

  element.textContent = message;
  element.classList.toggle("hidden", !message);
  element.classList.toggle("is-success", Boolean(message) && !isError);
}

function ensureToastStack() {
  if (toastStackElement?.isConnected) return toastStackElement;
  toastStackElement = document.createElement("div");
  toastStackElement.className = "app-toast-stack";
  toastStackElement.setAttribute("aria-live", "polite");
  toastStackElement.setAttribute("aria-label", "Notificacoes");
  document.body.appendChild(toastStackElement);
  return toastStackElement;
}

export function showAppToast({
  tone = "success",
  icon = "bx-check-circle",
  title = "Atualizacao",
  message = "",
  actionLabel = "",
  onAction = null,
  duration = 5000,
} = {}) {
  const stack = ensureToastStack();
  const toast = document.createElement("article");
  toast.className = `app-toast is-${tone}`;
  toast.setAttribute("role", "status");
  toast.innerHTML = `
    <div class="app-toast-icon" aria-hidden="true"><i class="bx ${icon}"></i></div>
    <div class="app-toast-copy">
      <strong>${title}</strong>
      <p>${message}</p>
    </div>
    <div class="app-toast-actions">
      ${actionLabel ? `<button class="app-toast-action" type="button">${actionLabel}</button>` : ""}
      <button class="app-toast-close" type="button" aria-label="Fechar notificacao">
        <i class="bx bx-x" aria-hidden="true"></i>
      </button>
    </div>
  `;

  const removeToast = () => {
    toast.classList.add("is-leaving");
    window.setTimeout(() => toast.remove(), 220);
  };

  toast.querySelector(".app-toast-close")?.addEventListener("click", removeToast);
  toast.querySelector(".app-toast-action")?.addEventListener("click", () => {
    if (typeof onAction === "function") onAction();
    removeToast();
  });

  stack.appendChild(toast);
  window.requestAnimationFrame(() => {
    toast.classList.add("is-visible");
  });

  if (duration > 0) {
    window.setTimeout(removeToast, duration);
  }

  return toast;
}

export function getReadableError(error, fallback = "Ocorreu um erro inesperado.") {
  const rawMessage = String(error?.message || error || "").trim();
  const message = rawMessage.toLowerCase();

  if (!rawMessage) return fallback;

  if (
    message.includes("failed to fetch") ||
    message.includes("fetch failed") ||
    message.includes("networkerror") ||
    message.includes("load failed")
  ) {
    return "Falha de conexao com o Supabase. Verifique se a SUPABASE_URL esta correta, se o projeto existe e se sua internet esta funcionando.";
  }

  if (
    message.includes("invalid api key") ||
    message.includes("apikey") ||
    message.includes("anonymous key") ||
    message.includes("publishable")
  ) {
    return "Chave publica do Supabase invalida. Revise a SUPABASE_ANON_KEY em frontend/assets/js/config.js.";
  }

  if (message.includes("user already registered")) {
    return "Este e-mail ja esta cadastrado.";
  }

  if (message.includes("invalid login credentials")) {
    return "E-mail ou senha invalidos.";
  }

  if (message.includes("email not confirmed")) {
    return "Seu e-mail ainda não foi confirmado. Verifique sua caixa de entrada.";
  }

  return rawMessage;
}

export function setLoading(button, loading, label = "Salvar", loadingLabel = "Carregando...") {
  if (!button) return;
  button.disabled = loading;
  button.textContent = loading ? loadingLabel : label;
}

export function setTableSkeleton(selector, columns = 4, rows = 4) {
  const element = typeof selector === "string" ? qs(selector) : selector;
  if (!element) return;

  element.innerHTML = Array.from({ length: rows })
    .map(
      () => `
        <tr class="skeleton-row">
          ${Array.from({ length: columns })
            .map(() => '<td><div class="skeleton">&nbsp;</div></td>')
            .join("")}
        </tr>
      `
    )
    .join("");
}

export function formatDateTime(value) {
  if (!value) return "-";
  return new Date(value).toLocaleString("pt-BR", {
    dateStyle: "short",
    timeStyle: "short"
  });
}

export async function copyText(text) {
  await navigator.clipboard.writeText(text);
}

export function openWhatsApp(text) {
  const url = `https://wa.me/${WHATSAPP_NUMBER}?text=${encodeURIComponent(text)}`;
  window.open(url, "_blank", "noopener,noreferrer");
}

function normalizePageShell() {
  const appMain = qs(".app-main");
  if (!appMain) return;

  const topbar = appMain.querySelector(":scope > .app-topbar");
  if (!topbar || appMain.querySelector(":scope > .page")) return;

  const page = document.createElement("main");
  page.className = "page";

  while (topbar.nextSibling) {
    page.appendChild(topbar.nextSibling);
  }

  appMain.appendChild(page);
}

export function initSidebar() {
  const page = document.body.dataset.page;
  const current = page === "new-request" ? "new" : page;
  const sidebar = qs("#appSidebar");
  const collapseStorageKey = "cotai_sidebar_collapsed";
  const mobileBreakpoint = window.matchMedia("(max-width: 920px)");

  ensureBoxicons();
  standardizeSidebarMarkup(sidebar, page);
  const nav = qs("#appNav");
  const indicator = qs("#sideIndicator");
  const toggle = qs("#sidebarToggle");
  const collapseButton = qs("#sidebarCollapse");
  const overlay = qs("#appDrawerOverlay");
  if (!sidebar || !nav) return;
  decorateAllSidebarNavs(sidebar);
  decorateActionButtons(document);
  normalizePageShell();
  document.body.classList.toggle("apex-shell", page !== "new-request");

  const activeLink = sidebar.querySelector(`.side-link[data-nav="${current}"]`);
  if (activeLink) activeLink.classList.add("active");

  const moveIndicator = () => {
    if (!indicator || !activeLink) return;
    const navRect = nav.getBoundingClientRect();
    const linkRect = activeLink.getBoundingClientRect();
    indicator.style.transform = `translateY(${Math.round(linkRect.top - navRect.top)}px)`;
    indicator.style.height = `${Math.round(linkRect.height)}px`;
    indicator.style.opacity = "1";
  };

  const setDrawerState = (isOpen) => {
    document.body.classList.toggle("drawer-open", isOpen);
    if (toggle) toggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
  };

  const setCollapsedState = (isCollapsed) => {
    if (mobileBreakpoint.matches) return;
    document.body.classList.toggle("sidebar-collapsed", isCollapsed);
    sidebar.classList.toggle("is-collapsed", isCollapsed);
    localStorage.setItem(collapseStorageKey, isCollapsed ? "1" : "0");
    if (collapseButton) {
      collapseButton.setAttribute("aria-expanded", isCollapsed ? "false" : "true");
      collapseButton.setAttribute("aria-label", isCollapsed ? "Expandir menu" : "Colapsar menu");
      const icon = collapseButton.querySelector(".btn-icon, .bx");
      if (icon) {
        icon.className = `bx ${isCollapsed ? "bx-chevrons-right" : "bx-chevrons-left"} btn-icon`;
      }
    }
    requestAnimationFrame(moveIndicator);
  };

  setCollapsedState(localStorage.getItem(collapseStorageKey) === "1");

  collapseButton?.addEventListener("click", () => {
    setCollapsedState(!sidebar.classList.contains("is-collapsed"));
  });

  toggle?.addEventListener("click", () => {
    if (mobileBreakpoint.matches) {
      setDrawerState(!document.body.classList.contains("drawer-open"));
      return;
    }

    setCollapsedState(!sidebar.classList.contains("is-collapsed"));
  });

  overlay?.addEventListener("click", () => setDrawerState(false));

  window.addEventListener("resize", () => {
    if (mobileBreakpoint.matches) {
      document.body.classList.remove("sidebar-collapsed");
      sidebar.classList.remove("is-collapsed");
    } else {
      setDrawerState(false);
      setCollapsedState(localStorage.getItem(collapseStorageKey) === "1");
    }

    requestAnimationFrame(moveIndicator);
  });

  nav.addEventListener("click", (event) => {
    if (event.target.closest(".side-link") && mobileBreakpoint.matches) {
      setDrawerState(false);
    }
  });

  requestAnimationFrame(moveIndicator);
  window.addEventListener("load", moveIndicator, { once: true });
}

export function initLandingMotion() {
  const header = document.querySelector(".header");
  const animatedSections = [...document.querySelectorAll("[data-animate]")];
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  if (header) {
    let ticking = false;
    const updateHeaderState = () => {
      header.classList.toggle("is-scrolled", window.scrollY > 18);
      ticking = false;
    };

    updateHeaderState();

    window.addEventListener("scroll", () => {
      if (ticking) return;
      ticking = true;
      window.requestAnimationFrame(updateHeaderState);
    }, { passive: true });
  }

  if (!animatedSections.length) return;

  animatedSections.forEach((element, index) => {
    element.classList.add("animate");
    element.dataset.animateDelay = String(index % 4);
  });

  if (reduceMotion || !("IntersectionObserver" in window)) {
    animatedSections.forEach((element) => element.classList.add("animate-visible"));
    return;
  }

  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      entry.target.classList.add("animate-visible");
      observer.unobserve(entry.target);
    });
  }, {
    threshold: 0.16,
    rootMargin: "0px 0px -8% 0px"
  });

  animatedSections.forEach((element) => observer.observe(element));
}
