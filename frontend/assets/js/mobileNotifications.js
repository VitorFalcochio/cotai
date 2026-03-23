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

async function syncProfilePreference(profile) {
  if (!supabase || !profile?.id) return profile;
  const localEnabled = areNotificationsEnabled();
  const remoteEnabled = profile.mobile_notifications_enabled;
  if (typeof remoteEnabled === "boolean" && remoteEnabled === localEnabled) return profile;

  const { data } = await supabase
    .from("profiles")
    .update({ mobile_notifications_enabled: localEnabled })
    .eq("id", profile.id)
    .select("*")
    .maybeSingle();
  return data || { ...profile, mobile_notifications_enabled: localEnabled };
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

async function fetchKnownNotifications(companyId) {
  if (!supabase || !companyId) return;
  const { data } = await supabase
    .from("company_notifications")
    .select("id, request_id, request_code, event_type, title, message, tone, metadata, created_at")
    .eq("company_id", companyId)
    .order("created_at", { ascending: false })
    .limit(120);

  knownStatusMap = new Map(
    (Array.isArray(data) ? data : []).map((row) => [String(row.id), true])
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
        event: "INSERT",
        schema: "public",
        table: "company_notifications",
        filter: `company_id=eq.${companyId}`,
      },
      async (event) => {
        const next = event.new || {};
        const notificationId = String(next.id || "");
        if (!notificationId || knownStatusMap.get(notificationId)) return;
        knownStatusMap.set(notificationId, true);

        const metadata = next.metadata && typeof next.metadata === "object" ? next.metadata : {};
        const requestId = String(next.request_id || metadata.request_id || "");
        const requestCode = String(next.request_code || metadata.request_code || requestId || "Pedido");
        const status = String(metadata.status || next.event_type || "").toUpperCase();
        const dedupeKey = `${notificationId}:${requestCode}:${status}`;
        if (hasSeenEvent(dedupeKey)) return;
        markEventSeen(dedupeKey);

        const tone = String(next.tone || "info").toLowerCase();
        const icon =
          tone === "success"
            ? "bx-check-circle"
            : tone === "warning"
              ? "bx-time-five"
              : tone === "danger"
                ? "bx-error-circle"
                : "bx-bell";

        showAppToast({
          tone,
          icon,
          title: next.title || statusLabel(status),
          message: next.message || statusLabel(status),
          actionLabel: "Abrir",
          onAction: () => {
            window.location.href = `requests.html?requestId=${encodeURIComponent(requestId)}`;
          },
        });

        await showSystemNotification({
          title: next.title || statusLabel(status),
          message: next.message || statusLabel(status),
          tag: `cotai-notification-${notificationId}`,
          url: `requests.html?requestId=${encodeURIComponent(requestId)}`,
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

  const profile = await syncProfilePreference(await getProfile(userId));
  if (profile?.mobile_notifications_enabled === false) return null;
  const companyId = String(profile?.company_id || "").trim();
  if (!companyId) return null;

  await fetchKnownNotifications(companyId);
  bindRealtimeChannel(companyId);
  return { companyId };
}
