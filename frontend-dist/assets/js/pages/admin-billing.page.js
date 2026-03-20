import { fetchAdminBilling } from "../adminBilling.js";
import { bootAdminPage, runAdminPageBoot } from "../adminPage.js";
import { formatCurrencyBRL } from "../adminCommon.js";
import { formatDateTime, setHTML, setText, showFeedback } from "../ui.js";

function renderRows(rows) {
  if (!rows.length) {
    return '<tr><td colspan="5" class="app-empty">Nenhuma assinatura real encontrada. Exibindo modo de demonstração ou aguardando integração financeira.</td></tr>';
  }

  return rows
    .map(
      (row) => `
        <tr>
          <td>${row.company}</td>
          <td>${row.plan}</td>
          <td>${row.status}</td>
          <td>${formatCurrencyBRL(row.amount)}</td>
          <td>${formatDateTime(row.updatedAt)}</td>
        </tr>
      `
    )
    .join("");
}

async function init() {
  await bootAdminPage();

  try {
    const payload = await fetchAdminBilling();
    setText("#billingMrr", formatCurrencyBRL(payload.metrics.mrr));
    setText("#billingTrials", String(payload.metrics.trials));
    setText("#billingInactive", String(payload.metrics.inactive));
    setText("#billingUpgrades", String(payload.metrics.upgrades));
    setText("#billingDowngrades", String(payload.metrics.downgrades));
    setText("#billingPlanSilver", String(payload.planCounts.prata));
    setText("#billingPlanGold", String(payload.planCounts.ouro));
    setText("#billingPlanDiamond", String(payload.planCounts.diamante));

    setHTML("#adminBillingBody", renderRows(payload.subscriptions));
    if (payload.notices.length) {
      showFeedback("#adminBillingFeedback", payload.notices.join(" "));
    }
  } catch (error) {
    showFeedback("#adminBillingFeedback", error.message || "Não foi possível carregar a área de receita.");
  }
}

runAdminPageBoot(init, "Carregando billing e assinatura.").catch((error) => {
  showFeedback("#adminBillingFeedback", error.message || "Erro ao iniciar a página financeira.");
});
