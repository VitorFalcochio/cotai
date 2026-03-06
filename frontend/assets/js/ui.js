import { WHATSAPP_NUMBER } from "./config.js";

export const qs = (selector, root = document) => root.querySelector(selector);

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
    return "Seu e-mail ainda nao foi confirmado. Verifique sua caixa de entrada.";
  }

  return rawMessage;
}

export function setLoading(button, loading, label = "Salvar") {
  if (!button) return;
  button.disabled = loading;
  button.textContent = loading ? "Carregando..." : label;
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
