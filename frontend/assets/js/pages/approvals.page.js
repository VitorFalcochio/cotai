import { bootClientWorkspace } from "../clientPage.js";
import { fetchProcurementOverview } from "../procurementData.js";
import { formatCurrencyBRL } from "../adminCommon.js";
import { formatDateTime, runPageBoot, setHTML, setText, showFeedback } from "../ui.js";

function renderRows(rows) {
  if (!rows.length) {
    return '<tr><td colspan="5" class="app-empty">Nenhum pedido aguardando aprovacao.</td></tr>';
  }

  return rows.map((row) => `
    <tr>
      <td><strong>${row.request_code || "-"}</strong></td>
      <td>${row.customer_name || "-"}</td>
      <td>${formatCurrencyBRL(row.potential_savings || 0)}</td>
      <td>${formatDateTime(row.created_at)}</td>
      <td><a class="btn btn-ghost" href="requests.html">Abrir em Pedidos</a></td>
    </tr>
  `).join("");
}

async function init() {
  const boot = await bootClientWorkspace();
  if (!boot) return;

  try {
    const overview = await fetchProcurementOverview();
    const rows = overview.requests.filter((request) =>
      ["AWAITING_APPROVAL", "AWAITING_CONFIRMATION"].includes(String(request.status || "").toUpperCase())
    );

    setText("#approvalsTitle", `Aprovacoes de ${overview.companyName || boot.companyLabel}`);
    setText("#approvalsCount", String(rows.length));
    setText(
      "#approvalsSavings",
      formatCurrencyBRL(rows.reduce((sum, row) => sum + (Number(row.potential_savings) || 0), 0))
    );
    setHTML("#approvalsTableBody", renderRows(rows));
  } catch (error) {
    showFeedback("#approvalsFeedback", error.message || "Nao foi possivel carregar aprovacoes.");
  }
}

runPageBoot(init, { loadingMessage: "Separando pedidos que pedem aprovacao." });
