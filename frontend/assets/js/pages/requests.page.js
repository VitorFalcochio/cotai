import { LOGIN_PATH } from "../config.js";
import { requireAuth, signOut } from "../auth.js";
import { fetchProcurementOverview } from "../procurementData.js";
import { exportQuoteCsv, printQuoteReport } from "../quoteExport.js";
import { formatCurrencyBRL } from "../adminCommon.js";
import { formatDateTime, initSidebar, qs, runPageBoot, setHTML, setTableSkeleton, setText, showFeedback } from "../ui.js";

let overview = null;
let filteredRequests = [];
let selectedRequest = null;
const DUPLICATE_REQUEST_STORAGE_KEY = "cotai_request_prefill";

const STATUS_LABELS = {
  DONE: "Concluido",
  ERROR: "Erro",
  PROCESSING: "Em andamento",
  PENDING_QUOTE: "Pendente",
  AWAITING_CONFIRMATION: "Aguardando confirmacao",
  AWAITING_APPROVAL: "Aguardando aprovacao",
  DRAFT: "Rascunho"
};

function badgeClass(status) {
  const value = String(status || "").toUpperCase();
  if (value === "DONE") return "is-success";
  if (value === "ERROR") return "is-danger";
  if (["PROCESSING", "PENDING_QUOTE", "AWAITING_CONFIRMATION", "AWAITING_APPROVAL"].includes(value)) return "is-warning";
  return "is-muted";
}

function formatStatus(status) {
  const key = String(status || "").toUpperCase();
  return STATUS_LABELS[key] || status || "-";
}

