import { deleteSnapshot, fetchAdminSnapshots, upsertSnapshot } from "../adminSnapshots.js";
import { bootAdminPage, runAdminPageBoot } from "../adminPage.js";
import { formatDateTime, qs, setHTML, setText, showFeedback } from "../ui.js";

let snapshots = [];
let filteredSnapshots = [];

function normalize(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

function formatMoney(value) {
  if (value === null || value === undefined || value === "") return "-";
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL"
  }).format(Number(value) || 0);
}

function renderRows(rows) {
  if (!rows.length) {
    return '<tr><td colspan="8" class="app-empty">Nenhum snapshot de preço encontrado.</td></tr>';
  }

  return rows
    .map(
      (row) => `
        <tr>
          <td><strong>${row.item_name || "-"}</strong><br /><small>${row.normalized_item_name || "-"}</small></td>
          <td>${row.supplier_name || "-"}<br /><small>${row.provider || row.source_name || "-"}</small></td>
          <td>${formatMoney(row.unit_price ?? row.price)}<br /><small>${row.currency || "BRL"}</small></td>
          <td>${row.delivery_label || (row.delivery_days ? `${row.delivery_days} dia(s)` : "-")}</td>
          <td>${row.query || "-"}</td>
          <td>${formatDateTime(row.captured_at)}</td>
          <td>${row.result_url ? `<a href="${row.result_url}" target="_blank" rel="noopener noreferrer">Abrir</a>` : "-"}</td>
          <td class="app-actions">
            <button class="btn btn-ghost" data-action="edit" data-id="${row.id}">Editar</button>
            <button class="btn btn-ghost" data-action="delete" data-id="${row.id}">Excluir</button>
          </td>
        </tr>
      `
    )
    .join("");
}

function computeMetrics(rows) {
  const uniqueItems = new Set(rows.map((row) => normalize(row.normalized_item_name || row.item_name)).filter(Boolean)).size;
  const uniqueSuppliers = new Set(rows.map((row) => normalize(row.supplier_name)).filter(Boolean)).size;
  const averagePrice =
    rows.length && rows.some((row) => row.unit_price ?? row.price)
      ? rows.reduce((sum, row) => sum + (Number(row.unit_price ?? row.price) || 0), 0) / rows.length
      : null;
  const latestCapturedAt = rows[0]?.captured_at || null;

  setText("#snapshotMetricTotal", String(rows.length));
  setText("#snapshotMetricItems", String(uniqueItems));
  setText("#snapshotMetricSuppliers", String(uniqueSuppliers));
  setText("#snapshotMetricAveragePrice", averagePrice ? formatMoney(averagePrice) : "-");
  setText("#snapshotMetricLatest", latestCapturedAt ? formatDateTime(latestCapturedAt) : "-");
}

function openModal(snapshot = null) {
  const modal = qs("#snapshotModal");
  if (!modal) return;
  qs("#snapshotModalTitle").textContent = snapshot ? "Editar snapshot" : "Novo produto/preço";
  qs("#snapshotId").value = snapshot?.id || "";
  qs("#snapshotCompanyId").value = snapshot?.company_id || "";
  qs("#snapshotItemName").value = snapshot?.item_name || "";
  qs("#snapshotNormalizedItemName").value = snapshot?.normalized_item_name || "";
  qs("#snapshotQuery").value = snapshot?.query || "";
  qs("#snapshotProvider").value = snapshot?.provider || "manual";
  qs("#snapshotSourceName").value = snapshot?.source_name || "";
  qs("#snapshotSupplierName").value = snapshot?.supplier_name || "";
  qs("#snapshotTitle").value = snapshot?.title || "";
  qs("#snapshotPrice").value = snapshot?.price ?? "";
  qs("#snapshotUnitPrice").value = snapshot?.unit_price ?? "";
  qs("#snapshotCurrency").value = snapshot?.currency || "BRL";
  qs("#snapshotDeliveryDays").value = snapshot?.delivery_days ?? "";
  qs("#snapshotDeliveryLabel").value = snapshot?.delivery_label || "";
  qs("#snapshotResultUrl").value = snapshot?.result_url || "";
  qs("#snapshotMetadata").value = JSON.stringify(snapshot?.metadata || {}, null, 2);
  modal.classList.add("show");
  modal.setAttribute("aria-hidden", "false");
  document.body.style.overflow = "hidden";
}

function closeModal() {
  const modal = qs("#snapshotModal");
  if (!modal) return;
  modal.classList.remove("show");
  modal.setAttribute("aria-hidden", "true");
  document.body.style.overflow = "";
}

