import { WHATSAPP_NUMBER } from "./config.js";

export const qs = (selector, root = document) => root.querySelector(selector);

const THEME_STORAGE_KEY = "cotai_theme_preference";
const THEME_OPTIONS = ["system", "light", "dark"];
let themeControlElement = null;
let themeMediaQuery = null;

function getStoredThemePreference() {
  const stored = String(window.localStorage.getItem(THEME_STORAGE_KEY) || "system").trim().toLowerCase();
  return THEME_OPTIONS.includes(stored) ? stored : "system";
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

export function initSidebar() {
  const page = document.body.dataset.page;
  const current = page === "new-request" ? "new" : page;
  const sidebar = qs("#appSidebar");
  const nav = qs("#appNav");
  const indicator = qs("#sideIndicator");
  const toggle = qs("#sidebarToggle");
  const collapseButton = qs("#sidebarCollapse");
  const overlay = qs("#appDrawerOverlay");
  const collapseStorageKey = "cotai_sidebar_collapsed";
  const mobileBreakpoint = window.matchMedia("(max-width: 920px)");

  if (!sidebar || !nav) return;

  const activeLink = nav.querySelector(`.side-link[data-nav="${current}"]`);
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
