import { LOGIN_PATH } from "../config.js";
import { requireAuth, signOut } from "../auth.js";
import {
  confirmChatThread,
  estimateConstruction,
  getApiHealth,
  getChatThread,
  getRequestStatus,
  quoteMaterials,
  sendChatMessage,
  updateChatDraft
} from "../chatApi.js";
import { formatDateTime, initSidebar, qs, runPageBoot, setHTML, setLoading, setText, showAppToast, showFeedback } from "../ui.js";

const THREAD_STORAGE_KEY = "cotai_active_chat_thread";
const DUPLICATE_REQUEST_STORAGE_KEY = "cotai_request_prefill";
let activeThreadId = sessionStorage.getItem(THREAD_STORAGE_KEY) || "";
let activeRequestId = "";
let pollTimer = null;
let lastKnownRequestStatus = "";
let currentDraft = {
  title: "",
  items: [],
  deliveryMode: "",
  deliveryLocation: "",
  notes: "",
  priority: "MEDIUM"
};
let quoteRenderContext = {
  requestId: "",
  requestCode: "",
  results: []
};
let latestDynamicPreview = null;
let latestConstructionPreview = null;

const STATUS_LABELS = {
  DRAFT: "Rascunho",
  AWAITING_CONFIRMATION: "Aguardando confirmação",
  AWAITING_APPROVAL: "Aguardando aprovação",
  PENDING_QUOTE: "Pendente",
  PROCESSING: "Em andamento",
  DONE: "Concluído",
  ERROR: "Erro"
};

function setChatAvailability(isAvailable) {
  const input = qs("#chatComposerInput");
  const submitButton = qs("#chatComposerSubmit");
  const confirmButton = qs("#chatConfirmButton");
  const saveButton = qs("#chatSaveDraftButton");
  const suggestions = Array.from(document.querySelectorAll("[data-suggestion]"));

  if (input) {
    input.disabled = !isAvailable;
    input.placeholder = isAvailable
      ? "Descreva os materiais, as quantidades, o local de entrega e as observações"
      : "A API do chatbot está offline no momento.";
  }
  if (submitButton) submitButton.disabled = !isAvailable;
  if (saveButton) saveButton.disabled = !isAvailable || !activeThreadId;
  if (confirmButton) confirmButton.disabled = !isAvailable || confirmButton.classList.contains("hidden");
  suggestions.forEach((button) => {
    button.disabled = !isAvailable;
  });
}

function badgeClass(status) {
  const value = String(status || "").toUpperCase();
  if (value === "DONE") return "is-success";
  if (value === "ERROR") return "is-danger";
  if (["PROCESSING", "PENDING_QUOTE", "AWAITING_CONFIRMATION", "AWAITING_APPROVAL"].includes(value)) return "is-warning";
  return "is-muted";
}

function formatStatus(status) {
  const key = String(status || "").toUpperCase();
  return STATUS_LABELS[key] || key || "-";
}

