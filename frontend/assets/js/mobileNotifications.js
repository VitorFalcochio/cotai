import { getProfile } from "./auth.js";
import { supabase } from "./supabaseClient.js";
import { showAppToast } from "./ui.js";

const SETTINGS_STORAGE_KEY = "cotai_settings";
const PROMPT_STORAGE_KEY = "cotai_notification_prompt_dismissed_v1";
const SEEN_EVENT_STORAGE_KEY = "cotai_seen_request_notifications_v1";
const CHANNEL_STORAGE_KEY = "__cotai_mobile_notification_channel__";
const MANIFEST_ID = "cotai-manifest-link";
const INTERESTING_STATUSES = new Set(["DONE", "ERROR", "AWAITING_APPROVAL"]);

let channel = null;
let channelCompanyId = "";
let knownStatusMap = new Map();
let promptShown = false;

function isMobileViewport() {
  return window.matchMedia("(max-width: 768px)").matches;
}

function readSettings() {
  try {
    return JSON.parse(window.localStorage.getItem(SETTINGS_STORAGE_KEY) || "{}");
  } catch (_) {
    return {};
  }
}

function writeSettings(nextSettings) {
  window.localStorage.setItem(SETTINGS_STORAGE_KEY, JSON.stringify(nextSettings));
}

function areNotificationsEnabled() {
  const settings = readSettings();
  return settings.notifications !== false;
}

export function setNotificationsEnabled(enabled) {
  const nextSettings = { ...readSettings(), notifications: Boolean(enabled) };
  writeSettings(nextSettings);
  return nextSettings.notifications;
}

