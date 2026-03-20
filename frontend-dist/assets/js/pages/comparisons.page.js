import { bootClientWorkspace } from "../clientPage.js";
import { fetchProcurementOverview } from "../procurementData.js";
import { formatCurrencyBRL } from "../adminCommon.js";
import { runPageBoot, setHTML, setText, showFeedback } from "../ui.js";

function renderCards(rows) {
  if (!rows.length) {
    return '<article class="entity-list-item"><div class="entity-list-copy"><p>Sem comparativos</p><strong>Os comparativos aparecem quando houver multiplos fornecedores por pedido.</strong></div><span class="app-badge is-muted">INFO</span></article>';
  }

  return rows
    .map(
      (row) => `
        <article class="card table-shell">
          <div class="filter-shell-head">
            <div>
              <p class="eyebrow">${row.request_code || "Pedido"}</p>
              <h2>${row.customer_name || "Comparativo"}</h2>
            </div>
            <span class="app-badge is-success">${formatCurrencyBRL(row.potential_savings || 0)} de economia</span>
          </div>
          <div class="entity-list">
            ${row.comparison.ranked.slice(0, 3).map((supplier, index) => `
              <article class="entity-list-item">
                <div class="entity-list-copy">
                  <p>${index === 0 ? "Melhor opcao" : "Alternativa"}</p>
                  <strong>${supplier.supplier}</strong>
                </div>
                <span class="app-badge ${index === 0 ? "is-success" : "is-info"}">${formatCurrencyBRL(supplier.totalPrice || 0)}</span>
              </article>
            `).join("")}
          </div>
        </article>
      `
    )
    .join("");
}

async function init() {
  const boot = await bootClientWorkspace();
  if (!boot) return;

  try {
    const overview = await fetchProcurementOverview();
    const rows = overview.requests
      .filter((request) => request.comparison?.ranked?.length)
      .sort((a, b) => (Number(b.potential_savings) || 0) - (Number(a.potential_savings) || 0))
      .slice(0, 6);

    setText("#comparisonsTitle", `Comparativos de ${overview.companyName || boot.companyLabel}`);
    setText("#comparisonsCount", String(rows.length));
    setHTML("#comparisonsGrid", renderCards(rows));
  } catch (error) {
    showFeedback("#comparisonsFeedback", error.message || "Nao foi possivel carregar comparativos.");
  }
}

runPageBoot(init, { loadingMessage: "Montando comparativos de fornecedores." });
