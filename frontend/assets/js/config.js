export const SUPABASE_URL = "https://hppeuzpgmywjniidqatw.supabase.co";
export const SUPABASE_ANON_KEY = "sb_publishable_0pD6K1pQGrJxxaG5NuNuMw_brF6wEn7";
const browserHost = globalThis?.location?.hostname || "127.0.0.1";
const apiHost = browserHost === "localhost" || browserHost === "127.0.0.1" ? browserHost : "127.0.0.1";
export const API_BASE_URL = `http://${apiHost}:8000`;
export const WHATSAPP_NUMBER = "5517996657737";
export const LOGIN_PATH = "login.html";
export const DASHBOARD_PATH = "dashboard.html";
