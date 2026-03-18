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

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function getRequestItems(requestId) {
  return overview.requestItems.filter((item) => item.request_id === requestId);
}

function getRequestResults(requestId) {
  return overview.quoteResults.filter((row) => row.request_id === requestId);
}

function renderInsightList(items, formatter, emptyTitle, emptyCopy) {
  if (!items?.length) {
    return `<article class="entity-list-item"><div class="entity-list-copy"><p>${emptyTitle}</p><strong>${emptyCopy}</strong></div><span class="app-badge is-muted">INFO</span></article>`;
  }
  return items.map(formatter).join("");
}

function statusRank(status) {
  const normalized = String(status || "").toUpperCase();
  if (normalized === "DONE") return 0;
  if (normalized === "PROCESSING") return 1;
  if (normalized === "PENDING_QUOTE") return 2;
  if (normalized === "AWAITING_APPROVAL") return 3;
  if (normalized === "ERROR") return 4;
  return 5;
}

function renderRows(rows) {
  if (!rows.length) {
    return '<tr><td colspan="6" class="app-empty">Nenhum pedido encontrado com os filtros atuais.</td></tr>';
  }

  return rows
    .map((row) => {
      const estimatedTotal = row.comparison?.bestSupplier?.totalPrice ?? 0;
      return `
        <tr>
          <td>
            <div class="table-entity-meta">
              <strong>${row.request_code || row.requestCode || row.id}</strong>
              <small>${row.customer_name || row.customerName || "Sem cliente"}${row.previous_request_code ? ` - recota semelhante a ${row.previous_request_code}` : ""}</small>
            </div>
          </td>
          <td>
            <div class="table-entity-meta">
              <strong><span class="app-badge ${badgeClass(row.status)}">${formatStatus(row.status)}</span></strong>
              <small>${row.priority || "MEDIUM"}</small>
            </div>
          </td>
          <td>
            <div class="table-entity-meta">
              <strong>${row.best_supplier_name || "-"}</strong>
              <small>${estimatedTotal ? `Total estimado ${formatCurrencyBRL(estimatedTotal)}` : "Sem total consolidado"}</small>
            </div>
          </td>
          <td>
            <div class="table-entity-meta">
              <strong>${row.delivery_location || "-"}</strong>
              <small>${row.approval_status || "NOT_REQUIRED"}</small>
            </div>
          </td>
          <td>${formatDateTime(row.updated_at || row.created_at)}</td>
          <td class="app-actions">
            <button class="btn btn-ghost" data-action="details" data-id="${row.id}">Detalhes</button>
            <button class="btn btn-ghost" data-action="duplicate" data-id="${row.id}">Recotar</button>
            <button class="btn btn-ghost" data-action="pdf" data-id="${row.id}">PDF</button>
            <button class="btn btn-ghost" data-action="csv" data-id="${row.id}">CSV</button>
          </td>
        </tr>
      `;
    })
    .join("");
}

function getDecisionSummary(request) {
  const ranked = request?.comparison?.ranked || [];
  const bestPrice = ranked[0] || null;
  const bestDelivery = [...ranked]
    .filter((supplier) => supplier.averageDeliveryDays !== null && supplier.averageDeliveryDays !== undefined)
    .sort((left, right) => left.averageDeliveryDays - right.averageDeliveryDays)[0] || null;
  const bestOverall = [...ranked].sort((left, right) => {
    if ((right.bestOverallCount || 0) !== (left.bestOverallCount || 0)) {
      return (right.bestOverallCount || 0) - (left.bestOverallCount || 0);
    }
    return (left.totalPrice || 0) - (right.totalPrice || 0);
  })[0] || null;

  return [
    { label: "Melhor preco", value: bestPrice ? `${bestPrice.supplier} - ${formatCurrencyBRL(bestPrice.totalPrice || 0)}` : "-" },
    { label: "Melhor prazo", value: bestDelivery ? `${bestDelivery.supplier} - ${Math.round(bestDelivery.averageDeliveryDays)} dia(s)` : "-" },
    { label: "Melhor opcao geral", value: bestOverall ? bestOverall.supplier : request?.best_supplier_name || "-" },
    { label: "Total estimado", value: bestPrice ? formatCurrencyBRL(bestPrice.totalPrice || 0) : "-" }
  ];
}

function renderDecisionSummary(request) {
  return getDecisionSummary(request)
    .map((item) => `<article class="comparison-summary-card"><span>${item.label}</span><strong>${escapeHtml(item.value)}</strong></article>`)
    .join("");
}

function renderComparison(request) {
  if (!request?.comparison?.ranked?.length) {
    return '<article class="entity-list-item"><div class="entity-list-copy"><p>Comparador</p><strong>Selecione um pedido com resultados consolidados.</strong></div><span class="app-badge is-muted">INFO</span></article>';
  }

  const items = getRequestItems(request.id)
    .map((item) => item.item_name || item.description || "Material")
    .slice(0, 8);

  return `
    <div class="comparison-offer-list">
      ${request.comparison.ranked
        .map(
          (supplier) => `
            <article class="comparison-offer-card">
              <header>
                <strong>${escapeHtml(supplier.supplier)}</strong>
                <span class="app-badge ${supplier.supplier === request.best_supplier_name ? "is-success" : "is-muted"}">
                  ${supplier.supplier === request.best_supplier_name ? "Melhor opcao" : `${supplier.items} item(ns)`}
                </span>
              </header>
              <div class="comparison-offer-meta">
                <span>Total ${formatCurrencyBRL(supplier.totalPrice || 0)}</span>
                <span>${supplier.averageDeliveryDays ? `${Math.round(supplier.averageDeliveryDays)} dia(s)` : "Prazo -"} </span>
                <span>${supplier.bestOverallCount || 0} destaque(s)</span>
              </div>
              <p>${supplier.supplier === request.best_supplier_name ? "Fornecedor lider da comparacao atual." : "Alternativa util para negociar preco ou prazo."}</p>
            </article>
          `
        )
        .join("")}
      <article class="comparison-offer-card">
        <header>
          <strong>Itens do pedido</strong>
          <span class="app-badge is-muted">${items.length}</span>
        </header>
        <div class="comparison-item-list">
          ${items.length ? items.map((item) => `<span class="comparison-item-pill">${escapeHtml(item)}</span>`).join("") : '<span class="app-badge is-muted">Sem itens</span>'}
        </div>
        <p>Economia potencial estimada: ${formatCurrencyBRL(request.potential_savings || 0)}</p>
      </article>
    </div>
  `;
}