function normalize(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

function renderInsightList(items, formatter) {
  if (!items?.length) {
    return '<article class="entity-list-item"><div class="entity-list-copy"><p>Sem dados</p><strong>Os dados aparecem conforme o uso da plataforma.</strong></div><span class="app-badge is-muted">INFO</span></article>';
  }
  return items.map(formatter).join("");
}

function renderRows(rows) {
  if (!rows.length) {
    return '<tr><td colspan="6" class="app-empty">Nenhum pedido encontrado com os filtros atuais.</td></tr>';
  }

  return rows
    .map(
      (row) => `
        <tr>
          <td><div class="table-entity"><strong>${row.request_code || row.requestCode || row.id}</strong><small>${row.customer_name || row.customerName || "-"}${row.previous_request_code ? ` • parecido com ${row.previous_request_code}` : ""}</small></div></td>
          <td><div class="table-entity"><span class="app-badge ${badgeClass(row.status)}">${formatStatus(row.status)}</span><small>${row.priority || "MEDIUM"}</small></div></td>
          <td><div class="table-entity"><strong>${row.best_supplier_name || "-"}</strong><small>Economia ${formatCurrencyBRL(row.potential_savings || 0)}</small></div></td>
          <td><div class="table-entity"><strong>${row.delivery_location || "-"}</strong><small>${row.approval_status || "NOT_REQUIRED"}</small></div></td>
          <td>${formatDateTime(row.created_at || row.createdAt)}</td>
          <td class="app-actions">
            <button class="btn btn-ghost" data-action="details" data-id="${row.id}">Detalhes</button>
            <button class="btn btn-ghost" data-action="duplicate" data-id="${row.id}">Duplicar</button>
            <button class="btn btn-ghost" data-action="pdf" data-id="${row.id}">PDF</button>
            <button class="btn btn-ghost" data-action="csv" data-id="${row.id}">CSV</button>
          </td>
        </tr>
      `
    )
    .join("");
}

function renderComparison(request) {
  if (!request?.comparison?.ranked?.length) {
    return '<article class="entity-list-item"><div class="entity-list-copy"><p>Comparador</p><strong>Selecione um pedido com resultados consolidados.</strong></div><span class="app-badge is-muted">INFO</span></article>';
  }

  return request.comparison.ranked
    .map(
      (supplier) => `
        <article class="entity-list-item">
          <div class="entity-list-copy">
            <p>${supplier.supplier}</p>
            <strong>${formatCurrencyBRL(supplier.totalPrice)}</strong>
          </div>
          <span class="app-badge ${supplier.supplier === request.best_supplier_name ? "is-success" : "is-muted"}">
            ${supplier.averageDeliveryDays ? `${Math.round(supplier.averageDeliveryDays)}d` : "Prazo -"}
          </span>
        </article>
      `
    )
    .join("");
}

function selectRequest(requestId) {
  selectedRequest = overview.requests.find((request) => request.id === requestId) || null;
  setText("#requestDetailTitle", selectedRequest?.request_code || selectedRequest?.requestCode || "Selecione um pedido");
  setHTML("#requestComparisonPanel", renderComparison(selectedRequest));
}

function buildDuplicatePayload(request) {
  const items = overview.requestItems
    .filter((item) => item.request_id === request.id)
    .map((item) => ({
      name: item.item_name || item.description || "Material",
      normalized_name: item.item_name || item.description || "Material",
      quantity: Number(item.quantity || item.estimated_qty || 0) || null,
      unit: item.unit || "un",
      raw: item.raw || item.item_name || item.description || "Material"
    }));

  return {
    source_request_id: request.id,
    request_code: request.request_code || request.requestCode || request.id,
    title: request.customer_name || request.request_code || "Nova cotacao",
    deliveryLocation: request.delivery_location || "",
    deliveryMode: request.delivery_mode || "",
    notes: request.notes || "",
    priority: request.priority || "MEDIUM",
    items,
    created_at: new Date().toISOString()
  };
}

function duplicateRequest(request) {
  sessionStorage.setItem(DUPLICATE_REQUEST_STORAGE_KEY, JSON.stringify(buildDuplicatePayload(request)));
  window.location.href = "new-request.html";
}

function exportCurrentRows() {
  const header = ["request_code", "status", "priority", "best_supplier", "potential_savings", "delivery_location"];
  const csv = [header]
    .concat(
      filteredRequests.map((request) => [
        request.request_code || request.requestCode || request.id,
        request.status,
        request.priority || "MEDIUM",
        request.best_supplier_name || "",
        request.potential_savings || 0,
        request.delivery_location || ""
      ])
    )
    .map((line) => line.map((cell) => `"${String(cell ?? "").replaceAll('"', '""')}"`).join(","))
    .join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "cotai-historico-pedidos.csv";
  link.click();
  URL.revokeObjectURL(url);
}

function applyFilters() {
  const searchValue = normalize(qs("#requestsSearch")?.value);
  const statusValue = String(qs("#requestsStatusFilter")?.value || "").toUpperCase();
  const priorityValue = String(qs("#requestsPriorityFilter")?.value || "").toUpperCase();
  const sortValue = String(qs("#requestsSort")?.value || "recent");

  filteredRequests = overview.requests.filter((row) => {
    const matchesSearch =
      !searchValue ||
      [row.request_code, row.customer_name, row.delivery_location, row.best_supplier_name]
        .some((value) => normalize(value).includes(searchValue));
    const matchesStatus = !statusValue || String(row.status || "").toUpperCase() === statusValue;
    const matchesPriority = !priorityValue || String(row.priority || "").toUpperCase() === priorityValue;
    return matchesSearch && matchesStatus && matchesPriority;
  });

  if (sortValue === "savings") {
    filteredRequests.sort((a, b) => (b.potential_savings || 0) - (a.potential_savings || 0));
  } else if (sortValue === "supplier") {
    filteredRequests.sort((a, b) => String(a.best_supplier_name || "").localeCompare(String(b.best_supplier_name || ""), "pt-BR"));
  } else {
    filteredRequests.sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0));
  }

  setText("#requestsCount", `${filteredRequests.length} pedidos`);
  setHTML("#requestsTableBody", renderRows(filteredRequests));
  if ((!selectedRequest || !filteredRequests.some((item) => item.id === selectedRequest.id)) && filteredRequests.length) {
    selectRequest(filteredRequests[0].id);
  }
}

