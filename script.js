// ====== CONFIG ======
const WHATSAPP_NUMBER = "5517996657737";

// ====== Helpers ======
const $ = (sel) => document.querySelector(sel);

const openWhatsApp = (text) => {
    const url = `https://wa.me/${WHATSAPP_NUMBER}?text=${encodeURIComponent(text)}`;
    window.location.href = url;
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
            const material = r.querySelector(".item-material")?.value?.trim();
            const quantidade = r.querySelector(".item-qty")?.value?.trim();
            if (!material || !quantidade) return null;
            return `  ${idx + 1}) ${material} — ${quantidade}`;
        }).filter(Boolean);

        if (itens.length === 0) {
            alert("Adicione pelo menos 1 material com quantidade.");
            return;
        }

        // 2. Formatação da mensagem com a tag oculta para o Bot
        const msg = `#COTAR_NOVA
Olá! Quero uma cotação automática.

• Nome: ${nome}
• Empresa: ${empresa}
• Itens:
${itens.join("\n")}
• Prazo desejado: ${prazo}
• Local de entrega: ${local}
${obs ? `• Observações: ${obs}` : ""}

Pode me retornar com as melhores opções (preço e prazo)?`;

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
    modal?.classList.add("show");
    document.body.style.overflow = "hidden";
    updateLimitUI();
};
const closeModal = () => {
    modal?.classList.remove("show");
    document.body.style.overflow = "";
};

["#openQuoteTop", "#openQuoteHero", "#openQuoteCard", "#openQuoteBottom", "#openQuoteMobile"].forEach(id => {
    const el = $(id);
    if (el) el.addEventListener("click", openModal);
});

const closeBtn = $("#closeModal");
if (closeBtn) closeBtn.addEventListener("click", closeModal);

const backdrop = $("#closeModalBackdrop");
if (backdrop) backdrop.addEventListener("click", closeModal);