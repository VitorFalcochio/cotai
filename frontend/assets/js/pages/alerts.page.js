import { bootClientWorkspace } from "../clientPage.js";
import { fetchProcurementOverview } from "../procurementData.js";
import { formatDateTime, runPageBoot, setHTML, setText, showFeedback } from "../ui.js";

function renderAlerts(items) {
  if (!items.length) {
    return '<article class="admin-status-row"><div><p>Sem alertas criticos</p><strong>A operacao esta saudavel neste momento.</strong></div><span class="app-badge is-success">OK</span></article>';
  }

  return items.map((item) => `
    <article class="admin-status-row">
      <div>
        <p>${item.label}</p>
        <strong>${item.title}</strong>
      </div>
      <span class="app-badge ${item.variant}">${item.meta}</span>
    </article>
  `).join("");
}

async function init() {
  const boot = await bootClientWorkspace();
  if (!boot) return;

  try {
    const overview = await fetchProcurementOverview();
    const approvalAlerts = overview.requests
      .filter((request) => ["AWAITING_APPROVAL", "AWAITING_CONFIRMATION"].includes(String(request.status || "").toUpperCase()))
      .slice(0, 6)
      .map((request) => ({
        label: "Aprovacao pendente",
        title: request.request_code || request.customer_name || "Pedido aguardando decisao",
        meta: formatDateTime(request.created_at),
        variant: "is-warning"
      }));

    const errorAlerts = overview.requests
      .filter((request) => String(request.status || "").toUpperCase() === "ERROR")
      .slice(0, 4)
      .map((request) => ({
        label: "Erro operacional",
        title: request.request_code || "Pedido com falha",
        meta: "Revisar",
        variant: "is-danger"
      }));

    const noticeAlerts = overview.notices.slice(0, 4).map((notice) => ({
      label: "Sistema",
      title: notice,
      meta: "Ambiente",
      variant: "is-info"
    }));

    const allAlerts = [...approvalAlerts, ...errorAlerts, ...noticeAlerts];
    setText("#alertsTitle", `Alertas de ${overview.companyName || boot.companyLabel}`);
    setText("#alertsCount", String(allAlerts.length));
    setText("#alertsApprovals", String(approvalAlerts.length));
    setText("#alertsErrors", String(errorAlerts.length));
    setHTML("#alertsList", renderAlerts(allAlerts));
  } catch (error) {
    showFeedback("#alertsFeedback", error.message || "Nao foi possivel carregar alertas.");
  }
}

runPageBoot(init, { loadingMessage: "Organizando alertas e sinais da operacao." });
