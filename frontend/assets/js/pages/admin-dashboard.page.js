import { fetchAdminOverview } from "../adminStats.js";
import { bootAdminPage } from "../adminPage.js";
import { formatCurrencyBRL } from "../adminCommon.js";
import { formatDateTime, setHTML, setText, showFeedback } from "../ui.js";

function renderNoticeList(notices) {
  if (!notices.length) return "";
  return notices.map((notice) => `<li>${notice}</li>`).join("");
}

function metricValue(value, suffix = "") {
  if (value === null || value === undefined || value === "") return "TODO";
  if (typeof value === "number") {
    return `${Math.round(value * 10) / 10}${suffix}`;
  }
  return `${value}${suffix}`;
}

function renderRecentRequests(rows) {
  if (!rows.length) {
    return '<tr><td colspan="5" class="app-empty">Nenhum pedido recente encontrado.</td></tr>';
  }

  return rows
    .map(
      (row) => `
        <tr>
          <td>${row.request_code || row.id}</td>
          <td>${row.customer_name || "-"}</td>
          <td>${row.status || "-"}</td>
          <td>${row.company_id || "-"}</td>
          <td>${formatDateTime(row.created_at)}</td>
        </tr>
      `
    )
    .join("");
}

function renderRecentErrors(rows) {
  if (!rows.length) {
    return '<tr><td colspan="4" class="app-empty">Nenhum erro recente do worker.</td></tr>';
  }

  return rows
    .map(
      (row) => `
        <tr>
          <td>${row.request_id || "-"}</td>
          <td>${row.status}</td>
          <td>${row.error_message || "Erro sem detalhes"}</td>
          <td>${formatDateTime(row.updated_at || row.created_at)}</td>
        </tr>
      `
    )
    .join("");
}

function renderStatus(items) {
  return items
    .map(
      (item) => `
        <article class="admin-status-row">
          <div>
            <p>${item.label}</p>
            <strong>${item.value}</strong>
          </div>
          <span class="app-badge ${item.tone === "success" ? "is-success" : item.tone === "warning" ? "is-warning" : "is-muted"}">${item.tone === "success" ? "OK" : item.tone === "warning" ? "ATENCAO" : "INFO"}</span>
        </article>
      `
    )
    .join("");
}

async function init() {
  const auth = await bootAdminPage();
  if (!auth) return;

  try {
    const overview = await fetchAdminOverview();
    setText("#metricCompanies", String(overview.metrics.activeCompanies));
    setText("#metricUsers", String(overview.metrics.totalUsers));
    setText("#metricRequestsToday", String(overview.metrics.requestsToday));
    setText("#metricRequestsMonth", String(overview.metrics.requestsMonth));
    setText("#metricQuotesDone", String(overview.metrics.quotesDone));
    setText("#metricQuotesError", String(overview.metrics.quotesError));
    setText("#metricWorkerStatus", overview.metrics.workerStatus);
    setText("#metricResponseTime", metricValue(overview.metrics.averageResponseMinutes, " min"));
    setText("#metricRevenue", formatCurrencyBRL(overview.metrics.estimatedRevenue));
    setText("#metricPlanSilver", String(overview.metrics.planCounts.prata));
    setText("#metricPlanGold", String(overview.metrics.planCounts.ouro));
    setText("#metricPlanDiamond", String(overview.metrics.planCounts.diamante));

    setHTML("#adminOverviewRecentRequests", renderRecentRequests(overview.recentRequests));
    setHTML("#adminOverviewErrors", renderRecentErrors(overview.recentErrors));
    setHTML("#adminSystemStatus", renderStatus(overview.systemStatus));
    setHTML("#adminOverviewNotices", renderNoticeList(overview.notices));

    if (!overview.notices.length) {
      document.querySelector("#adminOverviewNoticeCard")?.classList.add("hidden");
    }
  } catch (error) {
    showFeedback("#adminDashboardFeedback", error.message || "Nao foi possivel carregar o overview admin.");
  }
}

init().catch((error) => {
  showFeedback("#adminDashboardFeedback", error.message || "Erro ao iniciar o painel admin.");
});
