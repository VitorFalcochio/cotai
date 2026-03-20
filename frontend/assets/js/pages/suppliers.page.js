import { LOGIN_PATH } from "../config.js";
import { requireAuth } from "../auth.js";
import { fetchProcurementOverview } from "../procurementData.js";
import { deleteSupplier, upsertSupplier } from "../suppliers.js";
import { initSidebar, qs, runPageBoot, setHTML, setText, showFeedback } from "../ui.js";

let suppliers = [];
let supplierMap = null;
let supplierMarkers = [];
let userMarker = null;
let userLocation = null;

const CITY_COORDINATES = {
  "sao jose do rio preto-sp": { lat: -20.8113, lng: -49.3758 },
  "rio preto-sp": { lat: -20.8113, lng: -49.3758 },
  "campinas-sp": { lat: -22.9056, lng: -47.0608 },
  "sao paulo-sp": { lat: -23.5505, lng: -46.6333 },
  "ribeirao preto-sp": { lat: -21.1775, lng: -47.8103 },
  "sorocaba-sp": { lat: -23.5015, lng: -47.4526 },
};

function normalizeText(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

function toNumber(value) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function getSupplierCoordinates(supplier) {
  const latitude = toNumber(supplier.latitude);
  const longitude = toNumber(supplier.longitude);
  if (latitude !== null && longitude !== null) {
    return { lat: latitude, lng: longitude, precise: true };
  }
  const cityKey = normalizeText(supplier.city);
  const stateKey = normalizeText(supplier.state);
  const fallback = CITY_COORDINATES[`${cityKey}-${stateKey}`];
  return fallback ? { ...fallback, precise: false } : null;
}

function haversineKm(origin, destination) {
  const toRadians = (value) => (value * Math.PI) / 180;
  const earthRadiusKm = 6371;
  const dLat = toRadians(destination.lat - origin.lat);
  const dLng = toRadians(destination.lng - origin.lng);
  const lat1 = toRadians(origin.lat);
  const lat2 = toRadians(destination.lat);
  const arc =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2;
  return earthRadiusKm * (2 * Math.atan2(Math.sqrt(arc), Math.sqrt(1 - arc)));
}

function formatDistance(distanceKm) {
  if (distanceKm === null || distanceKm === undefined) return "Distancia indisponivel";
  if (distanceKm < 1) return `${Math.round(distanceKm * 1000)} m`;
  return `${distanceKm.toFixed(1)} km`;
}

function supplierDirectionsUrl(supplier) {
  const coordinates = supplier.coordinates || getSupplierCoordinates(supplier);
  if (!coordinates) return "#";
  return `https://www.google.com/maps/dir/?api=1&destination=${coordinates.lat},${coordinates.lng}&travelmode=driving`;
}

function renderHighlights(items) {
  if (!items.length) {
    return '<article class="entity-list-item"><div class="entity-list-copy"><p>Sem fornecedores</p><strong>Cadastre os primeiros parceiros para iniciar a base.</strong></div><span class="app-badge is-muted">INFO</span></article>';
  }

  return items
    .map(
      (supplier) => `
        <article class="entity-list-item">
          <div class="entity-list-copy">
            <p>${supplier.name}</p>
            <strong>${supplier.quote_participation_count || 0} participacoes</strong>
          </div>
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
    return '<article class="entity-list-item"><div class="entity-list-copy"><p>Sem tags</p><strong>Adicione materiais atendidos para formar a cobertura.</strong></div><span class="app-badge is-muted">INFO</span></article>';
  }

  return ranked
    .map(
      ([tag, count]) => `
        <article class="entity-list-item">
          <div class="entity-list-copy">
            <p>${tag}</p>
            <strong>${count} fornecedor(es)</strong>
          </div>
          <span class="app-badge is-muted">TAG</span>
        </article>
      `
    )
    .join("");
}

function renderTags(tags) {
  const values = (tags || []).slice(0, 3);
  if (!values.length) return '<span class="mini-badge">Sem tags</span>';
  return values.map((tag) => `<span class="mini-badge">${tag}</span>`).join("");
}

function renderRows(rows) {
  if (!rows.length) {
    return '<tr><td colspan="6" class="app-empty">Nenhum fornecedor cadastrado.</td></tr>';
  }

  return rows
    .map(
      (supplier) => `
        <tr>
          <td>
            <div class="table-entity">
              <strong>${supplier.name}</strong>
              <small>${[supplier.region, supplier.state].filter(Boolean).join(" • ") || "Sem regiao definida"}</small>
            </div>
          </td>
          <td>
            <div class="table-entity">
              <strong>${supplier.city || "Sem cidade"}</strong>
              <small>${[supplier.address_line, supplier.contact_name, supplier.contact_channel].filter(Boolean).join(" • ") || "Sem endereco"}</small>
            </div>
          </td>
          <td><div class="tag-cluster">${renderTags(supplier.material_tags)}</div></td>
          <td>
            <div class="table-entity">
              <strong>${supplier.quote_participation_count || 0} cotacoes</strong>
              <small>Nota ${supplier.derived_rating ? supplier.derived_rating.toFixed(1) : "-"} • Prazo ${supplier.average_delivery_days || "-"}d</small>
            </div>
          </td>
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

function renderNearestSuppliers(rows) {
  if (!rows.length) {
    return '<article class="entity-list-item"><div class="entity-list-copy"><p>Sem lojas localizadas</p><strong>Cadastre latitude/longitude ou cidades conhecidas para ver distancia e rotas.</strong></div><span class="app-badge is-muted">MAPA</span></article>';
  }

  return rows
    .slice(0, 5)
    .map(
      (supplier) => `
        <article class="entity-list-item">
          <div class="entity-list-copy">
            <p>${supplier.name}</p>
            <strong>${formatDistance(supplier.distanceKm)}</strong>
            <small>${[supplier.city, supplier.state].filter(Boolean).join(" • ") || "Sem cidade"}${supplier.coordinates?.precise ? "" : " • coordenada aproximada"}</small>
          </div>
          <a class="btn btn-ghost" href="${supplierDirectionsUrl(supplier)}" target="_blank" rel="noreferrer">Rota</a>
        </article>
      `
    )
    .join("");
}

function ensureMap() {
  if (supplierMap || !window.L || !qs("#supplierMap")) return;
  supplierMap = window.L.map("supplierMap").setView([-22.9, -47.06], 6);
  window.L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "&copy; OpenStreetMap"
  }).addTo(supplierMap);
}

function updateSupplierMap() {
  ensureMap();
  if (!supplierMap) return;

  supplierMarkers.forEach((marker) => marker.remove());
  supplierMarkers = [];
  if (userMarker) {
    userMarker.remove();
    userMarker = null;
  }

  const mappedSuppliers = suppliers
    .map((supplier) => ({ ...supplier, coordinates: getSupplierCoordinates(supplier) }))
    .filter((supplier) => supplier.coordinates);

  mappedSuppliers.forEach((supplier) => {
    const marker = window.L.marker([supplier.coordinates.lat, supplier.coordinates.lng]).addTo(supplierMap);
    marker.bindPopup(`
      <div class="supplier-map-popup">
        <strong>${supplier.name}</strong>
        <p>${[supplier.address_line, supplier.city, supplier.state].filter(Boolean).join(" • ") || "Endereco nao informado"}</p>
        <p>${supplier.coordinates.precise ? "Localizacao da loja" : "Localizacao aproximada pela cidade"}</p>
        <a href="${supplierDirectionsUrl(supplier)}" target="_blank" rel="noreferrer">Abrir rota</a>
      </div>
    `);
    supplierMarkers.push(marker);
  });

  let nearestSuppliers = mappedSuppliers.map((supplier) => ({ ...supplier, distanceKm: null }));
  if (userLocation) {
    nearestSuppliers = nearestSuppliers
      .map((supplier) => ({ ...supplier, distanceKm: haversineKm(userLocation, supplier.coordinates) }))
      .sort((left, right) => (left.distanceKm ?? Number.POSITIVE_INFINITY) - (right.distanceKm ?? Number.POSITIVE_INFINITY));

    userMarker = window.L.marker([userLocation.lat, userLocation.lng], {
      icon: window.L.divIcon({
        className: "supplier-user-pin",
        html: "<span></span>",
        iconSize: [18, 18]
      })
    }).addTo(supplierMap);

    setText(
      "#supplierMapSummary",
      nearestSuppliers.length
        ? `${nearestSuppliers.length} loja(s) mapeadas. Mais proxima: ${nearestSuppliers[0].name} a ${formatDistance(nearestSuppliers[0].distanceKm)}.`
        : "Sua localizacao foi carregada, mas ainda nao ha fornecedores com coordenadas."
    );

    const bounds = window.L.latLngBounds([
      [userLocation.lat, userLocation.lng],
      ...nearestSuppliers.map((supplier) => [supplier.coordinates.lat, supplier.coordinates.lng])
    ]);
    supplierMap.fitBounds(bounds.pad(0.18));
  } else if (mappedSuppliers.length) {
    const bounds = window.L.latLngBounds(mappedSuppliers.map((supplier) => [supplier.coordinates.lat, supplier.coordinates.lng]));
    supplierMap.fitBounds(bounds.pad(0.18));
    setText("#supplierMapSummary", "Mapa das lojas cadastradas. Ative sua localizacao para calcular distancia e abrir rotas.");
  } else {
    supplierMap.setView([-22.9, -47.06], 6);
    setText("#supplierMapSummary", "Ative sua localizacao ou cadastre latitude e longitude dos fornecedores para visualizar as lojas no mapa.");
  }

  setHTML("#supplierNearestList", renderNearestSuppliers(nearestSuppliers));
}

function requestUserLocation() {
  if (!navigator.geolocation) {
    showFeedback("#supplierFeedback", "Seu navegador nao suporta geolocalizacao.");
    return;
  }
  navigator.geolocation.getCurrentPosition(
    (position) => {
      userLocation = {
        lat: position.coords.latitude,
        lng: position.coords.longitude
      };
      updateSupplierMap();
      showFeedback("#supplierFeedback", "Localizacao carregada para comparar lojas proximas.", false);
    },
    () => {
      showFeedback("#supplierFeedback", "Nao foi possivel obter sua localizacao.");
    },
    { enableHighAccuracy: true, timeout: 12000 }
  );
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
  qs("#supplierAddress").value = supplier?.address_line || "";
  qs("#supplierPostalCode").value = supplier?.postal_code || "";
  qs("#supplierLatitude").value = supplier?.latitude ?? "";
  qs("#supplierLongitude").value = supplier?.longitude ?? "";
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
  setHTML("#supplierHighlights", renderHighlights(suppliers.slice(0, 4)));
  setHTML("#supplierCoverage", renderCoverage(suppliers));
  setHTML("#suppliersTableBody", renderRows(suppliers));
  updateSupplierMap();
  return overview;
}

async function init() {
  const session = await requireAuth(LOGIN_PATH);
  if (!session) return;
  initSidebar();

  await loadPage();

  qs("#newSupplierBtn")?.addEventListener("click", () => openModal());
  qs("#supplierLocateBtn")?.addEventListener("click", requestUserLocation);
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
      address_line: qs("#supplierAddress").value.trim(),
      postal_code: qs("#supplierPostalCode").value.trim(),
      latitude: qs("#supplierLatitude").value === "" ? null : Number(qs("#supplierLatitude").value),
      longitude: qs("#supplierLongitude").value === "" ? null : Number(qs("#supplierLongitude").value),
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
      showFeedback("#supplierFeedback", error.message || "Nao foi possivel salvar o fornecedor.");
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
        showFeedback("#supplierFeedback", error.message || "Nao foi possivel excluir o fornecedor.");
      }
    }
  });
}

runPageBoot(init, { loadingMessage: "Carregando a base de fornecedores." }).catch((error) => {
  showFeedback("#supplierFeedback", error.message || "Erro ao iniciar a pagina de fornecedores.");
});
