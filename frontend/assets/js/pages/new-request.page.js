import { LOGIN_PATH } from "../config.js";
import { requireAuth, signOut } from "../auth.js";
import {
  confirmChatThread,
  getApiHealth,
  getChatThread,
  getRequestStatus,
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

function renderMessage(row) {
  const tone = row.role === "user" ? "is-user" : row.role === "assistant" ? "is-assistant" : "is-system";
  return `
    <article class="chat-row ${tone}">
      <div class="chat-bubble ${tone}">
        <div class="chat-bubble-body">${escapeHtml(row.content || "").replace(/\n/g, "<br>")}</div>
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

  setText("#chatThreadTitle", payload.thread?.title || "Nova cotação");
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

  const list = qs("#chatMessages");
  if (list) {
    list.innerHTML = payload.messages.length
      ? payload.messages.map(renderMessage).join("")
      : '<div class="chat-empty"><div class="chat-empty-copy"><strong>Descreva os materiais e as quantidades para iniciar a cotação.</strong></div></div>';
    list.scrollTop = list.scrollHeight;
  }
  setChatStage(Boolean(payload.messages.length));

  updateSidebar(payload);
  managePolling();
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

  showFeedback("#newRequestFeedback", "", true);
  setLoading(submitButton, true, "Enviar", "Enviando...");

  try {
    const payload = await sendChatMessage({ threadId: activeThreadId || null, message });
    renderThread(payload);
    if (input) {
      input.value = "";
      input.style.height = "auto";
      input.focus();
    }
  } catch (error) {
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
  const session = await requireAuth(LOGIN_PATH);
  if (!session) return;

  initSidebar();
  await getApiHealth();
  setChatAvailability(true);

  qs("#logoutButton")?.addEventListener("click", async () => {
    await signOut();
    window.location.replace(LOGIN_PATH);
  });

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

  form?.addEventListener("submit", async (event) => {
    event.preventDefault();
    await submitMessage({ input, submitButton });
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
