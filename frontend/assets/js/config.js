import { RUNTIME_CONFIG } from "./runtime-config.js";

const DEFAULT_SUPABASE_URL = "https://hppeuzpgmywjniidqatw.supabase.co";
const DEFAULT_SUPABASE_ANON_KEY = "sb_publishable_0pD6K1pQGrJxxaG5NuNuMw_brF6wEn7";
const DEFAULT_WHATSAPP_NUMBER = "5517996657737";

function resolveApiBaseUrl() {
  const explicit = String(RUNTIME_CONFIG.API_BASE_URL || "").trim();
  if (explicit) {
    return explicit.replace(/\/+$/, "");
  }

  const browserHost = globalThis?.location?.hostname || "127.0.0.1";
  const isLocalhost = browserHost === "localhost" || browserHost === "127.0.0.1";
  return isLocalhost ? `http://${browserHost}:8000` : "http://127.0.0.1:8000";
}

export const SUPABASE_URL = String(RUNTIME_CONFIG.SUPABASE_URL || DEFAULT_SUPABASE_URL).trim();
export const SUPABASE_ANON_KEY = String(RUNTIME_CONFIG.SUPABASE_ANON_KEY || DEFAULT_SUPABASE_ANON_KEY).trim();
export const API_BASE_URL = resolveApiBaseUrl();
export const WHATSAPP_NUMBER = String(RUNTIME_CONFIG.WHATSAPP_NUMBER || DEFAULT_WHATSAPP_NUMBER).trim();
export const BILLING_ENABLED = Boolean(RUNTIME_CONFIG.BILLING_ENABLED);
export const PLAN_SELECTION_ENABLED = Boolean(RUNTIME_CONFIG.PLAN_SELECTION_ENABLED);
export const CLIENT_DISABLED_PAGES = Array.isArray(RUNTIME_CONFIG.CLIENT_DISABLED_PAGES)
  ? RUNTIME_CONFIG.CLIENT_DISABLED_PAGES.map((item) => String(item || "").trim()).filter(Boolean)
  : [];
export const LOGIN_PATH = "login.html";
export const DASHBOARD_PATH = "dashboard.html";
