import { DASHBOARD_PATH, LOGIN_PATH } from "./config.js";
import { getCompanyDisplayName, isAdminRole, requireAdmin, signOut } from "./auth.js";
import { initSidebar, qs, setText } from "./ui.js";

function getAdminLabel(profile, user) {
  return (
    profile?.full_name ||
    profile?.name ||
    user?.user_metadata?.full_name ||
    getCompanyDisplayName(user, "Admin Cotai")
  );
}

export async function bootAdminPage() {
  const auth = await requireAdmin(LOGIN_PATH, DASHBOARD_PATH);
  if (!auth) return null;

  initSidebar();

  const { session, profile } = auth;
  setText("#adminIdentity", getAdminLabel(profile, session.user));
  setText("#adminRole", String(profile?.role || "admin").toUpperCase());

  qs("#logoutButton")?.addEventListener("click", async () => {
    await signOut();
    window.location.replace(LOGIN_PATH);
  });

  qs("#backToClientButton")?.addEventListener("click", () => {
    window.location.href = DASHBOARD_PATH;
  });

  return auth;
}

export function showAdminShortcut(profile) {
  const shortcut = qs("#adminShortcut");
  if (!shortcut) return;

  if (isAdminRole(profile?.role)) {
    shortcut.classList.remove("hidden");
  } else {
    shortcut.classList.add("hidden");
  }
}
