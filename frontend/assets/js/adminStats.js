import {
  averageMinutes,
  collectNotice,
  deriveCompanies,
  formatPlanLabel,
  safeQuery,
  startOfMonthIso,
  startOfTodayIso
} from "./adminCommon.js";

export async function fetchAdminOverview() {
  const notices = new Set();
  const todayIso = startOfTodayIso();
  const monthIso = startOfMonthIso();

  const [
    companiesResult,
    profilesResult,
    requestsTodayResult,
    requestsMonthResult,
    requestsRecentResult,
    quotesDoneResult,
    quotesErrorResult,
    quotesRecentResult,
    heartbeatsResult,
    billingResult
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
          .select("id, request_code, customer_name, status, company_id, created_at, updated_at")
          .order("created_at", { ascending: false })
          .limit(8),
      { fallbackData: [], missingMessage: "Tabela requests ausente. Tabela de pedidos recentes em branco." }
    ),
    safeQuery(
      (client) =>
        client.from("request_quotes").select("id", { count: "exact", head: true }).eq("status", "DONE"),
      { fallbackData: null, missingMessage: "Tabela request_quotes ausente. Metricas de cotacao indisponiveis." }
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
      { fallbackData: [], missingMessage: "Tabela billing_subscriptions ausente. Receita exibida como TODO." }
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
    quotesDoneResult,
    quotesErrorResult,
    quotesRecentResult,
    heartbeatsResult,
    billingResult
  ].forEach((result) => collectNotice(notices, result));

  const profiles = profilesResult.data;
  const recentRequests = requestsRecentResult.data;
  const recentQuotes = quotesRecentResult.data;
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

  const lastActivity = latestHeartbeat?.created_at || recentQuotes[0]?.updated_at || null;
  const isWorkerOnline = lastActivity
    ? Date.now() - new Date(lastActivity).getTime() < 10 * 60 * 1000
    : false;

  return {
    metrics: {
      activeCompanies: activeCompanies.length,
      totalUsers: profiles.length,
      requestsToday: requestsTodayResult.count ?? 0,
      requestsMonth: requestsMonthResult.count ?? 0,
      quotesDone: quotesDoneResult.count ?? 0,
      quotesError: quotesErrorResult.count ?? 0,
      workerStatus: isWorkerOnline ? "Online" : "Offline",
      averageResponseMinutes: responseMinutes,
      estimatedRevenue,
      planCounts
    },
    recentRequests,
    recentErrors: recentQuotes.filter((quote) => quote?.status === "ERROR").slice(0, 6),
    systemStatus: [
      { label: "Supabase", value: "Conectado", tone: "success" },
      {
        label: "Worker",
        value: isWorkerOnline ? "Respondendo" : "Sem heartbeat recente",
        tone: isWorkerOnline ? "success" : "warning"
      },
      {
        label: "Billing",
        value: billingResult.data.length ? "Integrado" : "TODO / placeholder",
        tone: billingResult.data.length ? "success" : "muted"
      }
    ],
    notices: Array.from(notices)
  };
}
