import { fetchAdminRequests, reprocessAdminRequest } from "../adminRequests.js";
import { approveRequest } from "../chatApi.js";
import { bootAdminPage, runAdminPageBoot } from "../adminPage.js";
import { copyText, formatDateTime, qs, setHTML, showFeedback } from "../ui.js";

let allRows = [];
let visibleRows = [];

function badgeClass(status) {
  const value = String(status || "").toLowerCase();
  if (value.includes("done") || value.includes("approved")) return "is-success";
  if (value.includes("error") || value.includes("urgent")) return "is-warning";
  if (value.includes("awaiting") || value.includes("quot")) return "is-warning";
  return "is-muted";
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function renderRows(rows) {
  if (!rows.length) {
    return '<tr><td colspan="7" class="app-empty">Nenhum pedido encontrado.</td></tr>';
  }

  return rows
    .map(
      (row) => `
        <tr>
          <td><strong>${row.requestCode}</strong><br /><small>${row.duplicateOfRequestId ? `Duplicado de ${row.duplicateOfRequestId}` : "Sem duplicidade marcada"}</small></td>
          <td><strong>${escapeHtml(row.company)}</strong><br /><small>${escapeHtml(row.customerName)}</small></td>
          <td><span class="app-badge ${badgeClass(row.status)}">${row.status}</span><br /><small>${row.approvalStatus}</small></td>
          <td><strong>${row.priority}</strong><br /><small>${formatDateTime(row.slaDueAt)}</small></td>
          <td><strong>${row.supplierCount} fornecedor(es)</strong><br /><small>${row.bestPrice === null ? "Sem preços" : `Melhor preço: ${row.bestPrice}`}</small></td>
          <td><strong>${formatDateTime(row.updatedAt)}</strong><br /><small>${row.latestError ? `Falha: ${escapeHtml(row.latestError)}` : row.processedAt ? `Finalizado: ${formatDateTime(row.processedAt)}` : "Sem falha registrada"}</small></td>
          <td>
            <div class="admin-table-stack">
              <span>${row.execution}</span>
              <div class="app-actions">
                <button class="btn btn-ghost" data-action="details" data-id="${row.id}">Detalhes</button>
                ${row.approvalRequired && row.approvalStatus !== "APPROVED" ? `<button class="btn btn-ghost" data-action="approve" data-id="${row.id}">Aprovar</button>` : ""}
                <button class="btn btn-ghost" data-action="requote" data-id="${row.id}">Recotar</button>
                <button class="btn btn-ghost" data-action="resend" data-id="${row.id}">Copiar resposta</button>
                <button class="btn btn-ghost" data-action="logs" data-id="${row.id}">Abrir logs</button>
              </div>
            </div>
          </td>
        </tr>
      `
    )
    .join("");
}

function applyFilters() {
  const searchValue = String(qs("#adminRequestsSearch")?.value || "").toLowerCase().trim();
  const statusValue = String(qs("#adminRequestsStatus")?.value || "").toUpperCase();
  const priorityValue = String(qs("#adminRequestsPriority")?.value || "").toUpperCase();
  const approvalValue = String(qs("#adminRequestsApproval")?.value || "").toUpperCase();
  const companyValue = String(qs("#adminRequestsCompany")?.value || "").toLowerCase().trim();

  visibleRows = allRows.filter((row) => {
    const matchesSearch =
      !searchValue ||
      [row.requestCode, row.company, row.customerName, row.latestError]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(searchValue));
    const matchesStatus = !statusValue || String(row.status).toUpperCase() === statusValue;
    const matchesPriority = !priorityValue || String(row.priority).toUpperCase() === priorityValue;
    const matchesApproval = !approvalValue || String(row.approvalStatus).toUpperCase() === approvalValue;
    const matchesCompany = !companyValue || String(row.company).toLowerCase().includes(companyValue);
    return matchesSearch && matchesStatus && matchesPriority && matchesApproval && matchesCompany;
  });

  setHTML("#adminRequestsBody", renderRows(visibleRows));
}

