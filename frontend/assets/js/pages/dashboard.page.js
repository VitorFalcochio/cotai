import { LOGIN_PATH } from "../config.js";
import { getAdminProfile, getCompanyDisplayName, requireAuth, signOut } from "../auth.js";
import { fetchProcurementOverview } from "../procurementData.js";
import { formatCurrencyBRL } from "../adminCommon.js";
import { formatDateTime, initSidebar, qs, runPageBoot, setHTML, setText, showFeedback } from "../ui.js";
import { showAdminShortcut } from "../adminPage.js";

function renderRecentRows(rows) {
  if (!rows.length) {
    return '<tr><td colspan="5" class="app-empty">Nenhum pedido ainda.</td></tr>';
  }

  return rows
    .map(
      (row) => `
        <tr>
          <td>${row.request_code || row.id}</td>
          <td>${row.status}</td>
          <td>${row.best_supplier_name || "-"}</td>
          <td>${formatCurrencyBRL(row.potential_savings || 0)}</td>
          <td>${formatDateTime(row.created_at)}</td>
        </tr>
      `
    )
    .join("");
}

function renderStack(items, formatter) {
  if (!items.length) {
    return '<article class="admin-status-row"><div><p>Sem dados</p><strong>Os dados aparecerão conforme o uso da plataforma.</strong></div><span class="app-badge is-muted">INFO</span></article>';
  }
  return items.map(formatter).join("");
}

async function init() {
  const session = await requireAuth(LOGIN_PATH);
  if (!session) return;

  initSidebar();
  setText("#companyName", getCompanyDisplayName(session.user));

  qs("#logoutButton")?.addEventListener("click", async () => {
    await signOut();
    window.location.replace(LOGIN_PATH);
  });

  try {
    const adminProfile = await getAdminProfile(session.user.id);
    showAdminShortcut(adminProfile);
  } catch (_) {
    showAdminShortcut(null);
  }

  try {
    const overview = await fetchProcurementOverview();
    setText("#metricRequests", String(overview.metrics.totalRequests));
    setText("#metricMaterialsQuoted", String(overview.metrics.totalMaterialsQuoted));
    setText("#metricSavings", formatCurrencyBRL(overview.metrics.estimatedSavings));
    setText("#metricTimeSaved", `${overview.metrics.estimatedTimeSavedHours}h`);
    setText("#metricSuppliersConsulted", String(overview.metrics.suppliersConsulted));
    setText("#metricBestSupplier", overview.metrics.bestRecurringSupplier || "-");
    setText("#metricProjects", String(overview.metrics.activeProjects));
    setText("#metricPendingMaterials", String(overview.metrics.pendingMaterials));
    setHTML("#dashboardRecentBody", renderRecentRows(overview.requests.slice(0, 6)));
    setHTML(
      "#dashboardInsights",
      renderStack(overview.topMaterials.slice(0, 5), (item) => `
        <article class="admin-status-row">
          <div><p>${item.name}</p><strong>${item.count} cotações</strong></div>
          <span class="app-badge is-muted">MATERIAL</span>
        </article>
      `)
    );
    setHTML(
      "#dashboardSuppliers",
      renderStack(overview.suppliers.slice(0, 5), (supplier) => `
        <article class="admin-status-row">
          <div><p>${supplier.name}</p><strong>${supplier.quote_participation_count || 0} participações</strong></div>
          <span class="app-badge ${supplier.derived_rating && supplier.derived_rating >= 4 ? "is-success" : "is-muted"}">
            ${supplier.derived_rating ? `${supplier.derived_rating.toFixed(1)} / 5` : "Sem review"}
          </span>
        </article>
      `)
    );
    setHTML(
      "#dashboardProjects",
      renderStack(overview.projects.slice(0, 5), (project) => {
        const pendingCount = overview.projectMaterials.filter((item) => item.project_id === project.id && String(item.status || "").toLowerCase() !== "purchased").length;
        return `
          <article class="admin-status-row">
            <div><p>${project.name}</p><strong>${project.location || "Sem local definido"}</strong></div>
            <span class="app-badge ${pendingCount ? "is-warning" : "is-success"}">${pendingCount} pendencia(s)</span>
          </article>
        `;
      })
    );

    if (overview.notices.length) {
      showFeedback("#dashboardFeedback", "Alguns indicadores estão em modo de demonstração até a integração completa do ambiente.", false);
    }
  } catch (error) {
    showFeedback("#dashboardFeedback", error.message || "Não foi possível carregar o dashboard.");
    setHTML("#dashboardRecentBody", '<tr><td colspan="5" class="app-empty">Erro ao carregar pedidos.</td></tr>');
  }
}

runPageBoot(init, { loadingMessage: "Montando dashboard e sincronizando indicadores." }).catch((error) => {
  showFeedback("#dashboardFeedback", error.message || "Erro ao iniciar o dashboard.");
});