function applyFilters() {
  const searchValue = normalize(qs("#snapshotSearch")?.value);
  const providerValue = normalize(qs("#snapshotProviderFilter")?.value);

  filteredSnapshots = snapshots.filter((row) => {
    const matchesSearch =
      !searchValue ||
      [row.item_name, row.normalized_item_name, row.supplier_name, row.query, row.provider]
        .some((value) => normalize(value).includes(searchValue));
    const matchesProvider = !providerValue || normalize(row.provider) === providerValue;
    return matchesSearch && matchesProvider;
  });

  setHTML("#adminSnapshotsBody", renderRows(filteredSnapshots));
  computeMetrics(filteredSnapshots);
}

async function loadPage() {
  const payload = await fetchAdminSnapshots();
  snapshots = payload.rows;
  applyFilters();
  if (payload.notices.length) {
    showFeedback("#adminSnapshotsFeedback", payload.notices.join(" "));
  }
}

async function init() {
  await bootAdminPage();
  await loadPage();

  qs("#newSnapshotBtn")?.addEventListener("click", () => openModal());
  qs("#snapshotSearch")?.addEventListener("input", applyFilters);
  qs("#snapshotProviderFilter")?.addEventListener("change", applyFilters);
  qs("#snapshotClearFilters")?.addEventListener("click", () => {
    if (qs("#snapshotSearch")) qs("#snapshotSearch").value = "";
    if (qs("#snapshotProviderFilter")) qs("#snapshotProviderFilter").value = "";
    applyFilters();
  });

  document.querySelectorAll("[data-close-modal]").forEach((button) => {
    button.addEventListener("click", closeModal);
  });
  qs("#snapshotModal .app-modal-backdrop")?.addEventListener("click", closeModal);

  qs("#snapshotForm")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const metadataText = qs("#snapshotMetadata").value.trim();
      const metadata = metadataText ? JSON.parse(metadataText) : {};
      const itemName = qs("#snapshotItemName").value.trim();
      const normalizedItemName = qs("#snapshotNormalizedItemName").value.trim() || normalize(itemName);
      await upsertSnapshot({
        id: qs("#snapshotId").value || undefined,
        company_id: qs("#snapshotCompanyId").value.trim() || null,
        item_name: itemName,
        normalized_item_name: normalizedItemName,
        query: qs("#snapshotQuery").value.trim() || itemName,
        provider: qs("#snapshotProvider").value.trim() || "manual",
        source_name: qs("#snapshotSourceName").value.trim() || qs("#snapshotProvider").value.trim() || "manual",
        supplier_name: qs("#snapshotSupplierName").value.trim(),
        title: qs("#snapshotTitle").value.trim() || itemName,
        price: Number(qs("#snapshotPrice").value || 0) || null,
        unit_price: Number(qs("#snapshotUnitPrice").value || 0) || null,
        currency: qs("#snapshotCurrency").value.trim() || "BRL",
        delivery_days: Number(qs("#snapshotDeliveryDays").value || 0) || null,
        delivery_label: qs("#snapshotDeliveryLabel").value.trim() || null,
        result_url: qs("#snapshotResultUrl").value.trim() || null,
        metadata
      });
      closeModal();
      await loadPage();
      showFeedback("#adminSnapshotsFeedback", "Snapshot salvo com sucesso.", false);
    } catch (error) {
      showFeedback("#adminSnapshotsFeedback", error.message || "Não foi possível salvar o snapshot.");
    }
  });

  qs("#adminSnapshotsBody")?.addEventListener("click", async (event) => {
    const button = event.target.closest("button[data-action]");
    if (!button) return;
    const snapshot = snapshots.find((item) => item.id === button.dataset.id);
    if (!snapshot) return;

    if (button.dataset.action === "edit") {
      openModal(snapshot);
      return;
    }

    if (button.dataset.action === "delete") {
      if (!window.confirm(`Excluir snapshot de "${snapshot.item_name}"?`)) return;
      try {
        await deleteSnapshot(snapshot.id);
        await loadPage();
        showFeedback("#adminSnapshotsFeedback", "Snapshot excluido com sucesso.", false);
      } catch (error) {
        showFeedback("#adminSnapshotsFeedback", error.message || "Não foi possível excluir o snapshot.");
      }
    }
  });
}

runAdminPageBoot(init, "Carregando snapshots de preço.").catch((error) => {
  showFeedback("#adminSnapshotsFeedback", error.message || "Erro ao iniciar a página de snapshots.");
});