function readSeenEvents() {
  try {
    const parsed = JSON.parse(window.localStorage.getItem(SEEN_EVENT_STORAGE_KEY) || "{}");
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch (_) {
    return {};
  }
}

function markEventSeen(key) {
  const next = readSeenEvents();
  next[key] = Date.now();
  const entries = Object.entries(next)
    .sort((left, right) => Number(right[1] || 0) - Number(left[1] || 0))
    .slice(0, 120);
  window.localStorage.setItem(SEEN_EVENT_STORAGE_KEY, JSON.stringify(Object.fromEntries(entries)));
}

function hasSeenEvent(key) {
  return Boolean(readSeenEvents()[key]);
}

function statusLabel(status) {
  const normalized = String(status || "").toUpperCase();
  if (normalized === "DONE") return "Cotacao concluida";
  if (normalized === "ERROR") return "Erro na cotacao";
  if (normalized === "AWAITING_APPROVAL") return "Aguardando aprovacao";
  return normalized || "Atualizacao";
}

function notificationCopyForStatus(status, payload = {}) {
  const requestCode = payload.requestCode || "Pedido";
  const customerName = payload.customerName ? ` de ${payload.customerName}` : "";
  const normalized = String(status || "").toUpperCase();

  if (normalized === "DONE") {
    return {
      tone: "success",
      icon: "bx-check-circle",
      title: `${requestCode} pronto`,
      message: `A cotacao${customerName} foi concluida e ja pode ser revisada no comparador.`,
    };
  }

  if (normalized === "AWAITING_APPROVAL") {
    return {
      tone: "warning",
      icon: "bx-time-five",
      title: `${requestCode} aguardando aprovacao`,
      message: `A Cota finalizou a etapa tecnica${customerName} e o pedido precisa de liberacao.`,
    };
  }

  if (normalized === "ERROR") {
    return {
      tone: "danger",
      icon: "bx-error-circle",
      title: `${requestCode} com erro`,
      message: payload.errorMessage || `A cotacao${customerName} encontrou um erro e precisa de revisao.`,
    };
  }

  return {
    tone: "info",
    icon: "bx-bell",
    title: `${requestCode} atualizado`,
    message: statusLabel(status),
  };
}

function ensureManifestLink() {
  if (document.getElementById(MANIFEST_ID)) return;
  const link = document.createElement("link");
  link.id = MANIFEST_ID;
  link.rel = "manifest";
  link.href = "/manifest.webmanifest";
  document.head.appendChild(link);
}

export async function registerNotificationServiceWorker() {
  ensureManifestLink();
  if (!("serviceWorker" in navigator)) return null;
  try {
    return await navigator.serviceWorker.register("/sw.js");
  } catch (_) {
    return null;
  }
}

export async function requestSystemNotificationPermission() {
  if (!("Notification" in window)) return "unsupported";
  if (Notification.permission === "granted") {
    await registerNotificationServiceWorker();
    return "granted";
  }
  const permission = await Notification.requestPermission();
  if (permission === "granted") {
    await registerNotificationServiceWorker();
  }
  return permission;
}

async function showSystemNotification({ title, message, tag, url }) {
  if (!("Notification" in window) || Notification.permission !== "granted") return false;
  const registration = await registerNotificationServiceWorker();
  const payload = {
    body: message,
    icon: "/assets/favicon.svg",
    badge: "/assets/favicon.svg",
    tag,
    data: { url: url || "/requests.html" },
  };

  if (registration?.showNotification) {
    await registration.showNotification(title, payload);
    return true;
  }

  const notification = new Notification(title, payload);
  notification.onclick = () => {
    window.focus();
    window.location.href = url || "requests.html";
  };
  return true;
}

function maybePromptForPermission() {
  if (promptShown || !isMobileViewport() || !areNotificationsEnabled()) return;
  if (!("Notification" in window) || Notification.permission !== "default") return;
  if (window.localStorage.getItem(PROMPT_STORAGE_KEY) === "1") return;

  promptShown = true;
  showAppToast({
    tone: "info",
    icon: "bx-bell",
    title: "Ative as notificacoes",
    message: "Receba avisos no celular quando a Cota concluir uma cotacao ou quando um pedido precisar de aprovacao.",
    actionLabel: "Ativar",
    duration: 7000,
    onAction: async () => {
      const permission = await requestSystemNotificationPermission();
      if (permission !== "granted") {
        window.localStorage.setItem(PROMPT_STORAGE_KEY, "1");
      }
    },
  });
}

export async function announceRequestStatusNotification(status, payload = {}) {
  const normalized = String(status || "").toUpperCase();
  if (!INTERESTING_STATUSES.has(normalized) || !areNotificationsEnabled()) return;

  const requestCode = payload.requestCode || "Pedido";
  const dedupeKey = `${requestCode}:${normalized}:${payload.updatedAt || payload.requestId || ""}`;
  if (hasSeenEvent(dedupeKey)) return;
  markEventSeen(dedupeKey);

  const copy = notificationCopyForStatus(normalized, payload);
  showAppToast({
    tone: copy.tone,
    icon: copy.icon,
    title: copy.title,
    message: copy.message,
    actionLabel: "Abrir",
    onAction: () => {
      window.location.href = payload.url || `requests.html?requestId=${encodeURIComponent(payload.requestId || "")}`;
    },
  });

  await showSystemNotification({
    title: copy.title,
    message: copy.message,
    tag: `cotai-${requestCode}-${normalized}`,
    url: payload.url || `requests.html?requestId=${encodeURIComponent(payload.requestId || "")}`,
  });
}

async function fetchKnownStatuses(companyId) {
  if (!supabase || !companyId) return;
  const { data } = await supabase
    .from("requests")
    .select("id, request_code, status, updated_at")
    .eq("company_id", companyId)
    .order("updated_at", { ascending: false })
    .limit(120);

  knownStatusMap = new Map(
    (Array.isArray(data) ? data : []).map((row) => [String(row.id), { status: String(row.status || "").toUpperCase(), updatedAt: row.updated_at || "" }])
  );
}

function bindRealtimeChannel(companyId) {
  if (!supabase || !companyId) return;
  if (channel && channelCompanyId === companyId) return;

  if (channel) {
    supabase.removeChannel(channel);
    channel = null;
  }

  channelCompanyId = companyId;
  channel = supabase
    .channel(CHANNEL_STORAGE_KEY)
    .on(
      "postgres_changes",
      {
        event: "UPDATE",
        schema: "public",
        table: "requests",
        filter: `company_id=eq.${companyId}`,
      },
      async (event) => {
        const next = event.new || {};
        const requestId = String(next.id || "");
        if (!requestId) return;

        const previous = knownStatusMap.get(requestId) || null;
        const nextStatus = String(next.status || "").toUpperCase();
        const nextUpdatedAt = String(next.updated_at || "");
        knownStatusMap.set(requestId, { status: nextStatus, updatedAt: nextUpdatedAt });

        if (previous && previous.status === nextStatus && previous.updatedAt === nextUpdatedAt) return;
        await announceRequestStatusNotification(nextStatus, {
          requestId,
          requestCode: next.request_code || requestId,
          customerName: next.customer_name || "",
          updatedAt: nextUpdatedAt,
          errorMessage: next.last_error || "",
        });
      }
    )
    .subscribe();
}

export async function bootstrapMobileNotifications(userId) {
  if (!userId || !isMobileViewport()) return null;

  ensureManifestLink();
  maybePromptForPermission();

  if (!supabase || !areNotificationsEnabled()) return null;

  const profile = await getProfile(userId);
  const companyId = String(profile?.company_id || "").trim();
  if (!companyId) return null;

  await fetchKnownStatuses(companyId);
  bindRealtimeChannel(companyId);
  return { companyId };
}
