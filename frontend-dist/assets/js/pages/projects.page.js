import { LOGIN_PATH } from "../config.js";
import { handleSessionExpired, isSessionExpiredError, requireAuth, signOut } from "../auth.js";
import { getProject, listProjects } from "../chatApi.js";
import { formatDateTime, initSidebar, qs, runPageBoot, setHTML, setText, showFeedback } from "../ui.js";

let projectRows = [];
let selectedProjectId = "";

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

function renderProjectList(rows) {
  if (!rows.length) {
    return '<article class="entity-list-item"><div class="entity-list-copy"><p>Nenhum projeto salvo</p><strong>Salve um projeto no chat da Cota para ele aparecer aqui.</strong></div><span class="app-badge is-muted">INFO</span></article>';
  }

  return rows.map((row) => `
    <article class="entity-list-item ${selectedProjectId === row.id ? "is-selected" : ""}" data-project-id="${row.id}">
      <div class="entity-list-copy">
        <p>${escapeHtml(row.project_label || "Obra")}</p>
        <strong>${escapeHtml(row.name || "Projeto sem nome")}</strong>
        <span>${escapeHtml(row.location_label || "-")} · ${escapeHtml(row.area_label || "Pendente")} · ${escapeHtml(row.current_phase_label || "Planejamento")}</span>
      </div>
      <div class="table-entity-meta">
        <strong>${escapeHtml(row.estimated_total_display || "Sem custo consolidado")}</strong>
        <small>${row.material_count || 0} material(is) · ${row.request_count || 0} pedido(s)</small>
      </div>
    </article>
  `).join("");
}

function renderProjectSummary(project) {
  return [
    { label: "Tipo", value: project.project_label || project.project_type || "Obra" },
    { label: "Area", value: project.area_label || "Pendente" },
    { label: "Fase atual", value: project.current_phase_label || "Planejamento" },
    { label: "Custo salvo", value: project.estimated_total_display || "Sem custo consolidado" },
    { label: "Pedidos", value: String(project.request_count || 0) },
    { label: "Materiais", value: String(project.material_count || 0) },
  ].map((item) => `<article class="comparison-summary-card"><span>${escapeHtml(item.label)}</span><strong>${escapeHtml(item.value)}</strong></article>`).join("");
}

function renderTimeline(events) {
  if (!events?.length) {
    return '<article class="entity-list-item"><div class="entity-list-copy"><p>Sem eventos ainda</p><strong>O historico operacional vai aparecer aqui conforme a obra evoluir.</strong></div><span class="app-badge is-muted">INFO</span></article>';
  }
  return events.slice(0, 8).map((event) => `
    <article class="entity-list-item">
      <div class="entity-list-copy">
        <p>${escapeHtml(event.event_type || "evento")}</p>
        <strong>${escapeHtml(event.note || event.stage_label || event.material_name || "Atualizacao registrada")}</strong>
        <span>${formatDateTime(event.created_at)}${event.supplier_name ? ` · ${escapeHtml(event.supplier_name)}` : ""}</span>
      </div>
      <span class="app-badge ${event.impact_level === "warning" ? "is-warning" : event.impact_level === "success" ? "is-success" : "is-muted"}">${escapeHtml(event.impact_level || "info")}</span>
    </article>
  `).join("");
}

function renderMaterials(materials) {
  if (!materials?.length) {
    return '<article class="entity-list-item"><div class="entity-list-copy"><p>Sem materiais</p><strong>A lista de materiais vai aparecer aqui quando a Cota montar ou atualizar a obra.</strong></div><span class="app-badge is-muted">INFO</span></article>';
  }
  return materials.slice(0, 12).map((item) => `
    <article class="entity-list-item">
      <div class="entity-list-copy">
        <p>${escapeHtml(item.status || "pendente")}</p>
        <strong>${escapeHtml(item.material_name || "Material")}</strong>
        <span>Estimado: ${escapeHtml(String(item.estimated_qty ?? "-"))} · Pendente: ${escapeHtml(String(item.pending_qty ?? "-"))}</span>
      </div>
      <span class="app-badge is-muted">${escapeHtml(item.supplier_name || item.last_event_type || "obra")}</span>
    </article>
  `).join("");
}

async function selectProject(projectId) {
  selectedProjectId = projectId;
  setHTML("#projectsList", renderProjectList(projectRows));

  try {
    const payload = await getProject(projectId);
    const project = payload.project || {};
    setText("#projectDetailTitle", project.name || "Projeto");
    setText("#projectDetailSubtitle", `${project.location_label || "-"} · ${project.area_label || "Pendente"} · ${project.current_phase_label || "Planejamento"}`);
    setHTML("#projectDetailSummary", renderProjectSummary(project));
    setHTML("#projectDetailTimeline", renderTimeline(payload.events || []));
    setHTML("#projectDetailMaterials", renderMaterials(payload.materials || []));

    const resumeLink = qs("#projectResumeLink");
    if (resumeLink) {
      const threadId = project.source_thread_id;
      resumeLink.classList.toggle("hidden", !threadId);
      if (threadId) {
        resumeLink.href = "new-request.html";
        resumeLink.onclick = () => {
          sessionStorage.setItem("cotai_active_chat_thread", threadId);
        };
      }
    }
  } catch (error) {
    handlePageError(error, "Nao foi possivel carregar o detalhe do projeto.");
  }
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

  setText("#projectsMetricTotal", String(projectRows.length));
  setText("#projectsMetricMaterials", String(projectRows.reduce((sum, row) => sum + Number(row.material_count || 0), 0)));
  setText("#projectsMetricCost", formatCurrencyBRL(projectRows.reduce((sum, row) => sum + parseCurrencyToNumber(row.estimated_total_display), 0)));
  setText("#projectsMetricActive", String(projectRows.filter((row) => String(row.status || "").toLowerCase() === "active").length));
  setHTML("#projectsList", renderProjectList(projectRows));

  const projectIdFromUrl = new URLSearchParams(window.location.search).get("projectId");
  const initialProjectId = projectIdFromUrl || projectRows[0]?.id || "";
  if (initialProjectId) {
    await selectProject(initialProjectId);
  }

  qs("#projectsList")?.addEventListener("click", async (event) => {
    const card = event.target.closest("[data-project-id]");
    if (!card) return;
    await selectProject(card.dataset.projectId || "");
  });
}

runPageBoot(init, { loadingMessage: "Carregando projetos salvos pela Cota." }).catch((error) => {
  handlePageError(error, "Nao foi possivel iniciar a tela de projetos.");
});