function selectRequest(requestId) {
  selectedRequest = overview.requests.find((request) => request.id === requestId) || null;
  setText("#requestDetailTitle", selectedRequest?.request_code || selectedRequest?.requestCode || "Selecione um pedido");
  setHTML("#requestDecisionSummary", renderDecisionSummary(selectedRequest));
  setHTML("#requestComparisonPanel", renderComparison(selectedRequest));
}

function buildDuplicatePayload(request) {
  const items = getRequestItems(request.id).map((item) => ({
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

function renderPipeline(rows) {
  const buckets = [
    { label: "Em andamento", value: rows.filter((row) => String(row.status || "").toUpperCase() === "PROCESSING").length, tone: "is-warning" },
    { label: "Pendente de cotacao", value: rows.filter((row) => String(row.status || "").toUpperCase() === "PENDING_QUOTE").length, tone: "is-warning" },
    { label: "Aguardando aprovacao", value: rows.filter((row) => String(row.status || "").toUpperCase() === "AWAITING_APPROVAL").length, tone: "is-warning" },
    { label: "Com erro", value: rows.filter((row) => String(row.status || "").toUpperCase() === "ERROR").length, tone: "is-danger" }
  ];

  return buckets
    .map(
      (item) => `
        <article class="entity-list-item">
          <div class="entity-list-copy"><p>${item.label}</p><strong>${item.value} pedido(s)</strong></div>
          <span class="app-badge ${item.tone}">${item.value}</span>
        </article>
      `
    )
    .join("");
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
  } else if (sortValue === "status") {
    filteredRequests.sort((a, b) => statusRank(a.status) - statusRank(b.status));
  } else {
    filteredRequests.sort((a, b) => new Date(b.updated_at || b.created_at || 0) - new Date(a.updated_at || a.created_at || 0));
  }

  setText("#requestsCount", `${filteredRequests.length} pedido(s) monitorados`);
  setHTML("#requestsTableBody", renderRows(filteredRequests));
  if ((!selectedRequest || !filteredRequests.some((item) => item.id === selectedRequest.id)) && filteredRequests.length) {
    selectRequest(filteredRequests[0].id);
  }
  if (!filteredRequests.length) {
    setText("#requestDetailTitle", "Nenhum pedido com os filtros atuais");
    setHTML("#requestDecisionSummary", renderDecisionSummary(null));
    setHTML("#requestComparisonPanel", renderComparison(null));
  }
}

async function init() {
  const session = await requireAuth(LOGIN_PATH);
  if (!session) return;

  initSidebar();
  setTableSkeleton("#requestsTableBody", 6, 6);

  qs("#logoutButton")?.addEventListener("click", async () => {
    await signOut();
    window.location.replace(LOGIN_PATH);
  });

  try {
    overview = await fetchProcurementOverview();
    const doneCount = overview.requests.filter((row) => String(row.status || "").toUpperCase() === "DONE").length;
    const processingCount = overview.requests.filter((row) =>
      ["PROCESSING", "PENDING_QUOTE", "AWAITING_CONFIRMATION", "AWAITING_APPROVAL"].includes(String(row.status || "").toUpperCase())
    ).length;

    setText("#requestsMetricTotal", String(overview.metrics.totalRequests));
    setText("#requestsMetricProcessing", String(processingCount));
    setText("#requestsMetricDone", String(doneCount));
    setText("#requestsMetricSavings", formatCurrencyBRL(overview.metrics.estimatedSavings));
    setText("#requestsMetricTotalMeta", `${overview.topMaterials[0]?.name || "Sem lideranca"} lidera a demanda`);
    setText("#requestsMetricProcessingMeta", `${overview.requests.filter((row) => String(row.status || "").toUpperCase() === "ERROR").length} com erro`);
    setText("#requestsMetricDoneMeta", `${overview.metrics.bestRecurringSupplier || "-"} recorrente`);
    setText("#requestsMetricSavingsMeta", `${overview.metrics.suppliersConsulted || 0} fornecedores comparados`);

    setHTML(
      "#requestsTopMaterials",
      renderInsightList(
        overview.topMaterials,
        (item) => `
          <article class="entity-list-item">
            <div class="entity-list-copy"><p>${item.name}</p><strong>${item.count} cotacao(oes)</strong></div>
            <span class="app-badge is-muted">MATERIAL</span>
          </article>
        `,
        "Sem materiais",
        "Os materiais mais cotados aparecem conforme o uso da plataforma."
      )
    );
    setHTML("#requestsPipeline", renderPipeline(overview.requests));

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
        results: getRequestResults(request.id)
      });
    }
    if (button.dataset.action === "csv") {
      return exportQuoteCsv({
        request,
        results: getRequestResults(request.id)
      });
    }
  });
}

runPageBoot(init, { loadingMessage: "Carregando historico de cotacoes." }).catch((error) => {
  showFeedback("#requestsFeedback", error.message || "Erro ao iniciar a tela de pedidos.");
});
