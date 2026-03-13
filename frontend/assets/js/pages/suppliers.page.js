import { LOGIN_PATH } from "../config.js";
import { requireAuth } from "../auth.js";
import { fetchProcurementOverview } from "../procurementData.js";
import { deleteSupplier, upsertSupplier } from "../suppliers.js";
import { formatDateTime, initSidebar, qs, runPageBoot, setHTML, setText, showFeedback } from "../ui.js";

let suppliers = [];

function renderHighlights(items) {
  if (!items.length) {
    return '<article class="admin-status-row"><div><p>Sem fornecedores</p><strong>Cadastre os primeiros parceiros para iniciar a base.</strong></div><span class="app-badge is-muted">INFO</span></article>';
  }
  return items
    .map(
      (supplier) => `
        <article class="admin-status-row">
          <div><p>${supplier.name}</p><strong>${supplier.quote_participation_count || 0} participações</strong></div>
          <span class="app-badge ${supplier.derived_rating && supplier.derived_rating >= 4 ? "is-success" : "is-muted"}">${supplier.derived_rating ? supplier.derived_rating.toFixed(1) : "Sem nota"}</span>
        </article>
      `
    )
    .join("");
}

function renderCoverage(items) {
  const counts = new Map();
  items.forEach((supplier) => {
    (supplier.material_tags || []).forEach((tag) => counts.set(tag, (counts.get(tag) || 0) + 1));
  });
  const ranked = [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 6);
  if (!ranked.length) {
    return '<article class="admin-status-row"><div><p>Sem tags</p><strong>Adicione materiais atendidos para formar a cobertura.</strong></div><span class="app-badge is-muted">INFO</span></article>';
  }
  return ranked
    .map(
      ([tag, count]) => `
        <article class="admin-status-row">
          <div><p>${tag}</p><strong>${count} fornecedor(es)</strong></div>
          <span class="app-badge is-muted">TAG</span>
        </article>
      `
    )
    .join("");
}

function renderRows(rows) {
  if (!rows.length) {
    return '<tr><td colspan="6" class="app-empty">Nenhum fornecedor cadastrado.</td></tr>';
  }

  return rows
    .map(
      (supplier) => `
        <tr>
          <td><strong>${supplier.name}</strong><br /><small>${supplier.region || "-"} ${supplier.state ? `| ${supplier.state}` : ""}</small></td>
          <td>${supplier.city || "-"}<br /><small>${supplier.contact_name || "-"} | ${supplier.contact_channel || "-"}</small></td>
          <td>${(supplier.material_tags || []).join(", ") || "-"}</td>
          <td><strong>${supplier.quote_participation_count || 0} cotacoes</strong><br /><small>Rating: ${supplier.derived_rating ? supplier.derived_rating.toFixed(1) : "-"} | Prazo: ${supplier.average_delivery_days || "-"}d</small></td>
          <td><span class="app-badge ${String(supplier.status || "").toLowerCase() === "active" ? "is-success" : "is-muted"}">${supplier.status || "active"}</span></td>
          <td class="app-actions">
            <button class="btn btn-ghost" data-action="edit" data-id="${supplier.id}">Editar</button>
            <button class="btn btn-ghost" data-action="delete" data-id="${supplier.id}">Excluir</button>
          </td>
        </tr>
      `
    )
    .join("");
}

function openModal(supplier = null) {
  const modal = qs("#supplierModal");
  if (!modal) return;
  qs("#supplierModalTitle").textContent = supplier ? "Editar fornecedor" : "Novo fornecedor";
  qs("#supplierId").value = supplier?.id || "";
  qs("#supplierName").value = supplier?.name || "";
  qs("#supplierRegion").value = supplier?.region || "";
  qs("#supplierCity").value = supplier?.city || "";
  qs("#supplierState").value = supplier?.state || "";
  qs("#supplierDeliveryDays").value = supplier?.average_delivery_days || "";
  qs("#supplierContact").value = supplier?.contact_name || "";
  qs("#supplierChannel").value = supplier?.contact_channel || "";
  qs("#supplierTags").value = (supplier?.material_tags || []).join(", ");
  qs("#supplierStatus").value = supplier?.status || "active";
  modal.classList.add("show");
  modal.setAttribute("aria-hidden", "false");
  document.body.style.overflow = "hidden";
}

function closeModal() {
  const modal = qs("#supplierModal");
  if (!modal) return;
  modal.classList.remove("show");
  modal.setAttribute("aria-hidden", "true");
  document.body.style.overflow = "";
}

async function loadPage() {
  const overview = await fetchProcurementOverview();
  suppliers = overview.suppliers;
  setText("#supplierMetricTotal", String(suppliers.filter((supplier) => String(supplier.status || "").toLowerCase() === "active").length));
  setText("#supplierMetricRating", suppliers[0]?.derived_rating ? suppliers[0].derived_rating.toFixed(1) : "-");
  setText("#supplierMetricDelivery", suppliers[0]?.average_delivery_days ? `${suppliers[0].average_delivery_days}d` : "-");
  setText("#supplierMetricTop", suppliers[0]?.name || "-");
  setHTML("#supplierHighlights", renderHighlights(suppliers.slice(0, 5)));
  setHTML("#supplierCoverage", renderCoverage(suppliers));
  setHTML("#suppliersTableBody", renderRows(suppliers));
  return overview;
}

async function init() {
  const session = await requireAuth(LOGIN_PATH);
  if (!session) return;
  initSidebar();

  await loadPage();

  qs("#newSupplierBtn")?.addEventListener("click", () => openModal());
  document.querySelectorAll("[data-close-modal]").forEach((button) => {
    button.addEventListener("click", closeModal);
  });
  qs("#supplierModal .app-modal-backdrop")?.addEventListener("click", closeModal);

  qs("#supplierForm")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const payload = {
      id: qs("#supplierId").value || undefined,
      name: qs("#supplierName").value.trim(),
      region: qs("#supplierRegion").value.trim(),
      city: qs("#supplierCity").value.trim(),
      state: qs("#supplierState").value.trim(),
      average_delivery_days: Number(qs("#supplierDeliveryDays").value || 0) || null,
      contact_name: qs("#supplierContact").value.trim(),
      contact_channel: qs("#supplierChannel").value.trim(),
      material_tags: qs("#supplierTags").value.split(",").map((item) => item.trim()).filter(Boolean),
      status: qs("#supplierStatus").value
    };

    try {
      await upsertSupplier(payload);
      closeModal();
      await loadPage();
      showFeedback("#supplierFeedback", "Fornecedor salvo com sucesso.", false);
    } catch (error) {
      showFeedback("#supplierFeedback", error.message || "Não foi possível salvar o fornecedor.");
    }
  });

  qs("#suppliersTableBody")?.addEventListener("click", async (event) => {
    const button = event.target.closest("button[data-action]");
    if (!button) return;
    const supplier = suppliers.find((item) => item.id === button.dataset.id);
    if (!supplier) return;

    if (button.dataset.action === "edit") {
      openModal(supplier);
      return;
    }

    if (button.dataset.action === "delete") {
      if (!window.confirm(`Excluir fornecedor "${supplier.name}"?`)) return;
      try {
        await deleteSupplier(supplier.id);
        await loadPage();
      } catch (error) {
        showFeedback("#supplierFeedback", error.message || "Não foi possível excluir o fornecedor.");
      }
    }
  });
}

runPageBoot(init, { loadingMessage: "Carregando a base de fornecedores." }).catch((error) => {
  showFeedback("#supplierFeedback", error.message || "Erro ao iniciar a página de fornecedores.");
});