function notifyStatusTransition(status, payload = {}) {
  const normalizedStatus = String(status || "").toUpperCase();
  const requestCode = payload.requestCode || qs("#chatRequestCode")?.textContent || "Pedido";

  if (normalizedStatus === "DONE") {
    showAppToast({
      tone: "success",
      icon: "bx-check-circle",
      title: "Cotacao concluida",
      message: `${requestCode} pronto para revisao no chat.`,
      actionLabel: "Ver",
      onAction: () => qs("#chatMessages")?.scrollTo({ top: qs("#chatMessages")?.scrollHeight || 0, behavior: "smooth" }),
    });
    return;
  }

  if (normalizedStatus === "AWAITING_APPROVAL") {
    showAppToast({
      tone: "warning",
      icon: "bx-time-five",
      title: "Aguardando aprovacao",
      message: `${requestCode} foi enviado para validacao administrativa.`,
      actionLabel: "Ver",
      onAction: () => qs("#chatMessages")?.scrollTo({ top: qs("#chatMessages")?.scrollHeight || 0, behavior: "smooth" }),
    });
    return;
  }

  if (normalizedStatus === "ERROR") {
    showAppToast({
      tone: "danger",
      icon: "bx-error-circle",
      title: "Cotacao com erro",
      message: `${requestCode} nao foi concluido. Revise a conversa para tentar novamente.`,
      actionLabel: "Ver",
      onAction: () => qs("#chatMessages")?.scrollTo({ top: qs("#chatMessages")?.scrollHeight || 0, behavior: "smooth" }),
    });
  }
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function parseCurrencyLine(value) {
  const match = String(value || "").match(/R\$\s*[\d.,]+/);
  return match ? match[0] : String(value || "").trim();
}

function parseQuoteResponse(content) {
  const text = String(content || "").trim();
  if (!text.startsWith("Cotacao encontrada")) return null;

  const totalMatch = text.match(/Total estimado do pedido:\s*(R\$\s*[\d.,]+)/i);
  const totalOrder = totalMatch ? totalMatch[1] : "";
  const body = text
    .replace(/^Cotacao encontrada\s*/i, "")
    .replace(/\n*Total estimado do pedido:\s*R\$\s*[\d.,]+\s*$/i, "")
    .trim();

  const sections = body
    .split(/\n\s*---\s*\n/g)
    .map((chunk) => chunk.trim())
    .filter(Boolean);

  const items = sections
    .map((section) => {
      const lines = section.split(/\n+/).map((line) => line.trim()).filter(Boolean);
      if (!lines.length) return null;

      const item = {
        name: lines[0] || "Item",
        quantity: "",
        supplier: "",
        unitPrice: "",
        total: "",
        market: "",
        note: ""
      };

      for (let index = 1; index < lines.length; index += 1) {
        const line = lines[index];
        const next = lines[index + 1] || "";

        if (/^Quantidade:/i.test(line)) {
          item.quantity = line.replace(/^Quantidade:\s*/i, "").trim();
          continue;
        }
        if (line === "Mercado") {
          item.market = next.replace(/^Media:\s*/i, "").trim();
          index += 1;
          continue;
        }
        if (line === "Observacao") {
          item.note = next.trim();
          index += 1;
          continue;
        }
        if (!item.supplier && !/^R\$/i.test(line) && !/^Total estimado:/i.test(line)) {
          item.supplier = line;
          continue;
        }
        if (!item.unitPrice && /^R\$/i.test(line)) {
          item.unitPrice = parseCurrencyLine(line);
          continue;
        }
        if (/^Total estimado:/i.test(line)) {
          item.total = parseCurrencyLine(line);
        }
      }

      return item;
    })
    .filter(Boolean);

  if (!items.length) return null;
  return { title: "Cotacao encontrada", items, totalOrder };
}

function groupResultsByItem(results = []) {
  const groups = new Map();
  results.forEach((row) => {
    const itemName = String(row.item_name || row.title || "Item").trim();
    if (!itemName) return;
    const bucket = groups.get(itemName) || [];
    bucket.push(row);
    groups.set(itemName, bucket);
  });
  return Array.from(groups.entries()).map(([name, offers]) => ({ name, offers }));
}

function renderOfferBadges(offer) {
  const badges = [];
  if (offer.is_best_overall) badges.push('<span class="app-badge is-success">Melhor oferta</span>');
  if (offer.is_best_price) badges.push('<span class="app-badge is-info">Melhor preco</span>');
  if (offer.is_best_delivery) badges.push('<span class="app-badge is-warning">Melhor prazo</span>');
  return badges.join("");
}

function buildStructuredQuoteData(requestId, parsed) {
  if (!requestId || requestId !== quoteRenderContext.requestId || !quoteRenderContext.results.length) {
    return parsed;
  }

  const items = groupResultsByItem(quoteRenderContext.results).map((group) => {
    const sortedOffers = [...group.offers].sort((left, right) => {
      if (left.is_best_overall && !right.is_best_overall) return -1;
      if (!left.is_best_overall && right.is_best_overall) return 1;
      return Number(left.total_price || left.price || 999999) - Number(right.total_price || right.price || 999999);
    });
    const primary = sortedOffers[0] || {};
    const offerUnitPrices = sortedOffers.map((offer) => Number(offer.unit_price ?? offer.price ?? 0));
    return {
      name: group.name,
      quantity: parsed?.items?.find((item) => item.name === group.name)?.quantity || "",
      supplier: String(primary.supplier_name || primary.supplier || "-"),
      unitPrice: primary.unit_price || primary.price ? `R$ ${Number(primary.unit_price ?? primary.price).toFixed(2).replace(".", ",")}` : "-",
      total: primary.total_price ? `R$ ${Number(primary.total_price).toFixed(2).replace(".", ",")}` : "-",
      market: sortedOffers.length > 1
        ? `de R$ ${Number(Math.min(...offerUnitPrices)).toFixed(2).replace(".", ",")} a R$ ${Number(Math.max(...offerUnitPrices)).toFixed(2).replace(".", ",")}`
        : parsed?.items?.find((item) => item.name === group.name)?.market || "-",
      note: parsed?.items?.find((item) => item.name === group.name)?.note || "",
      offers: sortedOffers.slice(0, 3)
    };
  });

  return {
    title: parsed?.title || "Cotacao encontrada",
    totalOrder: parsed?.totalOrder || "",
    items
  };
}

function renderQuoteResponseCard(row) {
  const content = String(row?.content || "");
  const parsed = parseQuoteResponse(content);
  if (!parsed) return "";
  const requestId = String(row?.metadata?.request_id || "");
  const structured = buildStructuredQuoteData(requestId, parsed);

  const cards = structured.items
    .map(
      (item) => `
        <section class="chat-quote-card">
          <div class="chat-quote-card-head">
            <strong>${escapeHtml(item.name)}</strong>
            ${item.quantity ? `<span class="app-badge is-muted">${escapeHtml(item.quantity)}</span>` : ""}
          </div>
          ${item.offers?.length ? `<div class="chat-quote-badges">${renderOfferBadges(item.offers[0])}</div>` : ""}
          <div class="chat-quote-grid">
            <div class="chat-quote-metric">
              <span class="chat-quote-label"><i class="bx bx-store-alt" aria-hidden="true"></i>Fornecedor</span>
              <strong>${escapeHtml(item.supplier || "-")}</strong>
            </div>
            <div class="chat-quote-metric">
              <span class="chat-quote-label"><i class="bx bx-purchase-tag-alt" aria-hidden="true"></i>Unitario</span>
              <strong>${escapeHtml(item.unitPrice || "-")}</strong>
            </div>
            <div class="chat-quote-metric">
              <span class="chat-quote-label"><i class="bx bx-package" aria-hidden="true"></i>Total</span>
              <strong>${escapeHtml(item.total || "-")}</strong>
            </div>
            <div class="chat-quote-metric">
              <span class="chat-quote-label"><i class="bx bx-line-chart" aria-hidden="true"></i>Mercado</span>
              <strong>${escapeHtml(item.market || "-")}</strong>
            </div>
          </div>
          ${
            item.offers?.length > 1
              ? `<div class="chat-quote-offers">
                  ${item.offers
                    .slice(0, 3)
                    .map(
                      (offer) => `
                        <div class="chat-quote-offer-chip">
                          <span>${escapeHtml(offer.supplier_name || offer.supplier || "Fornecedor")}</span>
                          <strong>R$ ${Number(offer.unit_price ?? offer.price ?? 0).toFixed(2).replace(".", ",")}</strong>
                          <div class="chat-quote-offer-badges">${renderOfferBadges(offer)}</div>
                        </div>
                      `
                    )
                    .join("")}
                </div>`
              : ""
          }
          ${
            item.note
              ? `<p class="chat-quote-note"><i class="bx bx-info-circle" aria-hidden="true"></i>${escapeHtml(item.note)}</p>`
              : ""
          }
        </section>
      `
    )
    .join("");

  return `
    <div class="chat-quote-response">
      <div class="chat-quote-summary">
        <span class="app-badge is-success">Cota</span>
        <strong>${structured.title}</strong>
        ${structured.totalOrder ? `<span class="chat-quote-total-order">Total do pedido: ${escapeHtml(structured.totalOrder)}</span>` : ""}
      </div>
      <div class="chat-quote-stack">${cards}</div>
      <div class="chat-quote-actions">
        <a class="btn btn-primary" href="requests.html">Confirmar pedido</a>
        <button class="btn btn-secondary" type="button" data-quote-refine="true">Refinar cotacao</button>
      </div>
    </div>
  `;
}

function renderDynamicMarketPreview(payload) {
  const offers = Array.isArray(payload?.offers) ? payload.offers : [];
  if (!offers.length) return "";

  const itemLabel = payload?.query?.item || "Material";
  const brandLabel = payload?.query?.marca ? ` ${payload.query.marca}` : "";
  const specificationLabel = payload?.query?.especificacao ? ` ${payload.query.especificacao}` : "";
  const searchTerm = payload?.search_term || payload?.query?.raw || itemLabel;

  return `
    <div class="chat-quote-response">
      <div class="chat-quote-summary">
        <span class="app-badge is-info">Mercado</span>
        <strong>Previa de mercado para ${escapeHtml(`${itemLabel}${brandLabel}${specificationLabel}`.trim())}</strong>
        <span class="chat-quote-total-order">${payload.cache_hit ? "Resultado em cache" : "Busca ao vivo"}</span>
      </div>
      <div class="chat-quote-stack">
        ${offers
          .map(
            (offer, index) => `
              <section class="chat-quote-card">
                <div class="chat-quote-card-head">
                  <strong>${index === 0 ? "Melhor preco encontrado" : `Opcao ${index + 1}`}</strong>
                  <span class="app-badge ${index === 0 ? "is-success" : "is-muted"}">${escapeHtml(offer.supplier || offer.source || "Fornecedor")}</span>
                </div>
                <div class="chat-quote-grid">
                  <div class="chat-quote-metric">
                    <span class="chat-quote-label"><i class="bx bx-package" aria-hidden="true"></i>Produto</span>
                    <strong>${escapeHtml(offer.product_name || "-")}</strong>
                  </div>
                  <div class="chat-quote-metric">
                    <span class="chat-quote-label"><i class="bx bx-purchase-tag-alt" aria-hidden="true"></i>Preco</span>
                    <strong>${escapeHtml(offer.display_price || "-")}</strong>
                  </div>
                  <div class="chat-quote-metric">
                    <span class="chat-quote-label"><i class="bx bx-check-shield" aria-hidden="true"></i>Match</span>
                    <strong>${offer.match_score ? `${Math.round(Number(offer.match_score) * 100)}%` : "Validado"}</strong>
                  </div>
                  <div class="chat-quote-metric">
                    <span class="chat-quote-label"><i class="bx bx-link-external" aria-hidden="true"></i>Oferta</span>
                    <strong><a href="${escapeHtml(offer.offer_url || "#")}" target="_blank" rel="noreferrer">Abrir link</a></strong>
                  </div>
                </div>
              </section>
            `
          )
          .join("")}
      </div>
      <p class="chat-quote-note"><i class="bx bx-info-circle" aria-hidden="true"></i>Busca usada: ${escapeHtml(searchTerm)}. Esta previa ajuda a decidir mais rapido antes da cotacao consolidada.</p>
    </div>
  `;
}

function looksLikeConstructionEstimate(message) {
  const text = String(message || "").toLowerCase();
  return /(\d+(?:[.,]\d+)?)\s*m2\b/.test(text) && /(parede|piso|laje|revestimento|alvenaria)/.test(text);
}

function renderConstructionPreview(payload) {
  const items = Array.isArray(payload?.items) ? payload.items : [];
  if (!items.length) return "";

  return `
    <div class="chat-quote-response">
      <div class="chat-quote-summary">
        <span class="app-badge is-success">Construcao</span>
        <strong>${escapeHtml(payload?.summary?.title || "Estimativa inicial")}</strong>
        <span class="chat-quote-total-order">${escapeHtml(payload?.summary?.subtitle || "")}</span>
      </div>
      <div class="chat-quote-stack">
        ${items
          .map(
            (item) => `
              <section class="chat-quote-card">
                <div class="chat-quote-card-head">
                  <strong>${escapeHtml(item.material || "Material")}</strong>
                  <span class="app-badge is-muted">${escapeHtml(item.display_quantity || "-")}</span>
                </div>
                <p class="chat-quote-note"><i class="bx bx-info-circle" aria-hidden="true"></i>${escapeHtml(item.notes || "Composicao inicial para estudo.")}</p>
              </section>
            `
          )
          .join("")}
      </div>
      <p class="chat-quote-note"><i class="bx bx-shield-quarter" aria-hidden="true"></i>${escapeHtml(payload?.summary?.disclaimer || "Valide a composicao antes da compra.")}</p>
    </div>
  `;
}

function renderMessageBody(row) {
  return renderQuoteResponseCard(row) || escapeHtml(String(row.content || "")).replace(/\n/g, "<br>");
}

function renderMessage(row) {
  const tone = row.role === "user" ? "is-user" : row.role === "assistant" ? "is-assistant" : "is-system";
  return `
    <article class="chat-row ${tone}">
      <div class="chat-bubble ${tone}">
        <div class="chat-bubble-body">${renderMessageBody(row)}</div>
      </div>
    </article>
  `;
}

function renderDetectedItems(items) {
  if (!items?.length) {
    return '<li class="app-empty">Nenhum item detectado ainda.</li>';
  }

  return items
    .map((item) => `<li><strong>${escapeHtml(item.normalized_name || item.name)}</strong><span>${item.quantity ?? "-"} ${escapeHtml(item.unit || "un")}</span></li>`)
    .join("");
}

function renderResults(results) {
  if (!results?.length) {
    return '<li class="app-empty">Os resultados aparecerão aqui assim que a cotação terminar.</li>';
  }

  return results
    .slice(0, 8)
    .map(
      (item) => `
      <li>
        <strong>${escapeHtml(item.item_name || item.title || "Item")}</strong>
        <span>${escapeHtml(item.supplier_name || item.supplier || item.source || "Fornecedor")}</span>
        <span>${item.unit_price || item.price ? `Unit.: ${Number(item.unit_price ?? item.price).toFixed(2)}` : "Unit.: -"}</span>
        <span>${item.total_price ? `Total: ${Number(item.total_price).toFixed(2)}` : "Total: -"}</span>
        <span>${escapeHtml(item.delivery_label || (item.delivery_days ? `${item.delivery_days} dia(s)` : "Prazo -"))}</span>
        <span>${escapeHtml(item.origin_label || item.source_name || item.source || "Origem -")}</span>
        <span>${item.is_best_overall ? "Melhor opção" : item.is_best_price ? "Melhor preço" : item.is_best_delivery ? "Melhor prazo" : "-"}</span>
      </li>
    `
    )
    .join("");
}

function renderTimeline(items) {
  if (!items?.length) {
    return '<li class="app-empty">O histórico operacional aparecerá aqui.</li>';
  }
  return items
    .map((item) => `<li><strong>${escapeHtml(item.label || "-")}</strong><span>${formatDateTime(item.at)}</span></li>`)
    .join("");
}

function renderNotifications(items) {
  if (!items?.length) {
    return '<li class="app-empty">Nenhum alerta no momento.</li>';
  }
  return items
    .map((item) => `<li><strong>${item.tone === "warning" ? "Atenção" : "Info"}</strong><span>${escapeHtml(item.message)}</span></li>`)
    .join("");
}

function renderEstimate(items) {
  if (!items?.length) {
    return '<li class="app-empty">Use como estimativa inicial, não como memorial definitivo.</li>';
  }
  return items.map((item) => `<li><strong>${escapeHtml(item.label)}</strong><span>${escapeHtml(item.value)}</span></li>`).join("");
}

function renderDraftItemsEditor(items) {
  if (!items.length) {
    return '<div class="app-empty">Nenhum item no rascunho. Envie uma mensagem ou adicione manualmente.</div>';
  }
  return items
    .map(
      (item, index) => `
      <div class="form-row" data-draft-item="${index}">
        <label>Item ${index + 1}</label>
        <input data-field="name" type="text" value="${escapeHtml(item.name || item.normalized_name || "")}" placeholder="Material" />
        <input data-field="quantity" type="number" step="0.01" value="${item.quantity ?? ""}" placeholder="Qtd" />
        <input data-field="unit" type="text" value="${escapeHtml(item.unit || "un")}" placeholder="Unidade" />
        <button class="btn btn-ghost" type="button" data-remove-item="${index}">Remover</button>
      </div>
    `
    )
    .join("");
}

function buildDraftMessage(items = [], deliveryLocation = "") {
  if (!items.length) return "";
  const parts = items.map((item) => {
    const quantity = item.quantity ? `${item.quantity} ${item.unit || "un"}` : item.unit || "un";
    return `${item.name || item.normalized_name || "material"} - ${quantity}`.trim();
  });
  const locationSuffix = deliveryLocation ? ` para entrega em ${deliveryLocation}` : "";
  return `Quero cotar ${parts.join(", ")}${locationSuffix}.`;
}

function parseImportedItems(text) {
  return String(text || "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const match =
        line.match(/^(?<name>.+?)\s*[-:x]\s*(?<quantity>\d+(?:[.,]\d+)?)\s*(?<unit>.+)$/i) ||
        line.match(/^(?<quantity>\d+(?:[.,]\d+)?)\s*(?<unit>[a-zA-ZÀ-ÿ0-9/.-]+)\s+(?:de\s+)?(?<name>.+)$/i);
      if (!match?.groups) {
        return {
          name: line,
          normalized_name: line,
          quantity: null,
          unit: "un",
          raw: line
        };
      }
      const quantity = Number(String(match.groups.quantity || "").replace(",", ".")) || null;
      const name = String(match.groups.name || line).trim();
      const unit = String(match.groups.unit || "un").trim();
      return {
        name,
        normalized_name: name,
        quantity,
        unit,
        raw: line
      };
    });
}

