const now = Date.now();

function isoOffset(hoursAgo = 0) {
  return new Date(now - hoursAgo * 60 * 60 * 1000).toISOString();
}

export function getDemoBillingPayload() {
  const subscriptions = [
    {
      id: "demo-billing-1",
      company: "Construtora Horizonte",
      plan: "Diamante",
      status: "active",
      amount: 499,
      updatedAt: isoOffset(6)
    },
    {
      id: "demo-billing-2",
      company: "Atlas Engenharia",
      plan: "Ouro",
      status: "active",
      amount: 189,
      updatedAt: isoOffset(28)
    },
    {
      id: "demo-billing-3",
      company: "Modulo Obras",
      plan: "Prata",
      status: "trial",
      amount: 89,
      updatedAt: isoOffset(54)
    }
  ];

  return {
    metrics: {
      mrr: subscriptions.reduce((sum, item) => sum + item.amount, 0),
      trials: 1,
      inactive: 0,
      upgrades: 1,
      downgrades: 0
    },
    planCounts: {
      prata: 1,
      ouro: 1,
      diamante: 1
    },
    subscriptions,
    notices: ["Modo demonstracao ativo no billing. Conecte billing_subscriptions para numeros reais."]
  };
}

export function getDemoWorkerPayload() {
  const recentExecutions = [
    {
      id: "rq-demo-104",
      request_id: "CT-1048",
      status: "DONE",
      started_at: isoOffset(1.6),
      finished_at: isoOffset(1.45),
      created_at: isoOffset(1.6),
      updated_at: isoOffset(1.45),
      error_message: null
    },
    {
      id: "rq-demo-103",
      request_id: "CT-1047",
      status: "DONE",
      started_at: isoOffset(3.2),
      finished_at: isoOffset(3.0),
      created_at: isoOffset(3.2),
      updated_at: isoOffset(3.0),
      error_message: null
    },
    {
      id: "rq-demo-102",
      request_id: "CT-1046",
      status: "ERROR",
      started_at: isoOffset(5.5),
      finished_at: isoOffset(5.3),
      created_at: isoOffset(5.5),
      updated_at: isoOffset(5.3),
      error_message: "Fornecedor sem cobertura para o item."
    },
    {
      id: "rq-demo-101",
      request_id: "CT-1045",
      status: "DONE",
      started_at: isoOffset(8.4),
      finished_at: isoOffset(8.1),
      created_at: isoOffset(8.4),
      updated_at: isoOffset(8.1),
      error_message: null
    }
  ];

  return {
    metrics: {
      workerStatus: "Online",
      lastHeartbeat: isoOffset(0.2),
      processedToday: 17,
      ignoredToday: 2,
      failureCount: 1,
      averageExecution: 2.4
    },
    recentExecutions,
    recentFailures: recentExecutions.filter((item) => item.status === "ERROR"),
    notices: ["Modo demonstracao ativo no worker. Conecte worker_heartbeats e request_quotes para telemetria real."]
  };
}

