import { formatCurrencyBRL } from "../adminCommon.js";
import { bootClientWorkspace } from "../clientPage.js";
import { fetchProcurementOverview } from "../procurementData.js";
import { runPageBoot, setHTML, setText, showFeedback } from "../ui.js";

function topEntries(items, formatter) {
  if (!items.length) {
    return '<article class="admin-status-row"><div><p>Sem dados</p><strong>Os indicadores aparecem conforme o uso do sistema.</strong></div><span class="app-badge is-muted">INFO</span></article>';
  }
  return items.map(formatter).join("");
}

async function init() {
  const boot = await bootClientWorkspace();
  if (!boot) return;

  try {
    const overview = await fetchProcurementOverview();
    const topMaterials = overview.topMaterials.slice(0, 5);
    const topSuppliers = overview.suppliers.slice(0, 5);

    setText("#analyticsTitle", `Analytics de ${overview.companyName || boot.companyLabel}`);
    setText("#analyticsSavings", formatCurrencyBRL(overview.metrics.estimatedSavings));
    setText("#analyticsTime", `${overview.metrics.estimatedTimeSavedHours}h`);
    setText("#analyticsSuppliers", String(overview.metrics.suppliersConsulted));
    setText("#analyticsMaterials", String(overview.metrics.totalMaterialsQuoted));

    setHTML(
      "#analyticsTopMaterials",
      topEntries(
        topMaterials,
        (item) => `
          <article class="admin-status-row">
            <div>
              <p>Material</p>
              <strong>${item.name}</strong>
            </div>
            <span class="app-badge is-info">${item.count} cotacoes</span>
          </article>
        `
      )
    );

    setHTML(
      "#analyticsTopSuppliers",
      topEntries(
        topSuppliers,
        (supplier) => `
          <article class="admin-status-row">
            <div>
              <p>Fornecedor</p>
              <strong>${supplier.name}</strong>
            </div>
            <span class="app-badge is-success">${supplier.quote_participation_count || 0} cotacoes</span>
          </article>
        `
      )
    );
  } catch (error) {
    showFeedback("#analyticsFeedback", error.message || "Nao foi possivel carregar analytics.");
  }
}

runPageBoot(init, { loadingMessage: "Montando analytics operacional." });