function buildComparisonSummary(comparison) {
  const best = comparison?.best_supplier || comparison?.bestSupplier;
  if (!best) {
    return "A comparação entre fornecedores aparecerá aqui.";
  }
  return `${comparison.supplier_count || comparison.ranked?.length || 0} fornecedor(es) comparados. Melhor consolidado: ${best.supplier} com ${best.items} item(ns) e total aproximado de ${best.total_price?.toFixed?.(2) || best.total_price}.`;
}

function syncDraftInputs() {
  const titleInput = qs("#draftTitleInput");
  const deliveryModeInput = qs("#draftDeliveryMode");
  const deliveryLocationInput = qs("#draftDeliveryLocation");
  const notesInput = qs("#draftNotesInput");
  const priorityInput = qs("#draftPriority");

  if (titleInput) titleInput.value = currentDraft.title || "";
  if (deliveryModeInput) deliveryModeInput.value = currentDraft.deliveryMode || "";
  if (deliveryLocationInput) deliveryLocationInput.value = currentDraft.deliveryLocation || "";
  if (notesInput) notesInput.value = currentDraft.notes || "";
  if (priorityInput) priorityInput.value = currentDraft.priority || "MEDIUM";
  setHTML("#draftItemsEditor", renderDraftItemsEditor(currentDraft.items || []));
}

