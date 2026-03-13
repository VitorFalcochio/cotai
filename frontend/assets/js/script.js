// ====== CONFIG ======
const WHATSAPP_NUMBER = "5517996657737";

// ====== Helpers ======
const $ = (sel) => document.querySelector(sel);

let landingBootEl = null;

const startLandingBoot = (message = "Preparando a experiencia Cotai.") => {
    document.body.classList.add("app-booting");
    if (!landingBootEl) {
        landingBootEl = document.createElement("div");
        landingBootEl.className = "app-boot";
        landingBootEl.innerHTML = `
      <div class="app-boot-card" role="status">
        <div class="app-boot-loader" aria-hidden="true">
          <div class="loader">
            <div class="loader__bar"></div>
            <div class="loader__bar"></div>
            <div class="loader__bar"></div>
            <div class="loader__bar"></div>
            <div class="loader__bar"></div>
            <div class="loader__ball"></div>
          </div>
        </div>
        <div class="app-boot-copy">
          <strong>Carregando Cotai</strong>
          <span id="landingBootMessage">${message}</span>
        </div>
      </div>
    `;
        document.body.appendChild(landingBootEl);
    }
    const msg = landingBootEl.querySelector("#landingBootMessage");
    if (msg) msg.textContent = message;
    landingBootEl.classList.remove("is-hidden");
};

const finishLandingBoot = () => {
    if (!landingBootEl) return;
    landingBootEl.classList.add("is-hidden");
    document.body.classList.remove("app-booting");
};

startLandingBoot("Carregando componentes da landing page.");

const openWhatsApp = (text) => {
    const url = `https://wa.me/${WHATSAPP_NUMBER}?text=${encodeURIComponent(text)}`;
    window.location.href = url;
};

const generateLandingPedidoId = () => {
    const now = new Date();
    const yyyy = now.getFullYear();
    const mm = String(now.getMonth() + 1).padStart(2, "0");
    const dd = String(now.getDate()).padStart(2, "0");
    const hh = String(now.getHours()).padStart(2, "0");
    const mi = String(now.getMinutes()).padStart(2, "0");
    const ss = String(now.getSeconds()).padStart(2, "0");
    return `WEB-${yyyy}${mm}${dd}${hh}${mi}${ss}`;
};

// ====== Itens dinâmicos (materiais) ======
const itemsWrap = document.getElementById("itemsWrap");
const addItemBtn = document.getElementById("addItemBtn");
const MAX_ITEMS = 40;
const limitHint = document.getElementById("limitHint");
const itemsCountEl = document.getElementById("itemsCount");

const getItemsCount = () => {
    if (!itemsWrap) return 0;
    return itemsWrap.querySelectorAll("[data-item]").length;
};

const updateItemsCounter = () => {
    if (itemsCountEl) {
        itemsCountEl.textContent = `Itens: ${getItemsCount()}`;
    }
};

const createItemRow = () => {
    const row = document.createElement("div");
    row.className = "item-row";
    row.setAttribute("data-item", "");

    row.innerHTML = `
    <select class="item-material" required>
      <option value="" disabled selected>Material</option>
      <option value="Cimento">Cimento</option>
      <option value="Aço (Vergalhão)">Aço (Vergalhão)</option>
      <option value="Areia">Areia</option>
      <option value="Brita">Brita</option>
      <option value="Bloco / Tijolo">Bloco / Tijolo</option>
      <option value="Outro">Outro</option>
    </select>
    <input class="item-qty" type="text" placeholder="Quantidade (ex: 200 sacos)" required />
    <button type="button" class="mini-btn danger" data-remove title="Remover">✕</button>
  `;
    return row;
};

const updateLimitUI = () => {
    const count = getItemsCount();
    const reached = count >= MAX_ITEMS;
    if (addItemBtn) addItemBtn.disabled = reached;
    if (limitHint) limitHint.style.display = reached ? "block" : "none";
    updateItemsCounter();
};

