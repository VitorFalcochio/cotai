import { collectNotice, deriveCompanies, groupCount, latestBy, mapBy, safeQuery } from "./adminCommon.js";
import { assertSupabaseConfigured, supabase } from "./supabaseClient.js";

export async function fetchAdminRequests() {
  const notices = new Set();
  const [requestsResult, itemsResult, companiesResult, quotesResult] = await Promise.all([
    safeQuery(
      (client) =>
        client
          .from("requests")
          .select("id, request_code, customer_name, status, company_id, created_at, updated_at")
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
          .select("id, request_id, status, response_text, created_at, updated_at")
          .order("created_at", { ascending: false })
          .limit(200),
      { fallbackData: [], missingMessage: "Tabela request_quotes ausente. Execucao atual indisponivel." }
    )
  ]);

  const itemCountMap = groupCount(itemsResult.data, "request_id");
  const derivedCompanies = deriveCompanies({
    companies: companiesResult.data,
    profiles: [],
    requests: requestsResult.data
  });
  [requestsResult, itemsResult, quotesResult].forEach((result) => collectNotice(notices, result));
  if (derivedCompanies.length === 0 || companiesResult.status !== "missing") {
    collectNotice(notices, companiesResult);
  }
  const companyMap = mapBy(derivedCompanies, "id");
  const latestQuoteMap = latestBy(quotesResult.data, "request_id", "created_at");

  const rows = requestsResult.data.map((request) => {
    const latestQuote = latestQuoteMap.get(request.id);
    return {
      id: request.id,
      requestCode: request.request_code || request.id,
      company: companyMap.get(request.company_id)?.name || request.company_id || "-",
      customerName: request.customer_name || "-",
      status: request.status || "NEW",
      itemCount: itemCountMap.get(request.id) || 0,
      createdAt: request.created_at,
      updatedAt: request.updated_at,
      execution: latestQuote?.status || "-",
      latestResponse: latestQuote?.response_text || ""
    };
  });

  return { rows, notices: Array.from(notices) };
}

export async function updateRequest(requestId, patch) {
  assertSupabaseConfigured();
  const { error } = await supabase.from("requests").update(patch).eq("id", requestId);
  if (error) throw error;
}
