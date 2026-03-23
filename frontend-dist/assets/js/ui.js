import { BILLING_ENABLED, CLIENT_DISABLED_PAGES, DASHBOARD_PATH, PLAN_SELECTION_ENABLED, WHATSAPP_NUMBER } from "./config.js";

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
let developmentModalElement = null;

const DISABLED_PAGE_SET = new Set(CLIENT_DISABLED_PAGES);
const DEVELOPMENT_PAGE_LABELS = {
  analytics: "Analytics",
  alerts: "Alertas",
  approvals: "Aprovacoes",
  comparisons: "Comparativos",
  "price-book": "Tabela de precos",
};

const SIDEBAR_ICON_MAP = {
  dashboard: "bx-grid-alt",
  analytics: "bx-bar-chart-alt-2",
  alerts: "bx-bell",
  new: "bx-bot",
  projects: "bx-briefcase-alt-2",
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

const CLIENT_BOTTOM_NAV_ITEMS = [
  { key: "dashboard", label: "Hoje", href: "dashboard.html", icon: "bx-grid-alt" },
  { key: "new", label: "Cota", href: "new-request.html", icon: "bx-bot" },
  { key: "requests", label: "Pedidos", href: "requests.html", icon: "bx-receipt" },
  { key: "projects", label: "Projetos", href: "projects.html", icon: "bx-briefcase-alt-2" },
  { key: "settings", label: "Conta", href: "settings.html", icon: "bx-cog" }
];

function getClientSidebarMarkup() {
  const plansLink = BILLING_ENABLED || PLAN_SELECTION_ENABLED
    ? `<a class="side-link" data-nav="plans" href="plans.html" title="Planos"><span class="left"><span class="nav-label">Planos</span></span></a>`
    : "";

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
      <p class="dashboard-nav-title">Fluxo principal</p>
      <nav class="app-nav" id="appNav">
        <div class="side-indicator" id="sideIndicator" aria-hidden="true"></div>
        <a class="side-link" data-nav="dashboard" href="dashboard.html" title="Dashboard"><span class="left"><span class="nav-label">Dashboard</span></span></a>
        <a class="side-link" data-nav="new" href="new-request.html" title="Nova cotacao"><span class="left"><span class="nav-label">Cota</span></span><span class="mini-badge">IA</span></a>
        <a class="side-link" data-nav="projects" href="projects.html" title="Projetos"><span class="left"><span class="nav-label">Projetos</span></span></a>
        <a class="side-link" data-nav="requests" href="requests.html" title="Pedidos"><span class="left"><span class="nav-label">Pedidos</span></span></a>
        ${plansLink}
      </nav>
    </div>

    <div class="dashboard-nav-group">
      <p class="dashboard-nav-title">Conta</p>
      <nav class="app-nav">
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
  const billingLink = BILLING_ENABLED
    ? `<a class="side-link" data-nav="admin-billing" href="admin-billing.html" title="Receita"><span class="left"><span class="nav-label">Receita</span></span></a>`
    : "";

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
        ${billingLink}
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

function shouldShowClientBottomNav(page = "") {
  const normalizedPage = String(page || "").trim();
  if (!normalizedPage) return false;
  if (normalizedPage.startsWith("admin-")) return false;
  return !["index", "login", "signup"].includes(normalizedPage);
}

function ensureClientBottomNav(page) {
  const normalizedPage = String(page || "").trim();
  const navKey = normalizedPage === "new-request" ? "new" : normalizedPage;
  const existing = document.getElementById("appMobileNav");
  const shouldShow = shouldShowClientBottomNav(normalizedPage);

  if (!shouldShow) {
    existing?.remove();
    document.body?.classList.remove("has-mobile-nav");
    return null;
  }

  const markup = `
    <nav class="app-mobile-nav" id="appMobileNav" aria-label="Navegacao principal">
      ${CLIENT_BOTTOM_NAV_ITEMS.map((item) => `
        <a class="app-mobile-nav-link${item.key === navKey ? " active" : ""}" data-nav="${item.key}" href="${item.href}" title="${item.label}">
          <i class="bx ${item.icon}" aria-hidden="true"></i>
          <span>${item.label}</span>
        </a>
      `).join("")}
    </nav>
  `;

  if (existing) {
    existing.outerHTML = markup;
  } else {
    document.body.insertAdjacentHTML("beforeend", markup);
  }

  document.body?.classList.add("has-mobile-nav");
  return document.getElementById("appMobileNav");
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

function ensureDevelopmentModal() {
  if (developmentModalElement?.isConnected) return developmentModalElement;
  developmentModalElement = document.createElement("div");
  developmentModalElement.className = "app-modal";
  developmentModalElement.id = "developmentModal";
  developmentModalElement.setAttribute("aria-hidden", "true");
  developmentModalElement.innerHTML = `
    <div class="app-modal-backdrop" data-close-modal="true"></div>
    <div class="app-modal-dialog">
      <button class="icon-btn" type="button" aria-label="Fechar" data-close-modal="true"></button>
      <div class="app-modal-copy">
        <span class="eyebrow">Em desenvolvimento</span>
        <h3 id="developmentModalTitle">Tela em desenvolvimento</h3>
        <p id="developmentModalMessage">Esta area ainda nao faz parte do fluxo principal publicado.</p>
      </div>
      <div class="app-modal-actions">
        <button class="btn btn-primary" type="button" id="developmentModalConfirm">Entendi</button>
      </div>
    </div>
  `;
  document.body.appendChild(developmentModalElement);
  decorateActionButtons(document);

  const close = () => {
    developmentModalElement?.classList.remove("show");
    document.body.style.overflow = "";
    developmentModalElement?.setAttribute("aria-hidden", "true");
  };

  developmentModalElement.querySelectorAll("[data-close-modal]").forEach((button) => {
    button.addEventListener("click", close);
  });
  developmentModalElement.querySelector("#developmentModalConfirm")?.addEventListener("click", close);
  return developmentModalElement;
}

export function showDevelopmentModal(pageKey = "") {
  const modal = ensureDevelopmentModal();
  const normalizedKey = String(pageKey || "").trim();
  const title = DEVELOPMENT_PAGE_LABELS[normalizedKey] || "Tela em desenvolvimento";
  const titleEl = qs("#developmentModalTitle", modal);
  const messageEl = qs("#developmentModalMessage", modal);
  if (titleEl) titleEl.textContent = title;
  if (messageEl) {
    messageEl.textContent = `${title} ainda esta em desenvolvimento e sera liberada em uma proxima etapa.`;
  }
  modal.classList.add("show");
  modal.setAttribute("aria-hidden", "false");
  document.body.style.overflow = "hidden";
}

function markDisabledNavigation(root = document) {
  root.querySelectorAll("a[data-nav]").forEach((link) => {
    const pageKey = String(link.dataset.nav || "").trim();
    if (!DISABLED_PAGE_SET.has(pageKey)) return;
    link.dataset.devDisabled = "true";
    link.setAttribute("aria-disabled", "true");
    link.classList.add("is-disabled");
    const existingTitle = link.getAttribute("title") || DEVELOPMENT_PAGE_LABELS[pageKey] || "Tela";
    link.setAttribute("title", `${existingTitle} - tela em desenvolvimento`);
  });
}

function bindDevelopmentNavigation(root = document) {
  root.addEventListener("click", (event) => {
    const link = event.target.closest("a[data-nav][data-dev-disabled='true']");
    if (!link) return;
    event.preventDefault();
    showDevelopmentModal(link.dataset.nav || "");
  });
}

function enforcePageAvailability(page) {
  const normalizedPage = String(page || "").trim();
  if (!DISABLED_PAGE_SET.has(normalizedPage)) return;
  window.setTimeout(() => {
    showDevelopmentModal(normalizedPage);
    window.setTimeout(() => {
      if (String(document.body?.dataset.page || "").trim() === normalizedPage) {
        window.location.replace(DASHBOARD_PATH);
      }
    }, 1600);
  }, 120);
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

  if (
    message.includes("companies_slug_key") ||
    (message.includes("duplicate key value") && message.includes("slug"))
  ) {
    return "Ja existe uma empresa com um nome muito parecido. Tente ajustar o nome da empresa para concluir o cadastro.";
  }

  if (
    message.includes("session_expired") ||
    message.includes("sessao expirada") ||
    message.includes("sua sessao expirou") ||
    message.includes("sessao invalida")
  ) {
    return "Sua sessao expirou. Entre novamente para continuar.";
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
  markDisabledNavigation(sidebar);
  bindDevelopmentNavigation(sidebar);
  const mobileNav = ensureClientBottomNav(page);
  markDisabledNavigation(mobileNav || document);
  if (mobileNav) bindDevelopmentNavigation(mobileNav);
  decorateActionButtons(document);
  normalizePageShell();
  document.body.classList.toggle("apex-shell", page !== "new-request");
  enforcePageAvailability(page);

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
  const heroShell = document.querySelector(".hero-shell");
  const parallaxNodes = [...document.querySelectorAll("[data-parallax]")];
  const scrollZoomNodes = [...document.querySelectorAll("[data-scroll-zoom]")];
  const storyDrives = [...document.querySelectorAll("[data-story-drive]")];
  const editorialDrives = [...document.querySelectorAll("[data-editorial-drive]")];
  const sceneSections = [...document.querySelectorAll("[data-scene-section]")];
  const maskedHeadings = [...document.querySelectorAll(
    ".hero-copy h1, .ai-copy h2, .light-title, .story-screen h3, .story-step-card h3, .section-title, .future-title, .final-cta-shell h2"
  )];
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  maskedHeadings.forEach((heading) => {
    heading.setAttribute("data-mask-reveal", "");
  });

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

  if (heroShell && !reduceMotion) {
    const updateHeroSpotlight = (event) => {
      const rect = heroShell.getBoundingClientRect();
      const relativeX = ((event.clientX - rect.left) / rect.width) * 100;
      const relativeY = ((event.clientY - rect.top) / rect.height) * 100;

      heroShell.style.setProperty("--hero-spotlight-x", `${Math.max(0, Math.min(100, relativeX)).toFixed(2)}%`);
      heroShell.style.setProperty("--hero-spotlight-y", `${Math.max(0, Math.min(100, relativeY)).toFixed(2)}%`);
    };

    const resetHeroSpotlight = () => {
      heroShell.style.setProperty("--hero-spotlight-x", "50%");
      heroShell.style.setProperty("--hero-spotlight-y", "24%");
    };

    heroShell.addEventListener("pointermove", updateHeroSpotlight, { passive: true });
    heroShell.addEventListener("pointerleave", resetHeroSpotlight, { passive: true });
  }

  if (parallaxNodes.length && !reduceMotion) {
    let parallaxTicking = false;

    const updateParallax = () => {
      const viewportHeight = window.innerHeight || 1;

      parallaxNodes.forEach((node) => {
        const strength = Number(node.getAttribute("data-parallax")) || 10;
        const rect = node.getBoundingClientRect();
        const progress = ((rect.top + rect.height * 0.5) - viewportHeight * 0.5) / viewportHeight;
        const offset = Math.max(-1, Math.min(1, progress)) * strength;
        const rotation = Math.max(-1, Math.min(1, progress)) * -1.5;
        node.style.transform = `translate3d(0, ${offset.toFixed(2)}px, 0) rotate(${rotation.toFixed(2)}deg)`;
      });

      parallaxTicking = false;
    };

    updateParallax();

    window.addEventListener("scroll", () => {
      if (parallaxTicking) return;
      parallaxTicking = true;
      window.requestAnimationFrame(updateParallax);
    }, { passive: true });

    window.addEventListener("resize", updateParallax, { passive: true });
  }

  if (scrollZoomNodes.length && !reduceMotion) {
    let scrollZoomTicking = false;

    const updateScrollZoom = () => {
      const viewportHeight = window.innerHeight || 1;

      scrollZoomNodes.forEach((node) => {
        const rect = node.getBoundingClientRect();
        const center = rect.top + rect.height * 0.5;
        const distanceFromCenter = (center - viewportHeight * 0.5) / viewportHeight;
        const clamped = Math.max(-1, Math.min(1, distanceFromCenter));
        const scaleOffset = (1 - Math.abs(clamped)) * 0.055;
        const translateY = clamped * 34;
        const opacity = 0.52 + (1 - Math.abs(clamped)) * 0.48;

        node.style.setProperty("--scroll-zoom-scale-offset", scaleOffset.toFixed(4));
        node.style.setProperty("--scroll-zoom-y", `${translateY.toFixed(2)}px`);
        node.style.setProperty("--scroll-zoom-opacity", opacity.toFixed(3));
      });

      scrollZoomTicking = false;
    };

    updateScrollZoom();

    window.addEventListener("scroll", () => {
      if (scrollZoomTicking) return;
      scrollZoomTicking = true;
      window.requestAnimationFrame(updateScrollZoom);
    }, { passive: true });

    window.addEventListener("resize", updateScrollZoom, { passive: true });
  }

  if (storyDrives.length) {
    storyDrives.forEach((drive) => {
      const steps = [...drive.querySelectorAll("[data-story-step]")];
      if (!steps.length) return;

      const setActiveStep = (index) => {
        drive.setAttribute("data-active-step", String(index));
        steps.forEach((step, stepIndex) => {
          step.classList.toggle("is-active", stepIndex === index);
        });
      };

      setActiveStep(0);

      if (reduceMotion || !("IntersectionObserver" in window)) {
        return;
      }

      const storyObserver = new IntersectionObserver((entries) => {
        const visibleEntries = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio);

        if (!visibleEntries.length) return;

        const activeIndex = Number(visibleEntries[0].target.getAttribute("data-story-step")) || 0;
        setActiveStep(activeIndex);
      }, {
        threshold: [0.35, 0.55, 0.75],
        rootMargin: "-10% 0px -25% 0px"
      });

      steps.forEach((step) => storyObserver.observe(step));
    });
  }

  if (editorialDrives.length) {
    editorialDrives.forEach((drive) => {
      const steps = [...drive.querySelectorAll("[data-editorial-step]")];
      if (!steps.length) return;

      const setActiveSlide = (index) => {
        drive.setAttribute("data-active-slide", String(index));
      };

      setActiveSlide(0);

      if (reduceMotion || !("IntersectionObserver" in window)) {
        return;
      }

      const editorialObserver = new IntersectionObserver((entries) => {
        const visibleEntries = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio);

        if (!visibleEntries.length) return;

        const activeIndex = Number(visibleEntries[0].target.getAttribute("data-editorial-step")) || 0;
        setActiveSlide(activeIndex);
      }, {
        threshold: [0.3, 0.55, 0.8],
        rootMargin: "-8% 0px -12% 0px"
      });

      steps.forEach((step) => editorialObserver.observe(step));
    });
  }

  if (sceneSections.length) {
    const setScene = (scene) => {
      if (!document.body?.classList.contains("landing-page")) return;
      document.body.dataset.scene = scene || "hero";
    };

    setScene(document.body?.dataset.scene || "hero");

    if (!reduceMotion && "IntersectionObserver" in window) {
      const sceneObserver = new IntersectionObserver((entries) => {
        const visibleEntries = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio);

        if (!visibleEntries.length) return;

        const activeScene = visibleEntries[0].target.getAttribute("data-scene-section") || "hero";
        setScene(activeScene);
      }, {
        threshold: [0.2, 0.4, 0.65],
        rootMargin: "-12% 0px -18% 0px"
      });

      sceneSections.forEach((section) => sceneObserver.observe(section));
    }
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
