import { LOGIN_PATH } from "../config.js";
import { handleSessionExpired, isSessionExpiredError, requireAuth, signOut } from "../auth.js";
import { listProjects } from "../chatApi.js";
import { initSidebar, qs, runPageBoot, setHTML, setText, showFeedback } from "../ui.js";

let projectRows = [];
let visibleRows = [];

function handlePageError(error, fallback = "Nao foi possivel carregar os projetos.") {
  if (isSessionExpiredError(error)) {
    showFeedback("#projectsFeedback", "Sua sessao expirou. Redirecionando para o login.");
    window.setTimeout(() => handleSessionExpired(LOGIN_PATH), 350);
    return true;
  }
  showFeedback("#projectsFeedback", error.message || fallback);
  return false;
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function parseCurrencyToNumber(value) {
  const normalized = String(value || "").replace(/[^\d,.-]/g, "").replace(/\./g, "").replace(",", ".");
  const number = Number(normalized);
  return Number.isFinite(number) ? number : 0;
}

function formatCurrencyBRL(value) {
  const amount = Number(value || 0);
  return amount.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function toDisplayLabel(value, fallback) {
  const normalized = String(value || "").trim();
  if (!normalized) return fallback;
  return normalized
    .replaceAll("_", " ")
    .replace(/\s+/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function getStatusTone(value) {
  const normalized = String(value || "").trim().toLowerCase();
  if (["active", "in_progress", "ongoing", "em andamento"].includes(normalized)) return "is-active";
  if (["done", "completed", "complete", "finished", "concluido"].includes(normalized)) return "is-done";
  if (["paused", "pending", "planning", "draft", "planejamento"].includes(normalized)) return "is-pending";
  return "";
}

function getStatusLabel(row) {
  return toDisplayLabel(row.status_label || row.status || row.current_phase_label, "Planejamento");
}

function getProjectMetaLine(project) {
  const parts = [
    project.location_label || "Local a definir",
    project.area_label || "Area pendente",
    project.current_phase_label || "Planejamento",
  ].filter(Boolean);
  return parts.join(" - ");
}

function getSearchText(row) {
  return [
    row.name,
    row.project_label,
    row.location_label,
    row.area_label,
    row.current_phase_label,
    row.status,
    row.estimated_total_display,
  ].join(" ").toLowerCase();
}

function renderAction(row) {
  if (!row.source_thread_id) {
    return '<span class="projects-action-link is-disabled">Sem conversa</span>';
  }

  return `
    <a class="projects-action-link" href="new-request.html" data-thread-id="${escapeHtml(row.source_thread_id)}">
      <i class="bx bx-message-square-detail" aria-hidden="true"></i>
      <span>Abrir conversa</span>
    </a>
  `;
}

function renderEmptyTableRow(title, message) {
  return `
    <tr>
      <td colspan="6" class="projects-empty-cell">
        <strong>${escapeHtml(title)}</strong><br />
        <span>${escapeHtml(message)}</span>
      </td>
    </tr>
  `;
}

function renderProjectList(rows) {
  if (!rows.length) {
    return renderEmptyTableRow("Nenhum projeto encontrado", "Salve um projeto no chat da Cota ou ajuste o filtro para encontrar uma obra.");
  }

  return rows.map((row, index) => {
    const statusLabel = getStatusLabel(row);
    const statusTone = getStatusTone(row.status || row.current_phase_label);
    const summaryLine = `${Number(row.material_count || 0)} materiais - ${Number(row.request_count || 0)} pedidos`;
    const costLabel = row.estimated_total_display || "Sem custo consolidado";

    return `
      <tr>
        <td class="projects-col-index">${index + 1}</td>
        <td>
          <div class="projects-name-cell">
            <strong>${escapeHtml(row.name || "Projeto sem nome")}</strong>
            <span>${escapeHtml(row.project_label || "Projeto salvo no chat")}</span>
          </div>
        </td>
        <td class="projects-inline-meta">${escapeHtml(getProjectMetaLine(row))}<br />${escapeHtml(summaryLine)}</td>
        <td>${escapeHtml(costLabel)}</td>
        <td class="projects-col-status"><span class="projects-status-pill ${statusTone}">${escapeHtml(statusLabel)}</span></td>
        <td class="projects-col-action">${renderAction(row)}</td>
      </tr>
    `;
  }).join("");
}

function updateVisibleCount() {
  setText("#projectsVisibleCount", String(visibleRows.length));
}

function renderVisibleProjects() {
  setHTML("#projectsList", renderProjectList(visibleRows));
  updateVisibleCount();
}

function applyFilter() {
  const query = String(qs("#projectsSearch")?.value || "").trim().toLowerCase();
  visibleRows = query
    ? projectRows.filter((row) => getSearchText(row).includes(query))
    : [...projectRows];

  renderVisibleProjects();
}

async function init() {
  initSidebar();
  const session = await requireAuth(LOGIN_PATH);
  if (!session) return;

  qs("#logoutButton")?.addEventListener("click", async () => {
    await signOut();
    window.location.replace(LOGIN_PATH);
  });

  const payload = await listProjects();
  projectRows = Array.isArray(payload.projects) ? payload.projects : [];
  visibleRows = [...projectRows];

  setText("#projectsMetricTotal", String(projectRows.length));
  setText("#projectsMetricMaterials", String(projectRows.reduce((sum, row) => sum + Number(row.material_count || 0), 0)));
  setText("#projectsMetricCost", formatCurrencyBRL(projectRows.reduce((sum, row) => sum + parseCurrencyToNumber(row.estimated_total_display), 0)));
  setText(
    "#projectsMetricActive",
    String(
      projectRows.filter((row) => {
        const normalized = String(row.status || row.current_phase_label || "").trim().toLowerCase();
        return ["active", "in_progress", "ongoing", "planning", "planejamento", "em andamento"].includes(normalized);
      }).length
    )
  );

  renderVisibleProjects();

  qs("#projectsSearch")?.addEventListener("input", () => {
    applyFilter();
  });

  qs("#projectsList")?.addEventListener("click", (event) => {
    const actionLink = event.target.closest("[data-thread-id]");
    if (!actionLink) return;
    sessionStorage.setItem("cotai_active_chat_thread", actionLink.dataset.threadId || "");
  });
}

runPageBoot(init, { loadingMessage: "Carregando projetos salvos pela Cota." }).catch((error) => {
  handlePageError(error, "Nao foi possivel iniciar a tela de projetos.");
});
