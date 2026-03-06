import { fetchAdminRequests, updateRequest } from "../adminRequests.js";
import { bootAdminPage } from "../adminPage.js";
import { copyText, formatDateTime, openWhatsApp, qs, setHTML, showFeedback } from "../ui.js";

function badgeClass(status) {
  const value = String(status || "").toLowerCase();
  if (value.includes("done")) return "is-success";
  if (value.includes("error")) return "is-warning";
  if (value.includes("quot")) return "is-warning";
  return "is-muted";
}

function renderRows(rows) {
  if (!rows.length) {
    return '<tr><td colspan="8" class="app-empty">Nenhum pedido encontrado.</td></tr>';
  }

  return rows
    .map(
      (row) => `
        <tr>
          <td>${row.requestCode}</td>
          <td>${row.company}</td>
          <td>${row.customerName}</td>
          <td><span class="app-badge ${badgeClass(row.status)}">${row.status}</span></td>
          <td>${row.itemCount}</td>
          <td>${formatDateTime(row.createdAt)}</td>
          <td>${formatDateTime(row.updatedAt)}</td>
          <td>
            <div class="admin-table-stack">
              <span>${row.execution}</span>
              <div class="app-actions">
                <button class="btn btn-ghost" data-action="details" data-id="${row.id}">Ver detalhes</button>
                <button class="btn btn-ghost" data-action="requote" data-id="${row.id}">Recotar</button>
                <button class="btn btn-ghost" data-action="resend" data-id="${row.id}">Reenviar resposta</button>
                <button class="btn btn-ghost" data-action="logs" data-id="${row.id}">Abrir logs</button>
              </div>
            </div>
          </td>
        </tr>
      `
    )
    .join("");
}

async function loadRequests() {
  const payload = await fetchAdminRequests();
  setHTML("#adminRequestsBody", renderRows(payload.rows));
  if (payload.notices.length) {
    showFeedback("#adminRequestsFeedback", payload.notices.join(" "));
  }
  return payload.rows;
}

async function init() {
  await bootAdminPage();
  const body = qs("#adminRequestsBody");
  if (!body) return;

  let rows = await loadRequests();

  body.addEventListener("click", async (event) => {
    const button = event.target.closest("button[data-action]");
    if (!button) return;

    const request = rows.find((item) => item.id === button.dataset.id);
    if (!request) return;

    try {
      if (button.dataset.action === "details") {
        window.alert(
          `Pedido: ${request.requestCode}\nEmpresa: ${request.company}\nCliente: ${request.customerName}\nStatus: ${request.status}\nItens: ${request.itemCount}\nExecucao: ${request.execution}`
        );
        return;
      }

      if (button.dataset.action === "requote") {
        await updateRequest(request.id, { status: "NEW" });
        rows = await loadRequests();
        showFeedback("#adminRequestsFeedback", "Pedido reenfileirado para nova cotacao.", false);
        return;
      }

      if (button.dataset.action === "resend") {
        if (!request.latestResponse) {
          showFeedback("#adminRequestsFeedback", "Este pedido ainda nao possui resposta consolidada.");
          return;
        }
        await copyText(request.latestResponse);
        openWhatsApp(request.latestResponse);
        showFeedback("#adminRequestsFeedback", "Resposta copiada e pronta para reenvio.", false);
        return;
      }

      if (button.dataset.action === "logs") {
        window.location.href = `admin-logs.html?request_id=${encodeURIComponent(request.id)}`;
      }
    } catch (error) {
      showFeedback("#adminRequestsFeedback", error.message || "Nao foi possivel executar a acao no pedido.");
    }
  });
}

init().catch((error) => {
  showFeedback("#adminRequestsFeedback", error.message || "Erro ao iniciar a central de pedidos.");
});
