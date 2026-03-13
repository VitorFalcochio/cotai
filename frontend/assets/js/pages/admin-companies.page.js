import { fetchAdminCompanies, updateCompany } from "../adminCompanies.js";
import { bootAdminPage, runAdminPageBoot } from "../adminPage.js";
import { formatDateTime, qs, setHTML, showFeedback } from "../ui.js";

function badgeClass(status) {
  const value = String(status || "").toLowerCase();
  if (value.includes("active")) return "is-success";
  if (value.includes("block")) return "is-warning";
  if (value.includes("inactive") || value.includes("disabled")) return "is-muted";
  return "is-muted";
}

function renderRows(rows) {
  if (!rows.length) {
    return '<tr><td colspan="8" class="app-empty">Nenhuma empresa disponivel.</td></tr>';
  }

  return rows
    .map(
      (row) => `
        <tr>
          <td>${row.name}</td>
          <td>${row.plan}</td>
          <td><span class="app-badge ${badgeClass(row.status)}">${row.status}</span></td>
          <td>${row.users}</td>
          <td>${row.requests}</td>
          <td>${formatDateTime(row.createdAt)}</td>
          <td>${formatDateTime(row.lastRequestAt)}</td>
          <td class="app-actions">
            <button class="btn btn-ghost" data-action="details" data-id="${row.id}">Ver detalhes</button>
            <button class="btn btn-ghost" data-action="plan" data-id="${row.id}">Alterar plano</button>
            <button class="btn btn-ghost" data-action="toggle" data-id="${row.id}" data-status="${row.status}">${String(row.status).toLowerCase() === "active" ? "Desativar" : "Ativar"}</button>
            <button class="btn btn-ghost" data-action="block" data-id="${row.id}">Bloquear</button>
          </td>
        </tr>
      `
    )
    .join("");
}

async function loadCompanies() {
  const payload = await fetchAdminCompanies();
  setHTML("#adminCompaniesBody", renderRows(payload.rows));
  if (payload.notices.length) {
    showFeedback("#adminCompaniesFeedback", payload.notices.join(" "));
  }
  return payload.rows;
}

async function init() {
  await bootAdminPage();
  const body = qs("#adminCompaniesBody");
  if (!body) return;

  let rows = await loadCompanies();

  body.addEventListener("click", async (event) => {
    const button = event.target.closest("button[data-action]");
    if (!button) return;

    const company = rows.find((item) => item.id === button.dataset.id);
    if (!company) return;

    try {
      if (button.dataset.action === "details") {
        window.alert(
          `Empresa: ${company.name}\nPlano: ${company.plan}\nStatus: ${company.status}\nUsuarios: ${company.users}\nPedidos: ${company.requests}`
        );
        return;
      }

      if (button.dataset.action === "plan") {
        const nextPlan = window.prompt("Novo plano da empresa:", company.plan);
        if (!nextPlan) return;
        await updateCompany(company.id, { plan: nextPlan });
      }

      if (button.dataset.action === "toggle") {
        const nextStatus = String(company.status).toLowerCase() === "active" ? "inactive" : "active";
        await updateCompany(company.id, { status: nextStatus });
      }

      if (button.dataset.action === "block") {
        await updateCompany(company.id, { status: "blocked" });
      }

      rows = await loadCompanies();
      showFeedback("#adminCompaniesFeedback", "Empresa atualizada com sucesso.", false);
    } catch (error) {
      showFeedback("#adminCompaniesFeedback", error.message || "Não foi possível atualizar a empresa.");
    }
  });
}

runAdminPageBoot(init, "Carregando empresas cadastradas.").catch((error) => {
  showFeedback("#adminCompaniesFeedback", error.message || "Erro ao iniciar a página de empresas.");
});
