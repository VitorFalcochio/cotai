import { fetchAdminLogs } from "../adminLogs.js";
import { bootAdminPage } from "../adminPage.js";
import { formatDateTime, qs, setHTML, showFeedback } from "../ui.js";

function renderOptions(items, placeholder) {
  return [`<option value="all">${placeholder}</option>`]
    .concat(items.map((item) => `<option value="${item}">${item}</option>`))
    .join("");
}

function renderRows(rows) {
  if (!rows.length) {
    return '<tr><td colspan="5" class="app-empty">Nenhum evento encontrado com os filtros atuais.</td></tr>';
  }

  return rows
    .map(
      (row) => `
        <tr>
          <td>${formatDateTime(row.createdAt)}</td>
          <td>${row.type}</td>
          <td>${row.company}</td>
          <td>${row.actor}</td>
          <td>${row.message}</td>
        </tr>
      `
    )
    .join("");
}

async function loadLogs() {
  const urlParams = new URLSearchParams(window.location.search);
  const filters = {
    type: qs("#logTypeFilter")?.value || "all",
    company: qs("#logCompanyFilter")?.value || "all",
    startDate: qs("#logStartDate")?.value || "",
    endDate: qs("#logEndDate")?.value || "",
    requestId: urlParams.get("request_id") || ""
  };

  const payload = await fetchAdminLogs(filters);
  setHTML("#adminLogsBody", renderRows(payload.rows));

  const companyFilter = qs("#logCompanyFilter");
  const typeFilter = qs("#logTypeFilter");
  if (companyFilter && companyFilter.dataset.ready !== "true") {
    setHTML(companyFilter, renderOptions(payload.companies, "Todas as empresas"));
    companyFilter.dataset.ready = "true";
  }
  if (typeFilter && typeFilter.dataset.ready !== "true") {
    setHTML(typeFilter, renderOptions(payload.types, "Todos os eventos"));
    typeFilter.dataset.ready = "true";
  }

  if (payload.notices.length) {
    showFeedback("#adminLogsFeedback", payload.notices.join(" "));
  }
}

async function init() {
  await bootAdminPage();

  const form = qs("#adminLogsFilters");
  form?.addEventListener("submit", async (event) => {
    event.preventDefault();
    await loadLogs();
  });

  await loadLogs();
}

init().catch((error) => {
  showFeedback("#adminLogsFeedback", error.message || "Erro ao iniciar a pagina de logs.");
});