function readDraftFromInputs() {
  currentDraft.title = qs("#draftTitleInput")?.value?.trim() || currentDraft.title || "";
  currentDraft.deliveryMode = qs("#draftDeliveryMode")?.value?.trim() || "";
  currentDraft.deliveryLocation = qs("#draftDeliveryLocation")?.value?.trim() || "";
  currentDraft.notes = qs("#draftNotesInput")?.value?.trim() || "";
  currentDraft.priority = qs("#draftPriority")?.value || "MEDIUM";

  const rows = Array.from(document.querySelectorAll("[data-draft-item]"));
  if (rows.length) {
    currentDraft.items = rows
      .map((row) => ({
        name: row.querySelector('[data-field="name"]')?.value?.trim() || "",
        normalized_name: row.querySelector('[data-field="name"]')?.value?.trim() || "",
        quantity: Number(row.querySelector('[data-field="quantity"]')?.value || 0) || null,
        unit: row.querySelector('[data-field="unit"]')?.value?.trim() || "un",
        raw: row.querySelector('[data-field="name"]')?.value?.trim() || ""
      }))
      .filter((item) => item.name);
  }

  return currentDraft;
}

function updateSidebar(payload) {
  const request = payload.request;
  const latestQuote = payload.latest_quote;
  const status = request?.status || payload.thread?.status || "DRAFT";
  const draft = payload.draft || {};

  currentDraft = {
    title: draft.title || payload.thread?.title || "",
    items: draft.items || payload.detected_items || [],
    deliveryMode: draft.delivery_mode || "",
    deliveryLocation: draft.delivery_location || "",
    notes: draft.notes || "",
    priority: draft.priority || request?.priority || "MEDIUM"
  };
  syncDraftInputs();

  setText("#chatThreadTitle", payload.thread?.title || "Fale com a Cota");
  setText("#chatRequestCode", request?.request_code || "Aguardando");
  setText("#chatRequestStatus", formatStatus(status));
  setText("#chatRequestPriority", request?.priority || currentDraft.priority || "MEDIUM");
  setText("#chatRequestSla", formatDateTime(request?.sla_due_at || null));
  setText("#chatApprovalStatus", request?.approval_status || (request?.approval_required ? "PENDING" : "NOT_REQUIRED"));
  const statusBadge = qs("#chatRequestStatus");
  if (statusBadge) {
    statusBadge.dataset.status = String(status || "");
    statusBadge.className = `app-badge ${badgeClass(status)}`;
  }
  setText("#chatRequestUpdated", formatDateTime(latestQuote?.updated_at || request?.processed_at || request?.created_at || draft.saved_at || null));

  const confirmButton = qs("#chatConfirmButton");
  if (confirmButton) {
    confirmButton.disabled = !(currentDraft.items?.length) || Boolean(request?.id);
    confirmButton.classList.toggle("hidden", Boolean(request?.id) || !["AWAITING_CONFIRMATION", "DRAFT"].includes(payload.thread?.status));
  }

  const saveButton = qs("#chatSaveDraftButton");
  if (saveButton) {
    saveButton.disabled = !activeThreadId;
  }

  setHTML("#chatDetectedItems", renderDetectedItems(payload.detected_items));
  setHTML("#chatQuoteResults", renderResults(payload.results));
  setHTML("#chatTimeline", renderTimeline(payload.timeline));
  setHTML("#chatNotifications", renderNotifications(payload.notifications));
  setText("#chatComparisonSummary", buildComparisonSummary(payload.comparison));
  setText(
    "#chatSummary",
    latestQuote?.response_text ||
      request?.last_error ||
      (payload.duplicate_candidate ? `Pedido similar encontrado: ${payload.duplicate_candidate.request_code}.` : "A conversa vai consolidar o resumo final aqui.")
  );
}

