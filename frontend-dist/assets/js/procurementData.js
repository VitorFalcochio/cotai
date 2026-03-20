import { collectNotice, safeQuery } from "./adminCommon.js";
import { getSession } from "./auth.js";
import { getDemoProcurementOverview } from "./demoData.js";

function normalizeText(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

function toNumber(value) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function toSlug(value) {
  return normalizeText(value).replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "item";
}

function supplierStatsFromReviews(reviews) {
  const ratings = reviews
    .flatMap((review) => [review.price_rating, review.delivery_rating, review.service_rating, review.reliability_rating])
    .map(toNumber)
    .filter((value) => value !== null);
  if (!ratings.length) return null;
  return ratings.reduce((sum, value) => sum + value, 0) / ratings.length;
}

function deriveRequestComparison(quoteResults) {
  const byRequest = new Map();
  quoteResults.forEach((row) => {
    const requestId = row.request_id;
    if (!requestId) return;
    const supplierName = row.supplier_name || row.supplier || row.source_name || "Fornecedor";
    const current = byRequest.get(requestId) || {
      suppliers: new Map(),
      bestPrice: null,
      worstPrice: null,
      bestDelivery: null
    };
    const supplier = current.suppliers.get(supplierName) || {
      supplier_id: row.supplier_id || null,
      supplier: supplierName,
      items: 0,
      totalPrice: 0,
      averageDeliveryDays: null,
      bestOverallCount: 0,
      priceEntries: 0
    };
    if (!supplier.supplier_id && row.supplier_id) {
      supplier.supplier_id = row.supplier_id;
    }
    const totalPrice = toNumber(row.total_price) ?? toNumber(row.price) ?? 0;
    supplier.items += 1;
    supplier.totalPrice += totalPrice;
    supplier.priceEntries += 1;
    const deliveryDays = toNumber(row.delivery_days);
    if (deliveryDays !== null) {
      supplier.averageDeliveryDays =
        supplier.averageDeliveryDays === null
          ? deliveryDays
          : (supplier.averageDeliveryDays + deliveryDays) / 2;
    }
    supplier.bestOverallCount += row.is_best_overall ? 1 : 0;
    current.suppliers.set(supplierName, supplier);
    current.bestPrice = current.bestPrice === null ? totalPrice : Math.min(current.bestPrice, totalPrice);
    current.worstPrice = current.worstPrice === null ? totalPrice : Math.max(current.worstPrice, totalPrice);
    if (deliveryDays !== null) {
      current.bestDelivery = current.bestDelivery === null ? deliveryDays : Math.min(current.bestDelivery, deliveryDays);
    }
    byRequest.set(requestId, current);
  });

  for (const [requestId, value] of byRequest.entries()) {
    const ranked = [...value.suppliers.values()].sort((a, b) => a.totalPrice - b.totalPrice || b.bestOverallCount - a.bestOverallCount);
    byRequest.set(requestId, {
      ...value,
      ranked,
      bestSupplier: ranked[0] || null,
      potentialSavings: value.bestPrice !== null && value.worstPrice !== null ? value.worstPrice - value.bestPrice : 0
    });
  }
  return byRequest;
}

function deriveFallbackSuppliers(quoteResults, requestsById) {
  const grouped = new Map();
  quoteResults.forEach((row) => {
    const supplierName = String(row.supplier_name || row.supplier || row.source_name || "").trim();
    if (!supplierName) return;
    const request = requestsById.get(row.request_id);
    const companyId = request?.company_id || null;
    const key = `${companyId || "global"}::${normalizeText(supplierName)}`;
    const current = grouped.get(key) || {
      id: `fallback-supplier-${toSlug(key)}`,
      company_id: companyId,
      name: supplierName,
      region: row.source_name || null,
      city: null,
      state: null,
      contact_name: null,
      contact_channel: null,
      material_tags: new Set(),
      average_delivery_days: null,
      average_rating: null,
      quote_participation_count: 0,
      average_price_score: null,
      status: "active",
      created_at: row.created_at || request?.created_at || new Date().toISOString(),
      updated_at: row.created_at || request?.updated_at || new Date().toISOString(),
      deliverySamples: [],
      valueSamples: []
    };

    current.quote_participation_count += 1;
    if (row.item_name) current.material_tags.add(String(row.item_name));

    const deliveryDays = toNumber(row.delivery_days);
    if (deliveryDays !== null) current.deliverySamples.push(deliveryDays);

    const valueScore = toNumber(row.value_score);
    if (valueScore !== null) current.valueSamples.push(valueScore);

    grouped.set(key, current);
  });

  return [...grouped.values()]
    .map((item) => ({
      ...item,
      material_tags: [...item.material_tags].slice(0, 8),
      average_delivery_days: item.deliverySamples.length
        ? Math.round(item.deliverySamples.reduce((sum, value) => sum + value, 0) / item.deliverySamples.length)
        : null,
      average_price_score: item.valueSamples.length
        ? Math.round((item.valueSamples.reduce((sum, value) => sum + value, 0) / item.valueSamples.length) * 100) / 100
        : null
    }))
    .sort((a, b) => (b.quote_participation_count || 0) - (a.quote_participation_count || 0));
}

function deriveFallbackPriceHistory(quoteResults, requestsById) {
  return quoteResults
    .filter((row) => row.item_name && (row.unit_price ?? row.price ?? row.total_price) !== null)
    .map((row, index) => {
      const request = requestsById.get(row.request_id);
      return {
        id: `fallback-price-history-${index + 1}`,
        request_id: row.request_id || null,
        request_quote_id: row.request_quote_id || null,
        supplier_id: row.supplier_id || null,
        supplier_name: row.supplier_name || row.supplier || row.source_name || "Fornecedor",
        item_name: row.item_name,
        source_name: row.source_name || row.origin_label || null,
        price: toNumber(row.price),
        unit_price: toNumber(row.unit_price ?? row.price),
        total_price: toNumber(row.total_price ?? row.price),
        captured_at: row.created_at || request?.updated_at || request?.created_at || new Date().toISOString()
      };
    });
}

function deriveFallbackProjects(requests) {
  const grouped = new Map();
  requests.forEach((request, index) => {
    const nameKey = normalizeText(request.customer_name || request.request_code);
    const locationKey = normalizeText(request.delivery_location);
    const key = request.project_id || (nameKey || locationKey ? `${nameKey}::${locationKey}` : `request-${request.id || index}`);
    const current = grouped.get(key) || {
      id: request.project_id || `fallback-project-${toSlug(key)}`,
      company_id: request.company_id || null,
      name: request.customer_name || request.request_code || `Projeto ${grouped.size + 1}`,
      location: request.delivery_location || null,
      stage: "planning",
      status: "active",
      notes: request.notes || null,
      created_by_user_id: null,
      created_at: request.created_at || new Date().toISOString(),
      updated_at: request.updated_at || request.created_at || new Date().toISOString()
    };
    if (!current.location && request.delivery_location) current.location = request.delivery_location;
    if (!current.notes && request.notes) current.notes = request.notes;
    grouped.set(key, current);
  });
  return [...grouped.values()];
}

function deriveFallbackProjectMaterials(requestItems, requests, projects) {
  const requestProjectMap = new Map();
  requests.forEach((request) => {
    const project = projects.find(
      (item) =>
        item.id === request.project_id ||
        (item.name === (request.customer_name || request.request_code || "") && item.location === (request.delivery_location || null))
    );
    if (project) {
      requestProjectMap.set(request.id, project.id);
    }
  });

  return requestItems.map((item, index) => ({
    id: `fallback-project-material-${index + 1}`,
    project_id: requestProjectMap.get(item.request_id) || `fallback-project-request-${item.request_id}`,
    request_id: item.request_id,
    material_name: item.item_name || item.description || "Material",
    category: null,
    estimated_qty: null,
    purchased_qty: null,
    pending_qty: null,
    status: "pending",
    created_at: item.created_at || new Date().toISOString(),
    updated_at: item.created_at || new Date().toISOString()
  }));
}

export async function fetchProcurementOverview() {
  const notices = new Set();
  const session = await getSession();
  const userId = session?.user?.id || "";

  const [
    requestsResult,
    requestItemsResult,
    quoteResultsResult,
    requestQuotesResult,
    suppliersResult,
    reviewsResult,
    priceHistoryResult,
    projectsResult,
    projectMaterialsResult,
    profilesResult
  ] = await Promise.all([
    safeQuery(
      (client) => client.from("requests").select("*").order("created_at", { ascending: false }).limit(200),
      { fallbackData: [], missingMessage: "Tabela requests ausente. Indicadores principais limitados." }
    ),
    safeQuery(
      (client) => client.from("request_items").select("*").limit(1000),
      { fallbackData: [], missingMessage: "Tabela request_items ausente. Inteligencia de materiais reduzida." }
    ),
    safeQuery(
      (client) => client.from("quote_results").select("*").limit(2000),
      { fallbackData: [], missingMessage: "Tabela quote_results ausente. Comparador e economia reduzidos." }
    ),
    safeQuery(
      (client) => client.from("request_quotes").select("*").order("created_at", { ascending: false }).limit(400),
      { fallbackData: [], missingMessage: "Tabela request_quotes ausente. Histórico de execução reduzido." }
    ),
    safeQuery(
      (client) => client.from("suppliers").select("*").order("quote_participation_count", { ascending: false }).limit(300),
      { fallbackData: [], missingMessage: "", permissionMessage: "", errorMessage: "" }
    ),
    safeQuery(
      (client) => client.from("supplier_reviews").select("*").order("created_at", { ascending: false }).limit(600),
      { fallbackData: [], missingMessage: "", permissionMessage: "", errorMessage: "" }
    ),
    safeQuery(
      (client) => client.from("price_history").select("*").order("captured_at", { ascending: false }).limit(2000),
      { fallbackData: [], missingMessage: "", permissionMessage: "", errorMessage: "" }
    ),
    safeQuery(
      (client) => client.from("projects").select("*").order("created_at", { ascending: false }).limit(200),
      { fallbackData: [], missingMessage: "", permissionMessage: "", errorMessage: "" }
    ),
    safeQuery(
      (client) => client.from("project_materials").select("*").limit(1000),
      { fallbackData: [], missingMessage: "", permissionMessage: "", errorMessage: "" }
    ),
    safeQuery(
      (client) => client.from("profiles").select("id, company_id, company_name, full_name").eq("id", userId).maybeSingle(),
      { fallbackData: null, missingMessage: "Perfil não encontrado para filtrar a empresa atual." }
    )
  ]);

  [
    requestsResult,
    requestItemsResult,
    quoteResultsResult,
    requestQuotesResult,
    suppliersResult,
    reviewsResult,
    priceHistoryResult,
    projectsResult,
    projectMaterialsResult,
    profilesResult
  ].forEach((result) => collectNotice(notices, result));

  const companyId = profilesResult.data?.company_id || null;
  const companyName = profilesResult.data?.company_name || "";
  const requests = companyId ? requestsResult.data.filter((row) => row.company_id === companyId) : requestsResult.data;
  const requestsById = new Map(requestsResult.data.map((row) => [row.id, row]));
  const requestIdSet = new Set(requests.map((row) => row.id));
  const requestItems = requestItemsResult.data.filter((row) => requestIdSet.has(row.request_id));
  const quoteResults = quoteResultsResult.data.filter((row) => requestIdSet.has(row.request_id));
  const requestQuotes = requestQuotesResult.data.filter((row) => requestIdSet.has(row.request_id));
  const fallbackSuppliers = deriveFallbackSuppliers(quoteResults, requestsById);
  const resolvedSuppliers = suppliersResult.data?.length ? suppliersResult.data : fallbackSuppliers;
  const suppliers = companyId ? resolvedSuppliers.filter((row) => row.company_id === companyId) : resolvedSuppliers;
  const supplierIdSet = new Set(suppliers.map((row) => row.id));
  const reviews = reviewsResult.data.filter((row) => supplierIdSet.has(row.supplier_id) || requestIdSet.has(row.request_id));
  const fallbackPriceHistory = deriveFallbackPriceHistory(quoteResults, requestsById);
  const resolvedPriceHistory = priceHistoryResult.data?.length ? priceHistoryResult.data : fallbackPriceHistory;
  const priceHistory = resolvedPriceHistory.filter((row) => requestIdSet.has(row.request_id));
  const fallbackProjects = deriveFallbackProjects(requests);
  const resolvedProjects = projectsResult.data?.length ? projectsResult.data : fallbackProjects;
  const projects = companyId ? resolvedProjects.filter((row) => row.company_id === companyId) : resolvedProjects;
  const projectIdSet = new Set(projects.map((row) => row.id));
  const fallbackProjectMaterials = deriveFallbackProjectMaterials(requestItems, requests, projects);
  const resolvedProjectMaterials = projectMaterialsResult.data?.length ? projectMaterialsResult.data : fallbackProjectMaterials;
  const projectMaterials = resolvedProjectMaterials.filter((row) => projectIdSet.has(row.project_id));

  const comparisonByRequest = deriveRequestComparison(quoteResults);
  const totalMaterialsQuoted = requestItems.length;
  const potentialSavings = [...comparisonByRequest.values()].reduce((sum, item) => sum + (item.potentialSavings || 0), 0);
  const completedQuotes = requestQuotes.filter((row) => row.status === "DONE");
  const timeSavedHours = Math.round((completedQuotes.length * 1.75 + totalMaterialsQuoted * 0.08) * 10) / 10;
  const suppliersConsulted = new Set(quoteResults.map((row) => row.supplier_name || row.supplier || row.source_name)).size;

  const supplierUsage = new Map();
  quoteResults.forEach((row) => {
    const supplier = row.supplier_name || row.supplier || row.source_name;
    if (!supplier) return;
    supplierUsage.set(supplier, (supplierUsage.get(supplier) || 0) + 1);
  });
  const bestRecurringSupplier = [...supplierUsage.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] || "-";

  const topMaterials = [...requestItems.reduce((accumulator, row) => {
    const key = row.item_name || row.description || "Material";
    accumulator.set(key, (accumulator.get(key) || 0) + 1);
    return accumulator;
  }, new Map()).entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6)
    .map(([name, count]) => ({ name, count }));

  const topSuppliers = suppliers
    .map((supplier) => {
      const supplierReviews = reviews.filter((review) => review.supplier_id === supplier.id);
      return {
        ...supplier,
        derived_rating: supplierStatsFromReviews(supplierReviews) ?? supplier.average_rating ?? null,
        review_count: supplierReviews.length
      };
    })
    .sort((a, b) => (b.quote_participation_count || 0) - (a.quote_participation_count || 0))
    .slice(0, 8);

  const companySummary = [...requests.reduce((accumulator, row) => {
    const key = row.company_id || "sem-company";
    const current = accumulator.get(key) || {
      company_id: key,
      requests: 0,
      done: 0,
      error: 0
    };
    current.requests += 1;
    if (String(row.status || "").toUpperCase() === "DONE") current.done += 1;
    if (String(row.status || "").toUpperCase() === "ERROR") current.error += 1;
    accumulator.set(key, current);
    return accumulator;
  }, new Map()).values()]
    .sort((a, b) => b.requests - a.requests);

  const requestsWithInsights = requests.map((request) => {
    const comparison = comparisonByRequest.get(request.id);
    const previousSimilar = requests.find(
      (candidate) =>
        candidate.id !== request.id &&
        normalizeText(candidate.delivery_location) === normalizeText(request.delivery_location) &&
        candidate.status === "DONE"
    );
    return {
      ...request,
      comparison,
      supplier_count: comparison?.ranked?.length || 0,
      best_supplier_name: comparison?.bestSupplier?.supplier || null,
      potential_savings: comparison?.potentialSavings || 0,
      previous_request_code: previousSimilar?.request_code || null
    };
  });

  const priceTrendByItem = [...priceHistory.reduce((accumulator, row) => {
    const itemName = row.item_name || "Material";
    const current = accumulator.get(itemName) || [];
    const price = toNumber(row.unit_price ?? row.price);
    if (price !== null) {
      current.push({ price, captured_at: row.captured_at });
    }
    accumulator.set(itemName, current);
    return accumulator;
  }, new Map()).entries()]
    .slice(0, 8)
    .map(([item_name, values]) => {
      const ordered = values.sort((a, b) => new Date(a.captured_at) - new Date(b.captured_at));
      const first = ordered[0]?.price ?? null;
      const last = ordered.at(-1)?.price ?? null;
      const delta = first !== null && last !== null ? last - first : null;
      return { item_name, points: ordered.slice(-6), first, last, delta };
    });

  if (!requests.length && !requestItems.length && !quoteResults.length && !projects.length) {
    return getDemoProcurementOverview();
  }

  return {
    companyId,
    companyName,
    requests: requestsWithInsights,
    requestItems,
    quoteResults,
    requestQuotes,
    suppliers: topSuppliers,
    supplierReviews: reviews,
    priceHistory,
    projects,
    projectMaterials,
    priceTrendByItem,
    topMaterials,
    companySummary,
    metrics: {
      totalRequests: requests.length,
      totalMaterialsQuoted,
      estimatedSavings: potentialSavings,
      estimatedTimeSavedHours: timeSavedHours,
      suppliersConsulted,
      bestRecurringSupplier,
      activeProjects: projects.filter((project) => String(project.status || "").toLowerCase() !== "archived").length,
      pendingMaterials: projectMaterials.filter((item) => String(item.status || "").toLowerCase() !== "purchased").length
    },
    notices: Array.from(notices)
  };
}
