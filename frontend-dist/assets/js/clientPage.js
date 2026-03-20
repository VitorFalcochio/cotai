import { LOGIN_PATH } from "./config.js";
import { getAdminProfile, getCompanyDisplayName, requireAuth, signOut } from "./auth.js";
import { showAdminShortcut } from "./adminPage.js";
import { initSidebar, qs, setText } from "./ui.js";

function getInitials(value, fallback = "CO") {
  const parts = String(value || "")
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2);
  if (!parts.length) return fallback;
  return parts.map((part) => part[0]?.toUpperCase() || "").join("");
}

export async function bootClientWorkspace() {
  const session = await requireAuth(LOGIN_PATH);
  if (!session) return null;

  initSidebar();

  const companyLabel = getCompanyDisplayName(session.user);
  const initials = getInitials(companyLabel);
  setText("#companyNameSide", companyLabel);
  setText("#dashboardAvatar", initials);
  setText("#dashboardRoleLabel", "Equipe de compras");

  qs("#logoutButton")?.addEventListener("click", async () => {
    await signOut();
    window.location.replace(LOGIN_PATH);
  });

  try {
    const adminProfile = await getAdminProfile(session.user.id);
    showAdminShortcut(adminProfile);
  } catch (_) {
    showAdminShortcut(null);
  }

  return { session, companyLabel, initials };
}