if (addItemBtn && itemsWrap) {
    addItemBtn.addEventListener("click", () => {
        if (getItemsCount() >= MAX_ITEMS) return;
        const row = createItemRow();
        itemsWrap.appendChild(row);
        row.scrollIntoView({ behavior: "smooth", block: "nearest" });
        updateLimitUI();
    });

    itemsWrap.addEventListener("click", (e) => {
        const btn = e.target.closest("[data-remove]");
        if (!btn) return;
        const all = itemsWrap.querySelectorAll("[data-item]");
        if (all.length <= 1) return;
        btn.closest("[data-item]").remove();
        updateLimitUI();
    });
}

// ====== Form -> WhatsApp ======
const form = $("#quoteForm");

if (form) {
    form.addEventListener("submit", (e) => {
        e.preventDefault();

        // 1. Coleta de dados
        const formData = new FormData(form);
        const nome = formData.get("nome");
        const empresa = formData.get("empresa");
        const prazo = formData.get("prazo");
        const local = formData.get("local");
        const obs = formData.get("obs");

        const rows = [...itemsWrap.querySelectorAll("[data-item]")];
        
        const itens = rows.map((r, idx) => {
            const material = r.querySelector(".item-material").value.trim();
            const quantidade = r.querySelector(".item-qty").value.trim();
            if (!material || !quantidade) return null;
            return `  ${idx + 1}) ${material} — ${quantidade}`;
        }).filter(Boolean);

        if (itens.length === 0) {
            alert("Adicione pelo menos 1 material com quantidade.");
            return;
        }

        // 2. Formatação da mensagem com a tag oculta para o Bot
        const pedidoId = generateLandingPedidoId();
        const msg = `#COTAI
PedidoID: ${pedidoId}
Nome: ${nome}
Empresa: ${empresa}
Itens:
${itens.join("\n")}
Prazo desejado: ${prazo}
Local de entrega: ${local}
${obs ? `Observações: ${obs}` : ""}`;

        // 3. Envia direto para o WhatsApp
        closeModal();
        openWhatsApp(msg);
    });
}

// ====== Botão WhatsApp no footer ======
const openWhatsFooter = $("#openWhatsFooter");
if (openWhatsFooter) {
    openWhatsFooter.addEventListener("click", (e) => {
        e.preventDefault();
        openWhatsApp("Olá! Quero tirar uma dúvida sobre a Cotai.");
    });
}

// ====== UI / Modals / Menu ======
const yearEl = $("#year");
if (yearEl) yearEl.textContent = new Date().getFullYear();

const hamburger = $("#hamburger");
const mobileMenu = $("#mobileMenu");
if (hamburger && mobileMenu) {
    hamburger.addEventListener("click", () => mobileMenu.classList.toggle("show"));
}

const modal = $("#quoteModal");
const openModal = () => {
    if (!modal) {
        openWhatsApp("Olá! Quero agendar uma demonstração da Cotai com um pedido real da minha operação.");
        return;
    }
    modal.classList.add("show");
    document.body.style.overflow = "hidden";
    updateLimitUI();
};
const closeModal = () => {
    if (!modal) return;
    modal.classList.remove("show");
    document.body.style.overflow = "";
};

document.querySelectorAll("[data-demo-source]").forEach((button) => {
    button.addEventListener("click", () => {
        const source = button.getAttribute("data-demo-source") || "site";
        if (modal) {
            openModal();
            return;
        }
        openWhatsApp(`Olá! Quero agendar uma demonstração da Cotai. Origem: ${source}. Quero validar com uma demanda real da operação.`);
    });
});

const closeBtn = $("#closeModal");
if (closeBtn) closeBtn.addEventListener("click", closeModal);

const backdrop = $("#closeModalBackdrop");
if (backdrop) backdrop.addEventListener("click", closeModal);

window.addEventListener("load", () => {
    window.setTimeout(finishLandingBoot, 350);
}, { once: true });