export function getDemoProcurementOverview() {
  const requests = [
    {
      id: "req-demo-1",
      request_code: "CT-1048",
      customer_name: "Obra Alto Padrão Norte",
      company_id: "company-demo-1",
      status: "DONE",
      created_at: isoOffset(4),
      best_supplier_name: "Obra Forte Distribuicao",
      potential_savings: 480
    },
    {
      id: "req-demo-2",
      request_code: "CT-1047",
      customer_name: "Residencial Aurora",
      company_id: "company-demo-1",
      status: "PROCESSING",
      created_at: isoOffset(9),
      best_supplier_name: "Deposito Horizonte",
      potential_savings: 230
    },
    {
      id: "req-demo-3",
      request_code: "CT-1046",
      customer_name: "Galpao Industrial Atlas",
      company_id: "company-demo-1",
      status: "DONE",
      created_at: isoOffset(27),
      best_supplier_name: "Construmax Regional",
      potential_savings: 620
    }
  ];

  const suppliers = [
    { id: "sup-demo-1", name: "Obra Forte Distribuicao", quote_participation_count: 14, derived_rating: 4.8 },
    { id: "sup-demo-2", name: "Deposito Horizonte", quote_participation_count: 11, derived_rating: 4.5 },
    { id: "sup-demo-3", name: "Construmax Regional", quote_participation_count: 9, derived_rating: 4.3 }
  ];

  const projects = [
    { id: "proj-demo-1", name: "Obra Alto Padrão Norte", location: "Sao Jose do Rio Preto", status: "active" },
    { id: "proj-demo-2", name: "Galpao Industrial Atlas", location: "Mirassol", status: "active" }
  ];

  const projectMaterials = [
    { id: "pm-demo-1", project_id: "proj-demo-1", status: "pending" },
    { id: "pm-demo-2", project_id: "proj-demo-1", status: "purchased" },
    { id: "pm-demo-3", project_id: "proj-demo-2", status: "pending" }
  ];

  return {
    companyId: "company-demo-1",
    companyName: "Construtora Horizonte",
    requests,
    requestItems: [],
    quoteResults: [],
    requestQuotes: [],
    suppliers,
    supplierReviews: [],
    priceHistory: [],
    projects,
    projectMaterials,
    priceTrendByItem: [],
    topMaterials: [
      { name: "Cimento CP-II 50kg", count: 12 },
      { name: "Vergalhao CA-50 10mm", count: 9 },
      { name: "Areia media", count: 7 },
      { name: "Brita 1", count: 5 }
    ],
    companySummary: [
      { company_id: "company-demo-1", requests: 27, done: 22, error: 1 }
    ],
    metrics: {
      totalRequests: 27,
      totalMaterialsQuoted: 94,
      estimatedSavings: 4830,
      estimatedTimeSavedHours: 21.5,
      suppliersConsulted: 18,
      bestRecurringSupplier: "Obra Forte Distribuicao",
      activeProjects: 2,
      pendingMaterials: 2
    },
    notices: ["Modo demonstracao ativo. Conecte as tabelas operacionais para ver dados reais da sua conta."]
  };
}

export function getDemoAdminOverview() {
  return {
    metrics: {
      activeCompanies: 6,
      totalUsers: 19,
      requestsToday: 12,
      requestsMonth: 184,
      quotesDone: 151,
      quotesError: 7,
      workerStatus: "Online",
      averageResponseMinutes: 7.4,
      estimatedRevenue: 1450,
      planCounts: { prata: 2, ouro: 3, diamante: 1 },
      pendingRequests: 3,
      processingRequests: 2,
      approvalPending: 4,
      duplicatesFlagged: 1,
      overdueSla: 1,
      quoteSuccessRate: 96,
      mappedSuppliers: 34,
      topCompanyVolume: "Construtora Horizonte (42)",
      topSupplier: "Obra Forte Distribuicao",
      completedRequests: 151,
      highRiskCompanies: 0
    },
    recentRequests: [
      { id: "req-demo-1", request_code: "CT-1048", customer_name: "Obra Alto Padrão Norte", status: "DONE", company_id: "Construtora Horizonte", created_at: isoOffset(4) },
      { id: "req-demo-2", request_code: "CT-1047", customer_name: "Residencial Aurora", status: "PROCESSING", company_id: "Atlas Engenharia", created_at: isoOffset(7) }
    ],
    recentErrors: [
      { request_id: "CT-1046", status: "ERROR", error_message: "Fornecedor sem cobertura para o item.", updated_at: isoOffset(5.3) }
    ],
    alerts: [
      { tone: "warning", title: "Aprovação pendente", message: "4 pedidos aguardando aprovação." },
      { tone: "muted", title: "Fila de processamento", message: "2 pedidos em processamento pelo worker." }
    ],
    searchIndex: {
      requests: [{ type: "request", id: "req-demo-1", label: "CT-1048", subtitle: "Obra Alto Padrão Norte | DONE" }],
      companies: [{ type: "company", id: "company-demo-1", label: "Construtora Horizonte", subtitle: "Diamante | active" }],
      users: [{ type: "user", id: "user-demo-1", label: "Felipe Santos", subtitle: "admin | Construtora Horizonte" }]
    },
    systemStatus: [
      { label: "API", value: "Respondendo", tone: "success" },
      { label: "Supabase", value: "Conectado", tone: "success" },
      { label: "Worker", value: "Respondendo", tone: "success" },
      { label: "Fila", value: "3 pendente(s) / 2 em processamento", tone: "warning" },
      { label: "Billing", value: "Modo demonstracao", tone: "muted" }
    ],
    notices: ["Modo demonstracao ativo no painel admin. Conecte todas as tabelas para visao operacional real."]
  };
}