async function init() {
  const session = await requireAuth(LOGIN_PATH);
  if (!session) return;

  initSidebar();
  setTableSkeleton("#requestsTableBody", 6, 5);

  qs("#logoutButton")?.addEventListener("click", async () => {
    await signOut();
    window.location.replace(LOGIN_PATH);
  });

  try {
    overview = await fetchProcurementOverview();
    setText("#requestsMetricTotal", String(overview.metrics.totalRequests));
    setText("#requestsMetricTopMaterial", overview.topMaterials[0]?.name || "-");
    setText("#requestsMetricTopSupplier", overview.metrics.bestRecurringSupplier || "-");
    setText("#requestsMetricSavings", formatCurrencyBRL(overview.metrics.estimatedSavings));
    setHTML(
      "#requestsTopMaterials",
      renderInsightList(overview.topMaterials, (item) => `
        <article class="entity-list-item">
          <div class="entity-list-copy"><p>${item.name}</p><strong>${item.count} cotacoes</strong></div>
          <span class="app-badge is-muted">MATERIAL</span>
        </article>
      `)
    );
    setHTML(
      "#requestsPriceTrend",
      renderInsightList(overview.priceTrendByItem, (item) => `
        <article class="entity-list-item">
          <div class="entity-list-copy"><p>${item.item_name}</p><strong>${item.delta === null ? "Sem delta" : `${item.delta > 0 ? "+" : ""}${item.delta.toFixed(2)}`}</strong></div>
          <span class="app-badge ${item.delta !== null && item.delta <= 0 ? "is-success" : "is-muted"}">${item.last === null ? "-" : item.last.toFixed(2)}</span>
        </article>
      `)
    );
    if (overview.notices.length) {
      showFeedback("#requestsFeedback", overview.notices.join(" "));
    }
    applyFilters();
  } catch (error) {
    showFeedback("#requestsFeedback", error.message || "Nao foi possivel carregar os pedidos.");
    setHTML("#requestsTableBody", '<tr><td colspan="6" class="app-empty">Erro ao carregar pedidos.</td></tr>');
    return;
  }

  ["#requestsSearch", "#requestsStatusFilter", "#requestsPriorityFilter", "#requestsSort"].forEach((selector) => {
    qs(selector)?.addEventListener("input", applyFilters);
    qs(selector)?.addEventListener("change", applyFilters);
  });

  qs("#requestsClearFilters")?.addEventListener("click", () => {
    ["#requestsSearch", "#requestsStatusFilter", "#requestsPriorityFilter"].forEach((selector) => {
      const element = qs(selector);
      if (element) element.value = "";
    });
    const sort = qs("#requestsSort");
    if (sort) sort.value = "recent";
    applyFilters();
  });

  qs("#requestsExportCsv")?.addEventListener("click", exportCurrentRows);

  qs("#requestsTableBody")?.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-action]");
    if (!button) return;
    const request = overview.requests.find((item) => item.id === button.dataset.id);
    if (!request) return;
    if (button.dataset.action === "details") return selectRequest(request.id);
    if (button.dataset.action === "duplicate") return duplicateRequest(request);
    if (button.dataset.action === "pdf") {
      return printQuoteReport({
        companyName: overview.companyName,
        request,
        comparison: request.comparison,
        results: overview.quoteResults.filter((row) => row.request_id === request.id)
      });
    }
    if (button.dataset.action === "csv") {
      return exportQuoteCsv({
        request,
        results: overview.quoteResults.filter((row) => row.request_id === request.id)
      });
    }
  });
}

runPageBoot(init, { loadingMessage: "Carregando historico de cotacoes." }).catch((error) => {
  showFeedback("#requestsFeedback", error.message || "Erro ao iniciar a tela de pedidos.");
});