function applyPrefillDraft(prefill, feedbackMessage = "") {
  if (!prefill) return;
  currentDraft = {
    title: prefill.title || currentDraft.title || "",
    items: prefill.items?.length ? prefill.items : currentDraft.items || [],
    deliveryMode: prefill.deliveryMode || currentDraft.deliveryMode || "",
    deliveryLocation: prefill.deliveryLocation || currentDraft.deliveryLocation || "",
    notes: prefill.notes || currentDraft.notes || "",
    priority: prefill.priority || currentDraft.priority || "MEDIUM"
  };
  syncDraftInputs();
  const input = qs("#chatComposerInput");
  if (input && !input.value.trim()) {
    input.value = buildDraftMessage(currentDraft.items, currentDraft.deliveryLocation);
  }
  setText(
    "#chatPrefillNotice",
    feedbackMessage || `Rascunho reaproveitado de ${prefill.request_code || "pedido anterior"} com ${currentDraft.items.length} item(ns).`
  );
}

function setChatStage(hasMessages) {
  const page = document.querySelector(".quote-chat-page-bare");
  const home = qs("#chatHomeState");
  const stream = qs("#chatMessages");
  if (page) page.classList.toggle("is-thread-active", hasMessages);
  if (home) home.classList.toggle("hidden", hasMessages);
  if (stream) stream.classList.toggle("hidden", !hasMessages);
}

