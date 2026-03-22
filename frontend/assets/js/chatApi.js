import { API_BASE_URL } from "./config.js";
import { getSession } from "./auth.js";

export async function getApiHealth() {
  try {
    const response = await fetch(`${API_BASE_URL}/health`, { method: "GET" });
    if (!response.ok) {
      throw new Error("API indisponivel.");
    }
    return response.json().catch(() => ({}));
  } catch (_) {
    throw new Error("O motor de cotação está indisponível no momento. Verifique se o backend operacional da Cotai está ativo.");
  }
}

async function apiFetch(path, options = {}) {
  const session = await getSession();
  if (!session?.access_token) {
    throw new Error("Sessao invalida. Faca login novamente.");
  }

  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${session.access_token}`,
        ...(options.headers || {})
      }
    });
  } catch (error) {
    if (error instanceof TypeError) {
      throw new Error("O motor de cotação está indisponível no momento. Verifique se o backend operacional da Cotai está ativo.");
    }
    throw error;
  }

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || "Falha ao comunicar com a API da Cotai.");
  }

  return payload;
}

export function sendChatMessage({ threadId, message }) {
  return apiFetch("/chat/message", {
    method: "POST",
    body: JSON.stringify({ thread_id: threadId, message })
  });
}

export function quoteMaterials(query) {
  return apiFetch("/cotar", {
    method: "POST",
    body: JSON.stringify({ query })
  });
}

export function estimateConstruction(payload) {
  return apiFetch("/modo-construcao/estimar", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function analyzeConstruction(payload) {
  return apiFetch("/modo-construcao/analisar", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function buildConstructionProcurement(payload) {
  return apiFetch("/modo-construcao/compra", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function confirmChatThread(threadId, draft = {}) {
  return apiFetch("/chat/confirm", {
    method: "POST",
    body: JSON.stringify({
      thread_id: threadId,
      items: draft.items || undefined,
      delivery_mode: draft.deliveryMode || undefined,
      delivery_location: draft.deliveryLocation || undefined,
      notes: draft.notes || undefined,
      priority: draft.priority || undefined
    })
  });
}

export function getChatThread(threadId) {
  return apiFetch(`/chat/thread/${threadId}`);
}

export function updateChatDraft(threadId, draft) {
  return apiFetch(`/chat/thread/${threadId}/draft`, {
    method: "PUT",
    body: JSON.stringify({
      title: draft.title || undefined,
      items: draft.items || [],
      delivery_mode: draft.deliveryMode || undefined,
      delivery_location: draft.deliveryLocation || undefined,
      notes: draft.notes || undefined,
      priority: draft.priority || undefined
    })
  });
}

export function getRequestStatus(requestId) {
  return apiFetch(`/requests/${requestId}/status`);
}

export function getRequestResults(requestId) {
  return apiFetch(`/requests/${requestId}/results`);
}

export function registerExecutionEvent(requestId, payload) {
  return apiFetch(`/requests/${requestId}/execution-event`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function getOperationsOverview() {
  return apiFetch("/ops/overview");
}

export function reprocessRequest(requestId, reason) {
  return apiFetch(`/ops/requests/${requestId}/reprocess`, {
    method: "POST",
    body: JSON.stringify({ reason })
  });
}

export function approveRequest(requestId, comment = "") {
  return apiFetch(`/ops/requests/${requestId}/approve`, {
    method: "POST",
    body: JSON.stringify({ comment })
  });
}
