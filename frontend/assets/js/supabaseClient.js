import { SUPABASE_ANON_KEY, SUPABASE_URL } from "./config.js";

const isConfigured =
  SUPABASE_URL &&
  SUPABASE_ANON_KEY &&
  !SUPABASE_URL.includes("YOUR_PROJECT") &&
  !SUPABASE_ANON_KEY.includes("YOUR_SUPABASE");

if (!window.supabase?.createClient) {
  throw new Error("Supabase CDN nao foi carregado.");
}

export const supabase = isConfigured
  ? window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY)
  : null;

export function assertSupabaseConfigured() {
  if (supabase) return;

  throw new Error(
    "Configure SUPABASE_URL e SUPABASE_ANON_KEY em frontend/assets/js/config.js antes de usar o app."
  );
}