function renderThread(payload) {
  activeThreadId = payload.thread.id;
  sessionStorage.setItem(THREAD_STORAGE_KEY, activeThreadId);
  activeRequestId = payload.request?.id || "";
  lastKnownRequestStatus = String(payload.request?.status || payload.thread?.status || "").toUpperCase();
  quoteRenderContext = {
    requestId: String(payload.request?.id || payload.latest_quote?.request_id || ""),
    requestCode: String(payload.request?.request_code || ""),
    results: Array.isArray(payload.results) ? payload.results : []
  };
  const list = qs("#chatMessages");
  if (list) {
    list.innerHTML = payload.messages.length
      ? payload.messages.map(renderMessage).join("")
      : '<div class="chat-empty"><div class="chat-empty-copy"><strong>Descreva os materiais e as quantidades para iniciar a cotação.</strong></div></div>';
    list.scrollTop = list.scrollHeight;
  }
  setChatStage(Boolean(payload.messages.length));
  if (payload?.request?.id || !Array.isArray(payload?.detected_items) || !payload.detected_items.length) {
    latestDynamicPreview = null;
  }
  injectDynamicPreviewIntoLatestAssistant();

  updateSidebar(payload);
  managePolling();
}

function injectDynamicPreviewIntoLatestAssistant() {
  if (!latestDynamicPreview && !latestConstructionPreview) return;
  const list = qs("#chatMessages");
  if (!list) return;
  const target = list.querySelector(".chat-row.is-assistant:last-of-type .chat-bubble-body");
  if (!target) return;
  target.querySelectorAll('[data-market-preview="true"], [data-construction-preview="true"]').forEach((node) => node.remove());

  if (latestConstructionPreview) {
    const constructionCard = renderConstructionPreview(latestConstructionPreview);
    if (constructionCard) {
      const wrapper = document.createElement("section");
      wrapper.dataset.constructionPreview = "true";
      wrapper.innerHTML = constructionCard;
      target.appendChild(wrapper);
    }
  }

  if (latestDynamicPreview) {
    const marketCard = renderDynamicMarketPreview(latestDynamicPreview);
    if (marketCard) {
      const wrapper = document.createElement("section");
      wrapper.dataset.marketPreview = "true";
      wrapper.innerHTML = marketCard;
      target.appendChild(wrapper);
    }
  }
  list.scrollTop = list.scrollHeight;
}

async function loadDynamicPreview(message, payload) {
  if (!message?.trim()) return;
  if (payload?.request?.id) return;
  if (!Array.isArray(payload?.detected_items) || !payload.detected_items.length) return;

  try {
    latestDynamicPreview = await quoteMaterials(message);
    injectDynamicPreviewIntoLatestAssistant();
  } catch (_) {
    // Dynamic preview is additive only; the main chat flow should not fail because of it.
  }
}

async function loadConstructionPreview(message, payload) {
  if (!message?.trim()) return;
  if (payload?.request?.id) return;
  if (!looksLikeConstructionEstimate(message)) return;

  try {
    latestConstructionPreview = await estimateConstruction({ query: message });
    injectDynamicPreviewIntoLatestAssistant();
  } catch (_) {
    // Construction estimate is additive only; keep chat flow stable on failure.
  }
}

async function loadThread(threadId) {
  const payload = await getChatThread(threadId);
  renderThread(payload);
}

