import { fetchAdminOverview } from "../adminStats.js";
import { bootAdminPage, runAdminPageBoot } from "../adminPage.js";
import { formatCurrencyBRL } from "../adminCommon.js";
import { formatDateTime, setHTML, setText, showFeedback } from "../ui.js";

function renderNoticeList(notices) {
  if (!notices.length) return "";
  return notices.map((notice) => `<li>${notice}</li>`).join("");
}

function metricValue(value, suffix = "") {
  if (value === null || value === undefined || value === "") return "Não integrado";
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

function renderSearchResults(items) {
  if (!items?.length) {
    return '<article class="admin-status-row"><div><p>Busca global</p><strong>Nenhum resultado.</strong></div><span class="app-badge is-muted">INFO</span></article>';
  }
  return items
    .map(
      (item) => `
        <article class="admin-status-row">
          <div>
            <p>${item.type}</p>
            <strong>${item.label}</strong>
          </div>
          <span class="app-badge is-muted">${item.subtitle}</span>
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
    setText("#metricRevenueMirror", formatCurrencyBRL(overview.metrics.estimatedRevenue));
    setText("#metricRequestsQueued", String(overview.metrics.pendingRequests));
    setText("#metricRequestsProcessing", String(overview.metrics.processingRequests));
    setText("#metricApprovalPending", String(overview.metrics.approvalPending));
    setText("#metricOverdueSla", String(overview.metrics.overdueSla));
    setText("#metricOverdueSlaMirror", String(overview.metrics.overdueSla));
    setText("#metricDuplicates", String(overview.metrics.duplicatesFlagged));
    setText("#metricSuccessRate", metricValue(overview.metrics.quoteSuccessRate, "%"));
    setText("#metricMappedSuppliers", String(overview.metrics.mappedSuppliers));
    setText("#metricTopCompanyVolume", overview.metrics.topCompanyVolume);
    setText("#metricTopSupplier", overview.metrics.topSupplier);
    setText("#metricQuotesDoneMirror", String(overview.metrics.quotesDone));
    setText("#metricPlanSilver", String(overview.metrics.planCounts.prata));
    setText("#metricPlanGold", String(overview.metrics.planCounts.ouro));
    setText("#metricPlanDiamond", String(overview.metrics.planCounts.diamante));

    setHTML("#adminOverviewRecentRequests", renderRecentRequests(overview.recentRequests));
    setHTML("#adminOverviewErrors", renderRecentErrors(overview.recentErrors));
    setHTML("#adminSystemStatus", renderStatus(overview.systemStatus));
    setHTML("#adminAlerts", renderAlerts(overview.alerts));
    setHTML("#adminOverviewNotices", renderNoticeList(overview.notices));

    const searchInput = document.querySelector("#adminGlobalSearch");
    const searchTarget = document.querySelector("#adminGlobalSearchResults");
    const searchPool = [
      ...(overview.searchIndex?.requests || []),
      ...(overview.searchIndex?.companies || []),
      ...(overview.searchIndex?.users || [])
    ];
    const runSearch = () => {
      const query = String(searchInput?.value || "").toLowerCase().trim();
      const results = !query
        ? searchPool.slice(0, 6)
        : searchPool.filter((item) => `${item.label} ${item.subtitle}`.toLowerCase().includes(query)).slice(0, 6);
      if (searchTarget) searchTarget.innerHTML = renderSearchResults(results);
    };
    searchInput?.addEventListener("input", runSearch);
    runSearch();

    if (!overview.notices.length) {
      document.querySelector("#adminOverviewNoticeCard")?.classList.add("hidden");
    }
  } catch (error) {
    showFeedback("#adminDashboardFeedback", error.message || "Não foi possível carregar o painel administrativo.");
  }
}

runAdminPageBoot(init, "Carregando painel administrativo.").catch((error) => {
  showFeedback("#adminDashboardFeedback", error.message || "Erro ao iniciar o painel administrativo.");
});
