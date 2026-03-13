import { fetchAdminUsers, updateUser } from "../adminUsers.js";
import { bootAdminPage, runAdminPageBoot } from "../adminPage.js";
import { formatDateTime, qs, setHTML, showFeedback } from "../ui.js";

function badgeClass(status) {
  const value = String(status || "").toLowerCase();
  if (value.includes("active")) return "is-success";
  if (value.includes("inactive")) return "is-muted";
  return "is-warning";
}

function renderRows(rows) {
  if (!rows.length) {
    return '<tr><td colspan="7" class="app-empty">Nenhum usuário disponível.</td></tr>';
  }

  return rows
    .map(
      (row) => `
        <tr>
          <td>${row.name}</td>
          <td>${row.email}</td>
          <td>${row.company}</td>
          <td>${row.role}</td>
          <td>${formatDateTime(row.lastLogin)}</td>
          <td><span class="app-badge ${badgeClass(row.status)}">${row.status}</span></td>
          <td class="app-actions">
            <button class="btn btn-ghost" data-action="toggle" data-id="${row.id}" data-status="${row.status}">${String(row.status).toLowerCase() === "active" ? "Desativar" : "Reativar"}</button>
            <button class="btn btn-ghost" data-action="role" data-id="${row.id}" data-role="${row.role}">Alterar role</button>
          </td>
        </tr>
      `
    )
    .join("");
}

async function loadUsers() {
  const payload = await fetchAdminUsers();
  setHTML("#adminUsersBody", renderRows(payload.rows));
  if (payload.notices.length) {
    showFeedback("#adminUsersFeedback", payload.notices.join(" "));
  }
  return payload.rows;
}

async function init() {
  await bootAdminPage();
  const body = qs("#adminUsersBody");
  if (!body) return;

  let rows = await loadUsers();

  body.addEventListener("click", async (event) => {
    const button = event.target.closest("button[data-action]");
    if (!button) return;

    const user = rows.find((item) => item.id === button.dataset.id);
    if (!user) return;

    try {
      if (button.dataset.action === "toggle") {
        const nextStatus = String(user.status).toLowerCase() === "active" ? "inactive" : "active";
        await updateUser(user.id, { status: nextStatus });
      }

      if (button.dataset.action === "role") {
        const nextRole = window.prompt("Novo perfil do usuário:", user.role);
        if (!nextRole) return;
        await updateUser(user.id, { role: nextRole });
      }

      rows = await loadUsers();
      showFeedback("#adminUsersFeedback", "Usuario atualizado com sucesso.", false);
    } catch (error) {
      showFeedback("#adminUsersFeedback", error.message || "Não foi possível atualizar o usuário.");
    }
  });
}

runAdminPageBoot(init, "Carregando usuários e permissões.").catch((error) => {
  showFeedback("#adminUsersFeedback", error.message || "Erro ao iniciar a página de usuários.");
});
