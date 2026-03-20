import { fetchProcurementOverview } from "../procurementData.js";
import { formatDateTime, setHTML, setText, showFeedback } from "../ui.js";

const LOCAL_MATERIALS_KEY = "cotai_materials";

function normalizeText(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

function readLocalMaterials() {
  try {
    const payload = window.localStorage.getItem(LOCAL_MATERIALS_KEY);
    const parsed = payload ? JSON.parse(payload) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch (_) {
    return [];
  }
}

async function loadJson(relativePath) {
  const response = await fetch(relativePath, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Nao foi possivel carregar ${relativePath}.`);
  }
  return response.json();
}

function summarizeProviders(rows) {
  const grouped = new Map();
  rows.forEach((row) => {
    const source = String(row.source_name || row.provider || row.supplier_name || "Origem local").trim();
    const current = grouped.get(source) || {
      name: source,
      count: 0,
      latest: null
    };
    current.count += 1;
    const capturedAt = row.captured_at || row.created_at || null;
    if (capturedAt && (!current.latest || new Date(capturedAt) > new Date(current.latest))) {
      current.latest = capturedAt;
    }
    grouped.set(source, current);
  });
  return [...grouped.values()].sort((left, right) => right.count - left.count || String(left.name).localeCompare(String(right.name)));
}

function renderProviderCards(providers) {
  if (!providers.length) {
    return `
      <article class="materials-source-card is-empty">
        <strong>Sem historico ainda</strong>
        <p>Assim que o coletor gravar snapshots ou a empresa concluir cotacoes, este painel passa a mostrar as fontes reais e a data da ultima captura.</p>
      </article>
    `;
  }

  return providers
    .slice(0, 6)
    .map((provider) => `
      <article class="materials-source-card">
        <div class="materials-source-card-head">
          <strong>${provider.name}</strong>
          <span class="app-badge is-muted">${provider.count} registro(s)</span>
        </div>
        <p>Ultima captura: ${provider.latest ? formatDateTime(provider.latest) : "sem data"}</p>
      </article>
    `)
    .join("");
}

function uniqueCount(values) {
  return new Set(values.filter(Boolean).map((value) => normalizeText(value))).size;
}

function buildFallbackInsights({ catalogRows, watchlistRows, localMaterials }) {
  const providerRows = watchlistRows.map((row) => ({
    source_name: row.source_name || row.provider || "Origem configurada",
    provider: row.provider || row.source_name || "manual",
    captured_at: null
  }));

  return {
    mode: "fallback",
    catalogCount: uniqueCount([
      ...catalogRows.map((row) => row.name || row.titulo),
      ...localMaterials.map((row) => row.name)
    ]),
    coveredCount: 0,
    sourceCount: uniqueCount(providerRows.map((row) => row.source_name || row.provider)),
    latestCapture: null,
    providers: summarizeProviders(providerRows),
    summary: "Painel em modo local. As fontes abaixo estao configuradas para coleta, mas ainda sem historico confirmado nesta empresa.",
    coverageNote: watchlistRows.length
      ? `Existem ${watchlistRows.length} consulta(s) monitorada(s) na watchlist, prontas para gerar snapshots.`
      : "Ainda nao ha watchlist configurada para alimentar a base automaticamente."
  };
}

function buildLiveInsights({ overview, catalogRows, localMaterials }) {
  const priceHistory = Array.isArray(overview?.priceHistory) ? overview.priceHistory : [];
  const providers = summarizeProviders(priceHistory);
  const latestCapture = [...priceHistory]
    .map((row) => row.captured_at || row.created_at || null)
    .filter(Boolean)
    .sort((left, right) => new Date(right) - new Date(left))[0] || null;

  return {
    mode: "live",
    catalogCount: uniqueCount([
      ...catalogRows.map((row) => row.name || row.titulo),
      ...localMaterials.map((row) => row.name)
    ]),
    coveredCount: uniqueCount(priceHistory.map((row) => row.item_name)),
    sourceCount: uniqueCount(priceHistory.map((row) => row.source_name || row.provider || row.supplier_name)),
    latestCapture,
    providers,
    summary: providers.length
      ? `Base conectada com historico real de precos. As principais fontes abaixo mostram volume de referencias e a captura mais recente.`
      : "A base conectou, mas ainda nao existem registros de historico suficientes para este painel.",
    coverageNote: priceHistory.length
      ? `${uniqueCount(priceHistory.map((row) => row.item_name))} material(is) ja possuem historico de preco na empresa atual.`
      : "Ainda nao existe historico de preco suficiente para cruzar com a base de materiais."
  };
}

function renderInsights(insights) {
  setText("#materialsMetricCatalog", String(insights.catalogCount || 0));
  setText("#materialsMetricCovered", String(insights.coveredCount || 0));
  setText("#materialsMetricSources", String(insights.sourceCount || 0));
  setText("#materialsMetricLatest", insights.latestCapture ? formatDateTime(insights.latestCapture) : "-");
  setText("#materialsInsightsSummary", insights.summary);
  setText("#materialsCoverageNote", insights.coverageNote);
  setText("#materialsInsightsBadge", insights.mode === "live" ? "Base conectada" : "Painel local");
  setHTML("#materialsSourceList", renderProviderCards(insights.providers));
}

async function init() {
  if (document.body.dataset.page !== "materials") return;

  const localMaterials = readLocalMaterials();
  const [catalogRows, watchlistRows] = await Promise.all([
    loadJson("../../../../data/catalog.json").catch(() => []),
    loadJson("../../../../data/price_sources.json").catch(() => [])
  ]);

  try {
    const overview = await fetchProcurementOverview();
    renderInsights(buildLiveInsights({ overview, catalogRows, localMaterials }));
  } catch (error) {
    renderInsights(buildFallbackInsights({ catalogRows, watchlistRows, localMaterials }));
    showFeedback("#materialsInsightsFeedback", error.message || "Painel usando fallback local por enquanto.");
  }
}

init().catch((error) => {
  showFeedback("#materialsInsightsFeedback", error.message || "Nao foi possivel carregar o painel de materiais.");
  const fallback = buildFallbackInsights({ catalogRows: [], watchlistRows: [], localMaterials: readLocalMaterials() });
  renderInsights(fallback);
});
