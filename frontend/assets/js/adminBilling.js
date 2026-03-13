import { collectNotice, deriveCompanies, formatPlanLabel, safeQuery } from "./adminCommon.js";
import { getDemoBillingPayload } from "./demoData.js";

export async function fetchAdminBilling() {
  const notices = new Set();
  const [billingResult, companiesResult, profilesResult] = await Promise.all([
    safeQuery(
      (client) =>
        client
          .from("billing_subscriptions")
          .select("*")
          .order("created_at", { ascending: false }),
      { fallbackData: [], missingMessage: "Tabela billing_subscriptions ausente. Cards exibidos em modo demonstracao." }
    ),
    safeQuery(
      (client) => client.from("companies").select("id, name, plan, status"),
      { fallbackData: [], missingMessage: "Tabela companies ausente. Billing vai usar fallback baseado em profiles." }
    ),
    safeQuery(
      (client) => client.from("profiles").select("id, company_id, full_name, company_name, status, plan, created_at"),
      { fallbackData: [], missingMessage: "Tabela profiles ausente. Distribuicao por plano indisponivel." }
    )
  ]);

  collectNotice(notices, billingResult);
  collectNotice(notices, profilesResult);

  const derivedCompanies = deriveCompanies({
    companies: companiesResult.data,
    profiles: profilesResult.data,
    requests: []
  });

  if (derivedCompanies.length === 0 || companiesResult.status !== "missing") {
    collectNotice(notices, companiesResult);
  }

  if (!billingResult.data.length) {
    if (!derivedCompanies.length) {
      return getDemoBillingPayload();
    }

    const planCounts = derivedCompanies.reduce(
      (accumulator, company) => {
        const plan = formatPlanLabel(company?.plan).toLowerCase();
        if (plan.includes("prata")) accumulator.prata += 1;
        else if (plan.includes("ouro")) accumulator.ouro += 1;
        else if (plan.includes("diamante")) accumulator.diamante += 1;
        return accumulator;
      },
      { prata: 0, ouro: 0, diamante: 0 }
    );

    return {
      metrics: {
        mrr: 0,
        trials: 0,
        inactive: derivedCompanies.filter((company) => String(company?.status).toLowerCase() === "inactive").length,
        upgrades: 0,
        downgrades: 0
      },
      planCounts,
      subscriptions: derivedCompanies.map((company) => ({
        id: company.id,
        company: company.name,
        plan: formatPlanLabel(company.plan),
        status: company.status || "active",
        amount: 0,
        updatedAt: company.created_at || null
      })),
      notices: ["Billing em modo simplificado. Conecte billing_subscriptions para MRR e movimentacoes reais."]
    };
  }

  const subscriptions = billingResult.data.map((item) => ({
    id: item.id,
    company: item.company_name || item.customer_name || item.company_id || "-",
    plan: formatPlanLabel(item.plan),
    status: item.status || "active",
    amount:
      item.mrr ??
      item.monthly_amount ??
      item.amount_cents / 100 ??
      item.amount ??
      item.price_cents / 100 ??
      0,
    updatedAt: item.updated_at || item.created_at || null
  }));

  const planCounts = subscriptions.reduce(
    (accumulator, item) => {
      const plan = String(item.plan).toLowerCase();
      if (plan.includes("prata")) accumulator.prata += 1;
      else if (plan.includes("ouro")) accumulator.ouro += 1;
      else if (plan.includes("diamante")) accumulator.diamante += 1;
      return accumulator;
    },
    { prata: 0, ouro: 0, diamante: 0 }
  );

  return {
    metrics: {
      mrr: subscriptions.reduce((sum, item) => sum + (Number(item.amount) || 0), 0),
      trials: subscriptions.filter((item) => String(item.status).toLowerCase().includes("trial")).length,
      inactive: subscriptions.filter((item) => String(item.status).toLowerCase() === "inactive").length,
      upgrades: subscriptions.filter((item) => String(item.status).toLowerCase().includes("upgrade")).length,
      downgrades: subscriptions.filter((item) => String(item.status).toLowerCase().includes("downgrade")).length
    },
    planCounts,
    subscriptions,
    notices: Array.from(notices)
  };
}
