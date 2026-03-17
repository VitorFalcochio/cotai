import { bootClientWorkspace } from "../clientPage.js";
import { fetchProcurementOverview } from "../procurementData.js";
import { formatCurrencyBRL } from "../adminCommon.js";
import { formatDateTime, runPageBoot, setHTML, setText, showFeedback } from "../ui.js";

function renderRows(rows) {
  if (!rows.length) {
    return '<tr><td colspan="5" class="app-empty">Ainda nao ha historico de precos suficiente.</td></tr>';
  }

  return rows.map((row) => `
    <tr>
      <td><strong>${row.item_name}</strong></td>
      <td>${row.supplier_name || "-"}</td>
      <td>${formatCurrencyBRL(row.unit_price || row.price || 0)}</td>
      <td>${formatCurrencyBRL(row.total_price || row.price || 0)}</td>
      <td>${formatDateTime(row.captured_at)}</td>
    </tr>
  `).join("");
}

async function init() {
  const boot = await bootClientWorkspace();
  if (!boot) return;

  try {
    const overview = await fetchProcurementOverview();
    const rows = [...overview.priceHistory]
      .sort((a, b) => new Date(b.captured_at || 0) - new Date(a.captured_at || 0))
      .slice(0, 20);

    setText("#priceBookTitle", `Tabela de precos de ${overview.companyName || boot.companyLabel}`);
    setText("#priceBookCount", String(rows.length));
    setHTML("#priceBookTableBody", renderRows(rows));
  } catch (error) {
    showFeedback("#priceBookFeedback", error.message || "Nao foi possivel carregar tabela de precos.");
  }
}

runPageBoot(init, { loadingMessage: "Lendo historico de precos." });
