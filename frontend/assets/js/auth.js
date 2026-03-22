import { DASHBOARD_PATH } from "./config.js";
import { assertSupabaseConfigured, supabase } from "./supabaseClient.js";

const ADMIN_ROLES = new Set(["admin", "owner"]);
export const AUTH_ERROR_CODES = {
  sessionExpired: "session_expired",
  unauthenticated: "unauthenticated"
};

function buildAuthError(message, code) {
  const error = new Error(message);
  error.code = code;
  return error;
}

export async function signIn(email, password) {
  assertSupabaseConfigured();

  const { data, error } = await supabase.auth.signInWithPassword({
    email,
    password
  });

  if (error) throw error;
  return data;
}

export async function signUp({ email, password, companyName }) {
  assertSupabaseConfigured();

  const { data, error } = await supabase.auth.signUp({
    email,
    password,
    options: {
      data: {
        company_name: companyName
      }
    }
  });

  if (error) throw error;
  return data;
}

export async function signOut() {
  assertSupabaseConfigured();
  const { error } = await supabase.auth.signOut();
  if (error) throw error;
}

export async function getSession() {
  assertSupabaseConfigured();
  const { data, error } = await supabase.auth.getSession();
  if (error) throw error;
  return data.session;
}

export async function clearSession() {
  if (!supabase) return;
  try {
    await supabase.auth.signOut({ scope: "local" });
  } catch (_) {
    // Best effort cleanup for expired sessions.
  }
}

export async function requireAuth(loginPath = "/login.html") {
  const session = await getSession();

  if (!session) {
    window.location.replace(loginPath);
    return null;
  }

  return session;
}

export async function redirectIfAuthenticated(path = DASHBOARD_PATH) {
  const session = await getSession();

  if (session) {
    window.location.replace(path);
  }

  return session;
}

export function isAdminRole(role) {
  return ADMIN_ROLES.has(String(role || "").toLowerCase());
}

export function isSessionExpiredError(error) {
  return error?.code === AUTH_ERROR_CODES.sessionExpired || error?.code === AUTH_ERROR_CODES.unauthenticated;
}

export async function handleSessionExpired(loginPath = "/login.html") {
  await clearSession();
  if (globalThis?.sessionStorage) {
    sessionStorage.clear();
  }
  window.location.replace(loginPath);
}

export function createUnauthenticatedError(message = "Sessao invalida. Faca login novamente.") {
  return buildAuthError(message, AUTH_ERROR_CODES.unauthenticated);
}

export async function getProfile(userId) {
  assertSupabaseConfigured();

  const { data, error } = await supabase.from("profiles").select("*").eq("id", userId).maybeSingle();
  if (error) throw error;
  return data;
}

export async function getAdminProfile(userId) {
  const profile = await getProfile(userId);
  if (!profile || !isAdminRole(profile.role)) {
    return null;
  }

  return profile;
}

export async function requireAdmin(loginPath = "/login.html", fallbackPath = DASHBOARD_PATH) {
  const session = await requireAuth(loginPath);
  if (!session) return null;

  const profile = await getAdminProfile(session.user.id);
  if (!profile) {
    window.location.replace(fallbackPath);
    return null;
  }

  return { session, profile };
}

export async function redirectIfNotAdmin(loginPath = "/login.html", fallbackPath = DASHBOARD_PATH) {
  const session = await getSession();
  if (!session) {
    window.location.replace(loginPath);
    return null;
  }

  const profile = await getAdminProfile(session.user.id);
  if (!profile) {
    window.location.replace(fallbackPath);
    return null;
  }

  return { session, profile };
}

export function getCompanyDisplayName(user, fallback = "Minha empresa") {
  return (
    user?.user_metadata?.company_name ||
    user?.user_metadata?.company ||
    user?.user_metadata?.full_name ||
    user?.email ||
    fallback
  );
}