function managePolling() {
  if (pollTimer) {
    window.clearInterval(pollTimer);
    pollTimer = null;
  }

  if (!activeRequestId) return;
  const status = String(qs("#chatRequestStatus")?.dataset.status || "").toUpperCase();
  if (!["PROCESSING", "PENDING_QUOTE", "AWAITING_APPROVAL", "NEW"].includes(status)) return;

  pollTimer = window.setInterval(async () => {
    try {
      const payload = await getRequestStatus(activeRequestId);
      const badge = qs("#chatRequestStatus");
      if (badge) {
        badge.textContent = formatStatus(payload.status);
        badge.dataset.status = String(payload.status || "");
        badge.className = `app-badge ${badgeClass(payload.status)}`;
      }
      setText("#chatRequestPriority", payload.priority || currentDraft.priority || "MEDIUM");
      setText("#chatRequestSla", formatDateTime(payload.sla_due_at || null));
      setText("#chatApprovalStatus", payload.approval_status || "-");
      setText("#chatRequestUpdated", formatDateTime(payload.latest_quote?.updated_at || payload.processed_at || null));
      const nextStatus = String(payload.status || "").toUpperCase();
      if (nextStatus && nextStatus !== lastKnownRequestStatus && ["DONE", "ERROR", "AWAITING_APPROVAL"].includes(nextStatus)) {
        notifyStatusTransition(nextStatus, { requestCode: payload.request?.request_code || qs("#chatRequestCode")?.textContent });
      }
      lastKnownRequestStatus = nextStatus;
      if (["DONE", "ERROR", "AWAITING_APPROVAL"].includes(payload.status)) {
        window.clearInterval(pollTimer);
        pollTimer = null;
        await loadThread(activeThreadId);
      }
    } catch (_) {
      window.clearInterval(pollTimer);
      pollTimer = null;
    }
  }, 4000);
}

async function saveDraft(showMessage = true) {
  if (!activeThreadId) {
    showFeedback("#newRequestFeedback", "Envie uma mensagem antes de salvar o rascunho.");
    return;
  }
  const saveButton = qs("#chatSaveDraftButton");
  const draft = readDraftFromInputs();
  setLoading(saveButton, true, "Salvar rascunho", "Salvando...");
  try {
    const payload = await updateChatDraft(activeThreadId, draft);
    renderThread(payload);
    if (showMessage) {
      showFeedback("#newRequestFeedback", "Rascunho salvo com sucesso.", false);
    }
  } catch (error) {
    showFeedback("#newRequestFeedback", error.message || "Não foi possível salvar o rascunho.");
  } finally {
    setLoading(saveButton, false, "Salvar rascunho");
  }
}

async function submitMessage({ input, submitButton }) {
  const message = String(input?.value || "").trim();
  if (!message) return;

  const list = qs("#chatMessages");
  const previousMarkup = list?.innerHTML || "";
  const hadVisibleThread = !qs("#chatHomeState")?.classList.contains("hidden");
  showFeedback("#newRequestFeedback", "", true);
  setLoading(submitButton, true, "Enviar", "Enviando...");

  if (list) {
    const optimisticRows = [
      renderMessage({ role: "user", content: message }),
      `
        <article class="chat-row is-assistant is-pending">
          <div class="chat-bubble is-assistant">
            <div class="chat-bubble-body">A Cota está analisando sua solicitação...</div>
          </div>
        </article>
      `
    ].join("");
    list.innerHTML = previousMarkup ? `${previousMarkup}${optimisticRows}` : optimisticRows;
    setChatStage(true);
    list.scrollTop = list.scrollHeight;
  }

  try {
    const payload = await sendChatMessage({ threadId: activeThreadId || null, message });
    renderThread(payload);
    await loadConstructionPreview(message, payload);
    await loadDynamicPreview(message, payload);
    if (input) {
      input.value = "";
      input.style.height = "auto";
      input.focus();
    }
  } catch (error) {
    if (list) {
      list.innerHTML = previousMarkup;
      setChatStage(hadVisibleThread);
    }
    showFeedback("#newRequestFeedback", error.message || "Não foi possível enviar a mensagem.");
  } finally {
    setLoading(submitButton, false, "Enviar");
  }
}

function bindDraftEditor() {
  qs("#draftAddItemButton")?.addEventListener("click", () => {
    currentDraft.items = [...(currentDraft.items || []), { name: "", normalized_name: "", quantity: null, unit: "un", raw: "" }];
    syncDraftInputs();
  });

  document.addEventListener("click", (event) => {
    const removeButton = event.target.closest("[data-remove-item]");
    if (!removeButton) return;
    const index = Number(removeButton.dataset.removeItem);
    currentDraft.items = (currentDraft.items || []).filter((_, itemIndex) => itemIndex !== index);
    syncDraftInputs();
  });
}