function exportCsv() {
  const header = ["request_code", "company", "customer", "status", "priority", "approval_status", "sla_due_at", "supplier_count", "best_price", "latest_error"];
  const rows = visibleRows.map((row) => [
    row.requestCode,
    row.company,
    row.customerName,
    row.status,
    row.priority,
    row.approvalStatus,
    row.slaDueAt || "",
    row.supplierCount,
    row.bestPrice ?? "",
    row.latestError || ""
  ]);
  const csv = [header, ...rows]
    .map((line) => line.map((cell) => `"${String(cell ?? "").replaceAll('"', '""')}"`).join(","))
    .join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "cotai-admin-requests.csv";
  link.click();
  URL.revokeObjectURL(url);
}

async function loadRequests() {
  const payload = await fetchAdminRequests();
  allRows = payload.rows;
  applyFilters();
  if (payload.notices.length) {
    showFeedback("#adminRequestsFeedback", payload.notices.join(" "));
  }
}

async function init() {
  await bootAdminPage();
  const body = qs("#adminRequestsBody");
  if (!body) return;

  await loadRequests();

  ["#adminRequestsSearch", "#adminRequestsStatus", "#adminRequestsPriority", "#adminRequestsApproval", "#adminRequestsCompany"].forEach((selector) => {
    qs(selector)?.addEventListener("input", applyFilters);
    qs(selector)?.addEventListener("change", applyFilters);
  });

  qs("#adminRequestsClear")?.addEventListener("click", () => {
    ["#adminRequestsSearch", "#adminRequestsStatus", "#adminRequestsPriority", "#adminRequestsApproval", "#adminRequestsCompany"].forEach((selector) => {
      const element = qs(selector);
      if (element) element.value = "";
    });
    applyFilters();
  });

  qs("#exportRequestsButton")?.addEventListener("click", exportCsv);

  body.addEventListener("click", async (event) => {
    const button = event.target.closest("button[data-action]");
    if (!button) return;

    const request = allRows.find((item) => item.id === button.dataset.id);
    if (!request) return;

    try {
      if (button.dataset.action === "details") {
        window.alert(
          `Pedido: ${request.requestCode}\nEmpresa: ${request.company}\nCliente: ${request.customerName}\nStatus: ${request.status}\nPrioridade: ${request.priority}\nAprovação: ${request.approvalStatus}\nSLA: ${request.slaDueAt || "-"}\nFornecedores: ${request.supplierCount}\nMelhor preço: ${request.bestPrice ?? "-"}\nFalha recente: ${request.latestError || "nenhuma"}`
        );
        return;
      }

      if (button.dataset.action === "approve") {
        const comment = window.prompt("Comentário da aprovação:", "Liberado para cotação");
        if (comment === null) return;
        await approveRequest(request.id, comment);
        await loadRequests();
        showFeedback("#adminRequestsFeedback", "Pedido aprovado e reenfileirado.", false);
        return;
      }

      if (button.dataset.action === "requote") {
        const reason = window.prompt("Motivo do reprocessamento:", request.latestError || "Nova tentativa operacional");
        if (!reason) return;
        await reprocessAdminRequest(request.id, reason);
        await loadRequests();
        showFeedback("#adminRequestsFeedback", "Pedido reenfileirado com auditoria e motivo registrado.", false);
        return;
      }

      if (button.dataset.action === "resend") {
        if (!request.latestResponse) {
          showFeedback("#adminRequestsFeedback", "Este pedido ainda não possui uma resposta consolidada.");
          return;
        }
        await copyText(request.latestResponse);
        showFeedback("#adminRequestsFeedback", "Resposta copiada para compartilhar no canal desejado.", false);
        return;
      }

      if (button.dataset.action === "logs") {
        window.location.href = `admin-logs.html?request_id=${encodeURIComponent(request.id)}`;
      }
    } catch (error) {
      showFeedback("#adminRequestsFeedback", error.message || "Não foi possível executar a ação no pedido.");
    }
  });
}

runAdminPageBoot(init, "Carregando central de pedidos.").catch((error) => {
  showFeedback("#adminRequestsFeedback", error.message || "Erro ao iniciar a central de pedidos.");
});
