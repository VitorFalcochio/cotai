export const PLAN_CATALOG = {
  silver: {
    key: "silver",
    label: "Prata",
    price: 89,
    requestLimit: 80,
    userLimit: 2,
    supplierLimit: 20,
    historyDays: 90,
    csvImportsPerMonth: 1,
    supportLevel: "Padrao",
    badge: "Entrada",
    badgeTone: "is-muted",
    description: "Essencial para comecar com mais controle sem elevar o custo da operacao.",
    ctaLabel: "Escolher Prata",
    features: [
      "80 pedidos por mes",
      "Ate 2 usuarios ativos",
      "Base com ate 20 fornecedores",
      "Historico de 90 dias",
      "1 importacao por mes"
    ]
  },
  gold: {
    key: "gold",
    label: "Ouro",
    price: 189,
    requestLimit: 300,
    userLimit: 5,
    supplierLimit: 80,
    historyDays: 365,
    csvImportsPerMonth: 12,
    supportLevel: "Prioritario",
    badge: "Mais escolhido",
    badgeTone: "is-success",
    description: "Plano principal para equipes que ja compram com recorrencia e precisam de velocidade.",
    ctaLabel: "Escolher Ouro",
    features: [
      "300 pedidos por mes",
      "Ate 5 usuarios ativos",
      "Base com ate 80 fornecedores",
      "Historico de 12 meses",
      "12 importacoes por mes"
    ]
  },
  diamond: {
    key: "diamond",
    label: "Diamante",
    price: 499,
    requestLimit: 2000,
    userLimit: 15,
    supplierLimit: 400,
    historyDays: null,
    csvImportsPerMonth: null,
    supportLevel: "Premium",
    badge: "Escala",
    badgeTone: "is-info",
    description: "Operacao madura com volume alto, mais governanca e mais gente comprando ao mesmo tempo.",
    ctaLabel: "Escolher Diamante",
    features: [
      "2.000 pedidos por mes",
      "Ate 15 usuarios ativos",
      "Base com ate 400 fornecedores",
      "Historico completo",
      "Importacoes ilimitadas"
    ]
  }
};

export const PLAN_ORDER = ["silver", "gold", "diamond"];

export function normalizePlanKey(value, fallback = "silver") {
  const normalized = String(value || "").trim().toLowerCase();
  if (normalized === "prata") return "silver";
  if (normalized === "ouro") return "gold";
  if (normalized === "diamante") return "diamond";
  return PLAN_CATALOG[normalized] ? normalized : fallback;
}

export function getPlanConfig(value) {
  return PLAN_CATALOG[normalizePlanKey(value)];
}

export function formatPlanLabel(value) {
  return getPlanConfig(value)?.label || String(value || "Sem plano");
}

export function getPlanPrice(value) {
  return Number(getPlanConfig(value)?.price || 0);
}
