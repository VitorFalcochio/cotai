import { collectNotice, deriveCompanies, groupCount, latestBy, safeQuery } from "./adminCommon.js";
import { assertSupabaseConfigured, supabase } from "./supabaseClient.js";

export async function fetchAdminCompanies() {
  const notices = new Set();
  const [companiesResult, profilesResult, requestsResult] = await Promise.all([
    safeQuery(
      (client) =>
        client
          .from("companies")
          .select("id, name, plan, status, created_at")
          .order("created_at", { ascending: false }),
      { fallbackData: [], missingMessage: "Tabela companies ausente. Lista derivada de profiles/requests." }
    ),
    safeQuery(
      (client) => client.from("profiles").select("id, company_id, full_name, company_name, status, created_at, plan"),
      { fallbackData: [], missingMessage: "Tabela profiles ausente. Contagem de usuários indisponível." }
    ),
    safeQuery(
      (client) => client.from("requests").select("id, company_id, created_at"),
      { fallbackData: [], missingMessage: "Tabela requests ausente. Contagem de pedidos indisponivel." }
    )
  ]);

  const userCountMap = groupCount(profilesResult.data, "company_id");
  const requestCountMap = groupCount(requestsResult.data, "company_id");
  const lastRequestMap = latestBy(requestsResult.data, "company_id", "created_at");
  const companies = deriveCompanies({
    companies: companiesResult.data,
    profiles: profilesResult.data,
    requests: requestsResult.data
  });

  if (companies.length === 0 || companiesResult.status !== "missing") {
    collectNotice(notices, companiesResult);
  }
  [profilesResult, requestsResult].forEach((result) => collectNotice(notices, result));

  const rows = companies.map((company) => ({
    id: company.id,
    name: company.name || "Empresa sem nome",
    plan: company.plan || "Sem plano",
    status: company.status || "active",
    users: userCountMap.get(company.id) || 0,
    requests: requestCountMap.get(company.id) || 0,
    createdAt: company.created_at,
    lastRequestAt: lastRequestMap.get(company.id)?.created_at || null
  }));

  return { rows, notices: Array.from(notices) };
}

export async function updateCompany(companyId, patch) {
  assertSupabaseConfigured();
  const { error } = await supabase.from("companies").update(patch).eq("id", companyId);
  if (error) {
    if (String(error.message || "").toLowerCase().includes("does not exist")) {
      throw new Error("A tabela companies ainda não existe no Supabase. As ações de edição dependem dela.");
    }
    throw error;
  }
}
