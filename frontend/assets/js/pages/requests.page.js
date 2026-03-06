import { LOGIN_PATH } from "../config.js";
import { requireAuth, signOut } from "../auth.js";
import { listAllRequests } from "../requests.js";
import { formatDateTime, initSidebar, qs, setHTML, setText, showFeedback } from "../ui.js";

function renderRows(rows) {
  if (!rows.length) {
    return '<tr><td colspan="5" class="app-empty">Nenhum pedido encontrado.</td></tr>';
  }

  return rows
    .map(
      (row) => `
        <tr>
          <td>${row.requestCode}</td>
          <td>${row.customerName}</td>
          <td>${row.deliveryMode}</td>
          <td>${row.deliveryLocation}</td>
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

  qs("#logoutButton")?.addEventListener("click", async () => {
    await signOut();
    window.location.replace(LOGIN_PATH);
  });

  try {
    const requests = await listAllRequests();
    setText("#requestsCount", `${requests.length} pedidos`);
    setHTML("#requestsTableBody", renderRows(requests));
  } catch (error) {
    showFeedback("#requestsFeedback", error.message || "Nao foi possivel carregar os pedidos.");
    setHTML("#requestsTableBody", '<tr><td colspan="5" class="app-empty">Erro ao carregar pedidos.</td></tr>');
  }
}

init().catch((error) => {
  showFeedback("#requestsFeedback", error.message || "Erro ao iniciar a tela de pedidos.");
});
