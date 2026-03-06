import { LOGIN_PATH } from "../config.js";
import { getAdminProfile, getCompanyDisplayName, requireAuth, signOut } from "../auth.js";
import { countRequests, listRecentRequests } from "../requests.js";
import { formatDateTime, initSidebar, qs, setHTML, setText, showFeedback } from "../ui.js";
import { showAdminShortcut } from "../adminPage.js";

function renderRows(rows) {
  if (!rows.length) {
    return '<tr><td colspan="4" class="app-empty">Nenhum pedido ainda.</td></tr>';
  }

  return rows
    .map(
      (row) => `
        <tr>
          <td>${row.requestCode}</td>
          <td>${row.customerName}</td>
          <td>${row.deliveryMode}</td>
          <td>${formatDateTime(row.createdAt)}</td>
        </tr>
      `
    )
    .join("");
}

async function init() {
  const session = await requireAuth(LOGIN_PATH);
  if (!session) return;

  initSidebar();
  setText("#companyName", getCompanyDisplayName(session.user));

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

  try {
    const [requests, total] = await Promise.all([listRecentRequests(5), countRequests()]);
    setText("#metricRequests", String(total));
    setText("#metricLastRequest", requests[0]?.requestCode || "-");
    setHTML("#dashboardRecentBody", renderRows(requests));
  } catch (error) {
    showFeedback("#dashboardFeedback", error.message || "Nao foi possivel carregar o dashboard.");
    setHTML("#dashboardRecentBody", '<tr><td colspan="4" class="app-empty">Erro ao carregar pedidos.</td></tr>');
  }
}

init().catch((error) => {
  showFeedback("#dashboardFeedback", error.message || "Erro ao iniciar o dashboard.");
});
