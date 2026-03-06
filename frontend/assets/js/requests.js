import { assertSupabaseConfigured, supabase } from "./supabaseClient.js";

function getRequestCode(request) {
  if (request?.request_code) return request.request_code;
  if (request?.code) return request.code;
  if (typeof request?.id === "number") return `CT-${String(request.id).padStart(4, "0")}`;
  return request?.id || `CT-${Math.floor(Math.random() * 9000 + 1000)}`;
}

function normalizeRequest(row) {
  return {
    id: row.id,
    requestCode: getRequestCode(row),
    customerName: row.customer_name || row.customer || "-",
    deliveryMode: row.delivery_mode || "-",
    deliveryLocation: row.delivery_location || "-",
    notes: row.notes || "",
    createdAt: row.created_at || row.inserted_at || null
  };
}

async function tryInsertRequest(basePayload) {
  const payloads = [
    { ...basePayload, request_code: basePayload.request_code, status: "novo" },
    { ...basePayload, request_code: basePayload.request_code },
    { ...basePayload }
  ];

  for (const payload of payloads) {
    const { data, error } = await supabase
      .from("requests")
      .insert(payload)
      .select("*")
      .single();

    if (!error) return data;
  }

  throw new Error(
    "Nao foi possivel salvar em requests. Verifique se a tabela possui customer_name, delivery_mode, delivery_location e notes."
  );
}

async function tryInsertRequestItems(requestId, items) {
  const variants = [
    items.map((item, index) => ({ request_id: requestId, item_name: item, line_number: index + 1 })),
    items.map((item) => ({ request_id: requestId, item_name: item })),
    items.map((item, index) => ({ request_id: requestId, description: item, line_number: index + 1 })),
    items.map((item) => ({ request_id: requestId, description: item })),
    items.map((item, index) => ({ request_id: requestId, item: item, line_number: index + 1 })),
    items.map((item) => ({ request_id: requestId, item }))
  ];

  for (const payload of variants) {
    const { error } = await supabase.from("request_items").insert(payload);
    if (!error) return;
  }

  throw new Error(
    "O pedido foi criado, mas nao foi possivel salvar em request_items. Verifique as colunas request_id e item_name ou description."
  );
}

export async function listRecentRequests(limit = 5) {
  assertSupabaseConfigured();

  const { data, error } = await supabase
    .from("requests")
    .select("*")
    .order("created_at", { ascending: false })
    .limit(limit);

  if (error) throw error;
  return (data || []).map(normalizeRequest);
}

export async function listAllRequests() {
  assertSupabaseConfigured();

  const { data, error } = await supabase
    .from("requests")
    .select("*")
    .order("created_at", { ascending: false });

  if (error) throw error;
  return (data || []).map(normalizeRequest);
}

export async function countRequests() {
  assertSupabaseConfigured();

  const { count, error } = await supabase
    .from("requests")
    .select("*", { count: "exact", head: true });

  if (error) throw error;
  return count || 0;
}

export async function createRequest({ customerName, deliveryMode, deliveryLocation, notes, items }) {
  assertSupabaseConfigured();

  const requestCode = `CT-${Date.now().toString().slice(-6)}`;
  const requestRow = await tryInsertRequest({
    customer_name: customerName,
    delivery_mode: deliveryMode,
    delivery_location: deliveryLocation,
    notes,
    request_code: requestCode
  });

  await tryInsertRequestItems(requestRow.id, items);

  return {
    ...normalizeRequest(requestRow),
    requestCode: getRequestCode(requestRow) || requestCode,
    items
  };
}

export function buildWhatsappMessage(request, items) {
  const deliveryLabel = [request.deliveryMode, request.deliveryLocation].filter(Boolean).join(" | ");
  const itemLines = items.map((item) => `- ${item}`).join("\n");

  return `#COTAI
Pedido: ${request.requestCode}
Entrega: ${deliveryLabel}
Itens:
${itemLines}${request.notes ? `\nObservacoes: ${request.notes}` : ""}`;
}