function bindEstimator(input) {
  qs("#estimateMaterialsButton")?.addEventListener("click", () => {
    const type = qs("#estimateType")?.value || "wall";
    const area = Number(qs("#estimateArea")?.value || 0);
    if (!area) {
      showFeedback("#newRequestFeedback", "Informe a área para gerar a estimativa.");
      return;
    }
    const recipes = {
      wall: [
        { label: "Bloco estrutural", value: `${Math.ceil(area * 12.5)} un` },
        { label: "Argamassa", value: `${Math.ceil(area * 0.22)} m3` },
        { label: "Cimento", value: `${Math.ceil(area * 0.11)} saco(s)` }
      ],
      floor: [
        { label: "Piso", value: `${Math.ceil(area * 1.08)} m2` },
        { label: "Argamassa colante", value: `${Math.ceil(area * 0.22)} saco(s)` },
        { label: "Rejunte", value: `${Math.ceil(area * 0.05)} saco(s)` }
      ],
      slab: [
        { label: "Concreto usinado", value: `${(area * 0.12).toFixed(2)} m3` },
        { label: "Malha / aco", value: `${Math.ceil(area * 3.2)} kg` },
        { label: "Cimento equivalente", value: `${Math.ceil(area * 0.84)} saco(s)` }
      ]
    };
    const results = recipes[type] || [];
    setHTML("#estimateResults", renderEstimate(results));
    if (input && !input.value.trim()) {
      input.value = `Preciso estimar materiais para ${area} m2 de ${type === "wall" ? "parede" : type === "floor" ? "piso" : "laje"}.`;
    }
  });
}

function bindQuickImport() {
  qs("#applyImportedItemsButton")?.addEventListener("click", () => {
    const textarea = qs("#importItemsTextarea");
    const importedItems = parseImportedItems(textarea?.value || "");
    if (!importedItems.length) {
      showFeedback("#newRequestFeedback", "Cole pelo menos uma linha para importar os itens.");
      return;
    }
    currentDraft.items = importedItems;
    syncDraftInputs();
    const input = qs("#chatComposerInput");
    if (input && !input.value.trim()) {
      input.value = buildDraftMessage(importedItems, currentDraft.deliveryLocation);
    }
    setText("#chatPrefillNotice", `Lista importada com ${importedItems.length} item(ns). Revise o rascunho antes de confirmar.`);
    showFeedback("#newRequestFeedback", "Lista aplicada no rascunho.", false);
  });
}

function loadRequestPrefill() {
  const raw = sessionStorage.getItem(DUPLICATE_REQUEST_STORAGE_KEY);
  if (!raw) return false;
  sessionStorage.removeItem(DUPLICATE_REQUEST_STORAGE_KEY);
  try {
    const payload = JSON.parse(raw);
    activeThreadId = "";
    activeRequestId = "";
    sessionStorage.removeItem(THREAD_STORAGE_KEY);
    applyPrefillDraft(payload);
    return true;
  } catch (_) {
    setText("#chatPrefillNotice", "Não foi possível reaproveitar o pedido anterior.");
    return false;
  }
}

async function init() {
  initSidebar();
  const form = qs("#chatComposerForm");
  const input = qs("#chatComposerInput");
  const submitButton = qs("#chatComposerSubmit");
  const confirmButton = qs("#chatConfirmButton");
  const suggestions = Array.from(document.querySelectorAll("[data-suggestion]"));

  bindDraftEditor();
  bindEstimator(input);
  bindQuickImport();
  const prefillLoaded = loadRequestPrefill();

  suggestions.forEach((button) => {
    button.addEventListener("click", () => {
      if (!input) return;
      input.value = button.dataset.suggestion || "";
      input.focus();
    });
  });

  if (activeThreadId && !prefillLoaded) {
    try {
      await loadThread(activeThreadId);
    } catch (_) {
      sessionStorage.removeItem(THREAD_STORAGE_KEY);
      activeThreadId = "";
    }
  }

  if (!activeThreadId) {
    setChatStage(false);
  }

  input?.addEventListener("keydown", async (event) => {
    if (event.key !== "Enter" || event.shiftKey) return;
    event.preventDefault();
    await submitMessage({ input, submitButton });
  });

  submitButton?.addEventListener("click", async (event) => {
    event.preventDefault();
    await submitMessage({ input, submitButton });
  });

  form?.addEventListener("submit", async (event) => {
    event.preventDefault();
    await submitMessage({ input, submitButton });
  });

  window.__cotaiChatReady = true;

  const session = await requireAuth(LOGIN_PATH);
  if (!session) return;

  try {
    await getApiHealth();
    setChatAvailability(true);
  } catch (error) {
    setChatAvailability(true);
    showFeedback("#newRequestFeedback", error.message || "O motor de cotação parece instável, mas você ainda pode tentar enviar a mensagem.");
  }

  qs("#logoutButton")?.addEventListener("click", async () => {
    await signOut();
    window.location.replace(LOGIN_PATH);
  });

  qs("#chatSaveDraftButton")?.addEventListener("click", async () => {
    await saveDraft(true);
  });

  confirmButton?.addEventListener("click", async () => {
    if (!activeThreadId) return;
    const draft = readDraftFromInputs();
    setLoading(confirmButton, true, "Confirmar pedido", "Confirmando...");
    showFeedback("#newRequestFeedback", "", true);

    try {
      const payload = await confirmChatThread(activeThreadId, draft);
      renderThread(payload);
    } catch (error) {
      showFeedback("#newRequestFeedback", error.message || "Não foi possível confirmar o pedido.");
    } finally {
      setLoading(confirmButton, false, "Confirmar pedido");
    }
  });
}

runPageBoot(init, { loadingMessage: "Validando sessão e conectando ao motor de cotação." }).catch((error) => {
  setChatAvailability(false);
  showFeedback("#newRequestFeedback", error.message || "Não foi possível iniciar o motor de cotação.");
});
