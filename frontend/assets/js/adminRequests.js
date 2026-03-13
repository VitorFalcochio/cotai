import { collectNotice, deriveCompanies, groupCount, latestBy, mapBy, safeQuery } from "./adminCommon.js";
import { assertSupabaseConfigured, supabase } from "./supabaseClient.js";
import { reprocessRequest } from "./chatApi.js";

export async function fetchAdminRequests() {
  const notices = new Set();
  const [requestsResult, itemsResult, companiesResult, quotesResult, quoteResultsResult] = await Promise.all([
    safeQuery(
      (client) =>
        client
          .from("requests")
          .select("id, request_code, customer_name, status, company_id, created_at, updated_at, last_error, processed_at, priority, sla_due_at, approval_required, approval_status, duplicate_of_request_id")
          .order("created_at", { ascending: false })
          .limit(120),
      { fallbackData: [], missingMessage: "Tabela requests ausente. Central de pedidos em branco." }
    ),
    safeQuery(
      (client) => client.from("request_items").select("id, request_id"),
      { fallbackData: [], missingMessage: "Tabela request_items ausente. Total de itens indisponivel." }
    ),
    safeQuery(
      (client) => client.from("companies").select("id, name, plan, status"),
      { fallbackData: [], missingMessage: "Tabela companies ausente. Empresa derivada do company_id." }
    ),
    safeQuery(
      (client) =>
        client
          .from("request_quotes")
          .select("id, request_id, status, response_text, error_message, created_at, updated_at, finished_at")
          .order("created_at", { ascending: false })
          .limit(200),
      { fallbackData: [], missingMessage: "Tabela request_quotes ausente. Execucao atual indisponivel." }
    ),
    safeQuery(
      (client) =>
        client
          .from("quote_results")
          .select("request_id, supplier_name, price")
          .limit(500),
      { fallbackData: [], missingMessage: "Tabela quote_results ausente. Comparacao entre fornecedores indisponivel." }
    )
  ]);

  const itemCountMap = groupCount(itemsResult.data, "request_id");
  const derivedCompanies = deriveCompanies({
    companies: companiesResult.data,
    profiles: [],
    requests: requestsResult.data
  });
  [requestsResult, itemsResult, quotesResult, quoteResultsResult].forEach((result) => collectNotice(notices, result));
  if (derivedCompanies.length === 0 || companiesResult.status !== "missing") {
    collectNotice(notices, companiesResult);
  }
  const companyMap = mapBy(derivedCompanies, "id");
  const latestQuoteMap = latestBy(quotesResult.data, "request_id", "created_at");
  const quoteSummaryByRequest = quoteResultsResult.data.reduce((accumulator, row) => {
    const requestId = row.request_id;
    if (!requestId) return accumulator;
    const entry = accumulator.get(requestId) || { supplierCount: new Set(), bestPrice: null };
    if (row.supplier_name) entry.supplierCount.add(row.supplier_name);
    const price = Number(row.price);
    if (Number.isFinite(price)) {
      entry.bestPrice = entry.bestPrice === null ? price : Math.min(entry.bestPrice, price);
    }
    accumulator.set(requestId, entry);
    return accumulator;
  }, new Map());

  const rows = requestsResult.data.map((request) => {
    const latestQuote = latestQuoteMap.get(request.id);
    const quoteSummary = quoteSummaryByRequest.get(request.id);
    return {
      id: request.id,
      requestCode: request.request_code || request.id,
      company: companyMap.get(request.company_id)?.name || request.company_id || "-",
      customerName: request.customer_name || "-",
      status: request.status || "NEW",
      priority: request.priority || "MEDIUM",
      slaDueAt: request.sla_due_at || null,
      approvalRequired: Boolean(request.approval_required),
      approvalStatus: request.approval_status || "NOT_REQUIRED",
      duplicateOfRequestId: request.duplicate_of_request_id || "",
      itemCount: itemCountMap.get(request.id) || 0,
      createdAt: request.created_at,
      updatedAt: request.updated_at,
      execution: latestQuote?.status || "-",
      latestResponse: latestQuote?.response_text || "",
      latestError: latestQuote?.error_message || request.last_error || "",
      processedAt: request.processed_at || latestQuote?.finished_at || null,
      supplierCount: quoteSummary?.supplierCount?.size || 0,
      bestPrice: quoteSummary?.bestPrice ?? null
    };
  });

  return { rows, notices: Array.from(notices) };
}

export async function updateRequest(requestId, patch) {
  assertSupabaseConfigured();
  const { error } = await supabase.from("requests").update(patch).eq("id", requestId);
  if (error) throw error;
}

export async function reprocessAdminRequest(requestId, reason) {
  return reprocessRequest(requestId, reason);
}
