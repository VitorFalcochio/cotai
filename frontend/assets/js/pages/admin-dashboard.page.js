import { fetchAdminOverview } from "../adminStats.js";
import { bootAdminPage, runAdminPageBoot } from "../adminPage.js";
import { formatCurrencyBRL } from "../adminCommon.js";
import { formatDateTime, setHTML, setText, showFeedback } from "../ui.js";

function metricValue(value, suffix = "") {
  if (value === null || value === undefined || value === "") return "Nao integrado";
  if (typeof value === "number") return `${Math.round(value * 10) / 10}${suffix}`;
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
  if (!items?.length) {
    return '<article class="admin-status-row"><div><p>Sem sinais</p><strong>Nada relevante agora.</strong></div><span class="app-badge is-success">OK</span></article>';
  }

  return items
    .map(
      (item) => `
        <article class="admin-status-row">
          <div>
            <p>${item.label}</p>
            <strong>${item.value}</strong>
          </div>
          <span class="app-badge ${item.tone === "success" ? "is-success" : item.tone === "warning" ? "is-warning" : "is-muted"}">
            ${item.tone === "success" ? "OK" : item.tone === "warning" ? "ATENCAO" : "INFO"}
          </span>
        </article>
      `
    )
    .join("");
}

function renderAlerts(items) {
  if (!items?.length) {
    return '<article class="admin-status-row"><div><p>Sem alertas</p><strong>Fila operacional sob controle.</strong></div><span class="app-badge is-success">OK</span></article>';
  }

  return items
    .map(
      (item) => `
        <article class="admin-status-row">
          <div>
            <p>${item.title}</p>
            <strong>${item.message}</strong>
          </div>
          <span class="app-badge ${item.tone === "warning" ? "is-warning" : "is-muted"}">${item.tone === "warning" ? "ATENCAO" : "INFO"}</span>
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

    setText("#metricRequestsToday", String(overview.metrics.requestsToday));
    setText("#metricRequestsQueued", String(overview.metrics.pendingRequests));
    setText("#metricRequestsProcessing", String(overview.metrics.processingRequests));
    setText("#metricWorkerStatus", overview.metrics.workerStatus);
    setText("#metricQuotesError", String(overview.metrics.quotesError));
    setText("#metricSuccessRate", metricValue(overview.metrics.quoteSuccessRate, "%"));

    setText("#metricRequestsTodayMeta", `${overview.metrics.requestsMonth} no mes`);
    setText("#metricRequestsQueuedMeta", `${overview.metrics.approvalPending} aguardando aprovacao`);
    setText("#metricRequestsProcessingMeta", `${overview.metrics.overdueSla} SLA vencido(s)`);
    setText("#metricWorkerStatusMeta", overview.metrics.averageResponseMinutes ? `${metricValue(overview.metrics.averageResponseMinutes, " min")} medio` : "Sem media ainda");
    setText("#metricQuotesErrorMeta", `${overview.metrics.duplicatesFlagged} duplicidade(s)`);
    setText("#metricSuccessRateMeta", `${overview.metrics.quotesDone} concluidas`);

    setText("#metricCompanies", String(overview.metrics.activeCompanies));
    setText("#metricUsers", String(overview.metrics.totalUsers));
    setText("#metricApprovalPending", String(overview.metrics.approvalPending));
    setText("#metricOverdueSla", String(overview.metrics.overdueSla));
    setText("#metricRequestsMonth", String(overview.metrics.requestsMonth));
    setText("#metricQuotesDone", String(overview.metrics.quotesDone));
    setText("#metricRevenue", formatCurrencyBRL(overview.metrics.estimatedRevenue));
    setText("#metricSummaryNotice", overview.notices[0] || "Sem alertas extras");

    setHTML("#adminAlerts", renderAlerts(overview.alerts));
    setHTML("#adminSystemStatus", renderStatus(overview.systemStatus));
    setHTML("#adminOverviewRecentRequests", renderRecentRequests(overview.recentRequests));
    setHTML("#adminOverviewErrors", renderRecentErrors(overview.recentErrors));

    if (overview.notices.length) {
      showFeedback("#adminDashboardFeedback", overview.notices.join(" "));
    }
  } catch (error) {
    showFeedback("#adminDashboardFeedback", error.message || "Nao foi possivel carregar o painel administrativo.");
  }
}

runAdminPageBoot(init, "Carregando painel administrativo.").catch((error) => {
  showFeedback("#adminDashboardFeedback", error.message || "Erro ao iniciar o painel administrativo.");
});
