import { LOGIN_PATH } from "../config.js";
import { requireAuth, signOut } from "../auth.js";
import { fetchProcurementOverview } from "../procurementData.js";
import { exportQuoteCsv, printQuoteReport } from "../quoteExport.js";
import { submitSupplierReview } from "../suppliers.js";
import { formatCurrencyBRL } from "../adminCommon.js";
import { formatDateTime, initSidebar, qs, runPageBoot, setHTML, setTableSkeleton, setText, showFeedback } from "../ui.js";

let overview = null;
let filteredRequests = [];
let selectedRequest = null;
const DUPLICATE_REQUEST_STORAGE_KEY = "cotai_request_prefill";

const STATUS_LABELS = {
  DONE: "Concluído",
  ERROR: "Erro",
  PROCESSING: "Em andamento",
  PENDING_QUOTE: "Pendente",
  AWAITING_CONFIRMATION: "Aguardando confirmação",
  AWAITING_APPROVAL: "Aguardando aprovação",
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
    return '<article class="admin-status-row"><div><p>Sem dados</p><strong>Os dados aparecerão conforme o uso da plataforma.</strong></div><span class="app-badge is-muted">INFO</span></article>';
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
          <td><strong>${row.request_code || row.requestCode || row.id}</strong><br /><small>${row.customer_name || row.customerName || "-"} ${row.previous_request_code ? `| parecido com ${row.previous_request_code}` : ""}</small></td>
          <td><span class="app-badge ${badgeClass(row.status)}">${formatStatus(row.status)}</span><br /><small>${row.priority || "MEDIUM"}</small></td>
          <td><strong>${row.best_supplier_name || "-"}</strong><br /><small>Economia: ${formatCurrencyBRL(row.potential_savings || 0)}</small></td>
          <td>${row.delivery_location || "-"}<br /><small>${row.approval_status || "NOT_REQUIRED"}</small></td>
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
    return '<article class="admin-status-row"><div><p>Comparador</p><strong>Selecione um pedido com resultados consolidados.</strong></div><span class="app-badge is-muted">INFO</span></article>';
  }

  return request.comparison.ranked
    .map(
      (supplier) => `
        <article class="admin-status-row">
          <div>
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

function updateReviewSuppliers(request) {
  const select = qs("#reviewSupplierSelect");
  if (!select) return;
  const suppliers = request?.comparison?.ranked || [];
  select.innerHTML = suppliers.length
    ? suppliers.map((supplier, index) => `<option value="${supplier.supplier_id || supplier.supplier || index}">${supplier.supplier}</option>`).join("")
    : '<option value="">Sem fornecedor</option>';
}

function selectRequest(requestId) {
  selectedRequest = overview.requests.find((request) => request.id === requestId) || null;
  setText("#requestDetailTitle", selectedRequest?.request_code || selectedRequest?.requestCode || "Selecione um pedido");
  setHTML("#requestComparisonPanel", renderComparison(selectedRequest));
  updateReviewSuppliers(selectedRequest);
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
    title: request.customer_name || request.request_code || "Nova cotação",
    deliveryLocation: request.delivery_location || "",
    deliveryMode: request.delivery_mode || "",
    notes: request.notes || "",
    priority: request.priority || "MEDIUM",
    items,
    created_at: new Date().toISOString()
  };
}

function duplicateRequest(request) {
  const payload = buildDuplicatePayload(request);
  sessionStorage.setItem(DUPLICATE_REQUEST_STORAGE_KEY, JSON.stringify(payload));
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
  if (!selectedRequest && filteredRequests.length) {
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
        <article class="admin-status-row">
          <div><p>${item.name}</p><strong>${item.count} cotações</strong></div>
          <span class="app-badge is-muted">MATERIAL</span>
        </article>
      `)
    );
    setHTML(
      "#requestsPriceTrend",
      renderInsightList(overview.priceTrendByItem, (item) => `
        <article class="admin-status-row">
          <div><p>${item.item_name}</p><strong>${item.delta === null ? "Sem delta" : `${item.delta > 0 ? "+" : ""}${item.delta.toFixed(2)}`}</strong></div>
          <span class="app-badge ${item.delta !== null && item.delta <= 0 ? "is-success" : "is-muted"}">${item.last === null ? "-" : item.last.toFixed(2)}</span>
        </article>
      `)
    );
    if (overview.notices.length) {
      showFeedback("#requestsFeedback", overview.notices.join(" "));
    }
    applyFilters();
  } catch (error) {
    showFeedback("#requestsFeedback", error.message || "Não foi possível carregar os pedidos.");
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
    if (button.dataset.action === "details") {
      selectRequest(request.id);
      return;
    }
    if (button.dataset.action === "duplicate") {
      duplicateRequest(request);
      return;
    }
    if (button.dataset.action === "pdf") {
      printQuoteReport({
        companyName: overview.companyName,
        request,
        comparison: request.comparison,
        results: overview.quoteResults.filter((row) => row.request_id === request.id)
      });
      return;
    }
    if (button.dataset.action === "csv") {
      exportQuoteCsv({
        request,
        results: overview.quoteResults.filter((row) => row.request_id === request.id)
      });
    }
  });

  qs("#supplierReviewForm")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!selectedRequest) {
      showFeedback("#requestsFeedback", "Selecione um pedido antes de avaliar o fornecedor.");
      return;
    }
    try {
      await submitSupplierReview({
        request_id: selectedRequest.id,
        supplier_id: qs("#reviewSupplierSelect")?.value,
        price_rating: Number(qs("#reviewPrice")?.value || 5),
        delivery_rating: Number(qs("#reviewDelivery")?.value || 5),
        service_rating: Number(qs("#reviewService")?.value || 5),
        reliability_rating: Number(qs("#reviewReliability")?.value || 5),
        comment: qs("#reviewComment")?.value || ""
      });
      showFeedback("#requestsFeedback", "Avaliação registrada com sucesso.", false);
      qs("#reviewComment").value = "";
    } catch (error) {
      showFeedback("#requestsFeedback", error.message || "Não foi possível registrar a avaliação.");
    }
  });
}

runPageBoot(init, { loadingMessage: "Carregando histórico de cotações." }).catch((error) => {
  showFeedback("#requestsFeedback", error.message || "Erro ao iniciar a tela de pedidos.");
});
