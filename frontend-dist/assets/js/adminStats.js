import {
  averageMinutes,
  collectNotice,
  deriveCompanies,
  formatPlanLabel,
  safeQuery,
  startOfMonthIso,
  startOfTodayIso
} from "./adminCommon.js";
import { getOperationsOverview } from "./chatApi.js";
import { getDemoAdminOverview } from "./demoData.js";

export async function fetchAdminOverview() {
  const notices = new Set();
  const todayIso = startOfTodayIso();
  const monthIso = startOfMonthIso();
  let operationsOverview = null;

  try {
    operationsOverview = await getOperationsOverview();
  } catch (error) {
    notices.add(error.message || "API operacional indisponivel. Dashboard usando apenas consultas diretas ao Supabase.");
  }

  const [
    companiesResult,
    profilesResult,
    requestsTodayResult,
    requestsMonthResult,
    requestsRecentResult,
    requestsAllResult,
    quotesDoneResult,
    quotesErrorResult,
    quotesRecentResult,
    heartbeatsResult,
    billingResult,
    suppliersResult
  ] = await Promise.all([
    safeQuery(
      (client) => client.from("companies").select("id, name, plan, status, created_at"),
      { fallbackData: [], missingMessage: "Tabela companies ausente. Overview usando company_id de profiles/requests." }
    ),
    safeQuery(
      (client) => client.from("profiles").select("id, company_id, role, full_name, company_name, status, created_at, plan"),
      { fallbackData: [], missingMessage: "Tabela profiles ausente. Usuarios totais indisponiveis." }
    ),
    safeQuery(
      (client) =>
        client.from("requests").select("id", { count: "exact", head: true }).gte("created_at", todayIso),
      { fallbackData: null, missingMessage: "Tabela requests ausente. Pedidos de hoje indisponiveis." }
    ),
    safeQuery(
      (client) =>
        client.from("requests").select("id", { count: "exact", head: true }).gte("created_at", monthIso),
      { fallbackData: null, missingMessage: "Tabela requests ausente. Pedidos do mes indisponiveis." }
    ),
    safeQuery(
      (client) =>
        client
          .from("requests")
          .select("id, request_code, customer_name, status, company_id, created_at, updated_at, priority, sla_due_at, approval_status, approval_required, duplicate_of_request_id")
          .order("created_at", { ascending: false })
          .limit(40),
      { fallbackData: [], missingMessage: "Tabela requests ausente. Tabela de pedidos recentes em branco." }
    ),
    safeQuery(
      (client) =>
        client
          .from("requests")
          .select("id, request_code, customer_name, status, company_id, created_at, updated_at, priority, sla_due_at, approval_status, approval_required, duplicate_of_request_id")
          .order("created_at", { ascending: false })
          .limit(500),
      { fallbackData: [], missingMessage: "Tabela requests ausente. Metricas estrategicas por empresa reduzidas." }
    ),
    safeQuery(
      (client) =>
        client.from("request_quotes").select("id", { count: "exact", head: true }).eq("status", "DONE"),
      { fallbackData: null, missingMessage: "Tabela request_quotes ausente. Métricas de cotação indisponíveis." }
    ),
    safeQuery(
      (client) =>
        client.from("request_quotes").select("id", { count: "exact", head: true }).eq("status", "ERROR"),
      { fallbackData: null, missingMessage: "Tabela request_quotes ausente. Erros do worker indisponiveis." }
    ),
    safeQuery(
      (client) =>
        client
          .from("request_quotes")
          .select("id, request_id, status, error_message, started_at, finished_at, created_at, updated_at, response_text")
          .order("created_at", { ascending: false })
          .limit(12),
      { fallbackData: [], missingMessage: "Tabela request_quotes ausente. Execucoes recentes indisponiveis." }
    ),
    safeQuery(
      (client) =>
        client
          .from("worker_heartbeats")
          .select("*")
          .order("created_at", { ascending: false })
          .limit(1),
      { fallbackData: [], missingMessage: "Tabela worker_heartbeats ausente. Status do worker usando fallback." }
    ),
    safeQuery(
      (client) => client.from("billing_subscriptions").select("*"),
      { fallbackData: [], missingMessage: "Tabela billing_subscriptions ausente. Receita exibida em modo demonstracao." }
    ),
    safeQuery(
      (client) => client.from("suppliers").select("id, name, company_id, quote_participation_count, average_rating, average_delivery_days"),
      { fallbackData: [], missingMessage: "", permissionMessage: "", errorMessage: "" }
    )
  ]);

  const companies = deriveCompanies({
    companies: companiesResult.data,
    profiles: profilesResult.data,
    requests: requestsRecentResult.data
  });

  if (companies.length === 0 || companiesResult.status !== "missing") {
    collectNotice(notices, companiesResult);
  }
  [
    profilesResult,
    requestsTodayResult,
    requestsMonthResult,
    requestsRecentResult,
    requestsAllResult,
    quotesDoneResult,
    quotesErrorResult,
    quotesRecentResult,
    heartbeatsResult,
    billingResult,
    suppliersResult
  ].forEach((result) => collectNotice(notices, result));

  const profiles = profilesResult.data;
  const recentRequests = requestsRecentResult.data;
  const allRequests = requestsAllResult.data;
  const recentQuotes = quotesRecentResult.data;
  const suppliers = suppliersResult.data;
  const latestHeartbeat = heartbeatsResult.data?.[0] || null;

  const activeCompanies = companies.filter((company) => String(company?.status || "active").toLowerCase() !== "inactive");
  const planCounts = companies.reduce(
    (accumulator, company) => {
      const plan = formatPlanLabel(company?.plan).toLowerCase();
      if (plan.includes("prata")) accumulator.prata += 1;
      else if (plan.includes("ouro")) accumulator.ouro += 1;
      else if (plan.includes("diamante")) accumulator.diamante += 1;
      return accumulator;
    },
    { prata: 0, ouro: 0, diamante: 0 }
  );

  const responseMinutes = averageMinutes(
    recentQuotes.filter((quote) => quote?.status === "DONE"),
    "started_at",
    "finished_at"
  );

  const estimatedRevenue = billingResult.data.length
    ? billingResult.data.reduce((sum, item) => {
        const amount =
          item?.mrr ??
          item?.monthly_amount ??
          item?.amount_cents / 100 ??
          item?.amount ??
          item?.price_cents / 100 ??
          0;
        return sum + (Number(amount) || 0);
      }, 0)
    : null;

  const opsQueue = operationsOverview?.queue || {};
  const opsWorker = operationsOverview?.worker || {};
  const opsSupabase = operationsOverview?.supabase || {};
  const lastActivity = opsWorker.last_heartbeat_at || latestHeartbeat?.created_at || recentQuotes[0]?.updated_at || null;
  const isWorkerOnline = lastActivity
    ? Date.now() - new Date(lastActivity).getTime() < 10 * 60 * 1000
    : false;

  const approvalPending = recentRequests.filter((request) => String(request.approval_status || "").toUpperCase() === "PENDING").length;
  const duplicatesFlagged = recentRequests.filter((request) => request.duplicate_of_request_id).length;
  const overdueSla = recentRequests.filter((request) => request.sla_due_at && new Date(request.sla_due_at).getTime() < Date.now() && request.status !== "DONE").length;
  const completedRequests = allRequests.filter((request) => String(request.status || "").toUpperCase() === "DONE").length;
  const quoteSuccessRate = quotesDoneResult.count || quotesErrorResult.count
    ? Math.round(((quotesDoneResult.count ?? 0) / Math.max((quotesDoneResult.count ?? 0) + (quotesErrorResult.count ?? 0), 1)) * 100)
    : null;
  const volumeByCompany = [...allRequests.reduce((accumulator, request) => {
    const key = request.company_id || "sem-company";
    const current = accumulator.get(key) || { company_id: key, requests: 0, done: 0 };
    current.requests += 1;
    if (String(request.status || "").toUpperCase() === "DONE") current.done += 1;
    accumulator.set(key, current);
    return accumulator;
  }, new Map()).values()]
    .sort((a, b) => b.requests - a.requests);
  const topCompany = volumeByCompany[0] || null;
  const topSupplier = [...suppliers]
    .sort((a, b) => (b.quote_participation_count || 0) - (a.quote_participation_count || 0))[0] || null;
  const highRiskCompanies = volumeByCompany.filter((company) => company.requests >= 3 && company.done / company.requests < 0.5).length;

  if (!companies.length && !recentRequests.length && !recentQuotes.length && !suppliers.length) {
    return getDemoAdminOverview();
  }

  return {
    metrics: {
      activeCompanies: activeCompanies.length,
      totalUsers: profiles.length,
      requestsToday: requestsTodayResult.count ?? 0,
      requestsMonth: requestsMonthResult.count ?? 0,
      quotesDone: quotesDoneResult.count ?? 0,
      quotesError: quotesErrorResult.count ?? 0,
      workerStatus: opsWorker.status ? String(opsWorker.status).replace(/^./, (char) => char.toUpperCase()) : isWorkerOnline ? "Online" : "Offline",
      averageResponseMinutes: opsQueue.average_quote_minutes_today ?? responseMinutes,
      estimatedRevenue,
      planCounts,
      pendingRequests: opsQueue.pending_requests ?? 0,
      processingRequests: opsQueue.processing_requests ?? 0,
      approvalPending,
      duplicatesFlagged,
      overdueSla,
      quoteSuccessRate,
      mappedSuppliers: suppliers.length,
      topCompanyVolume: topCompany ? `${topCompany.company_id} (${topCompany.requests})` : "-",
      topSupplier: topSupplier?.name || "-",
      completedRequests,
      highRiskCompanies
    },
    recentRequests: recentRequests.slice(0, 8),
    recentErrors: recentQuotes.filter((quote) => quote?.status === "ERROR").slice(0, 6),
    alerts: [
      ...(approvalPending ? [{ tone: "warning", title: "Aprovação pendente", message: `${approvalPending} pedido(s) aguardando aprovação.` }] : []),
      ...(overdueSla ? [{ tone: "warning", title: "SLA vencido", message: `${overdueSla} pedido(s) estao acima do SLA.` }] : []),
      ...(duplicatesFlagged ? [{ tone: "muted", title: "Duplicidade", message: `${duplicatesFlagged} pedido(s) marcados como possível duplicidade.` }] : []),
      ...(highRiskCompanies ? [{ tone: "warning", title: "Empresas em risco", message: `${highRiskCompanies} empresa(s) com alto volume e baixa taxa de conclusao recente.` }] : []),
      ...((opsWorker.status || "").toLowerCase() !== "online" ? [{ tone: "warning", title: "Worker offline", message: "O worker não reportou heartbeat recente." }] : [])
    ],
    searchIndex: {
      requests: recentRequests.map((request) => ({
        type: "request",
        id: request.id,
        label: request.request_code || request.id,
        subtitle: `${request.customer_name || "-"} | ${request.status || "-"}`,
      })),
      companies: companies.map((company) => ({
        type: "company",
        id: company.id,
        label: company.name,
        subtitle: `${company.plan || "Sem plano"} | ${company.status || "active"}`,
      })),
      users: profiles.slice(0, 50).map((profile) => ({
        type: "user",
        id: profile.id,
        label: profile.full_name || profile.company_name || profile.id,
        subtitle: `${profile.role || "member"} | ${profile.company_name || profile.company_id || "-"}`,
      })),
    },
    systemStatus: [
      {
        label: "API",
        value: operationsOverview?.api?.status === "online" ? "Respondendo" : "Sem telemetria",
        tone: operationsOverview?.api?.status === "online" ? "success" : "warning"
      },
      {
        label: "Supabase",
        value: opsSupabase.status === "healthy" ? "Conectado" : opsSupabase.status === "degraded" ? "Degradado" : "Conectado via fallback",
        tone: opsSupabase.status === "degraded" ? "warning" : "success"
      },
      {
        label: "Worker",
        value: opsWorker.last_heartbeat_status
          ? `${opsWorker.status || "offline"} | ultimo status ${opsWorker.last_heartbeat_status}`
          : isWorkerOnline
            ? "Respondendo"
            : "Sem heartbeat recente",
        tone: (opsWorker.status || "").toLowerCase() === "online" || isWorkerOnline ? "success" : "warning"
      },
      {
        label: "Fila",
        value: `${opsQueue.pending_requests ?? 0} pendente(s) / ${opsQueue.processing_requests ?? 0} em processamento`,
        tone: (opsQueue.pending_requests ?? 0) > 0 || (opsQueue.processing_requests ?? 0) > 0 ? "warning" : "success"
      },
      {
        label: "Billing",
        value: billingResult.data.length ? "Integrado" : "Modo demonstracao",
        tone: billingResult.data.length ? "success" : "muted"
      }
    ],
    notices: Array.from(notices)
  };
}
