// ====== CONFIG ======
// Troque para o seu número (com DDI +55). Ex: 5511999999999
const WHATSAPP_NUMBER = "5517996657737";

// ====== Helpers ======
const $ = (sel) => document.querySelector(sel);

const openWhatsApp = (text) => {
    const url = `https://wa.me/${WHATSAPP_NUMBER}?text=${encodeURIComponent(text)}`;
    // Evita bloqueio de popup em alguns navegadores
    window.location.href = url;
};

// ====== Itens dinâmicos (materiais) ======
const itemsWrap = document.getElementById("itemsWrap");
const addItemBtn = document.getElementById("addItemBtn");

const MAX_ITEMS = 40; // ajuste entre 30–50 como preferir
const limitHint = document.getElementById("limitHint");
const sendListWhatsBtn = document.getElementById("sendListWhatsBtn");

const getItemsCount = () => {
    if (!itemsWrap) return 0;
    return itemsWrap.querySelectorAll("[data-item]").length;
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

    <input class="item-qty" type="text" placeholder="Quantidade (ex: 200 sacos / 1.5 ton)" required />

    <button type="button" class="mini-btn danger" data-remove title="Remover">✕</button>
  `;

    return row;
};

const buildCurrentListMessage = () => {
    // tenta puxar dados já preenchidos no form
    const form = document.querySelector("#quoteForm");
    const data = form ? new FormData(form) : null;

    const nome = data?.get("nome")?.toString().trim() || "(não informado)";
    const empresa = data?.get("empresa")?.toString().trim() || "(não informada)";
    const prazo = data?.get("prazo")?.toString().trim() || "(não informado)";
    const local = data?.get("local")?.toString().trim() || "(não informado)";
    const obs = data?.get("obs")?.toString().trim() || "";

    // pega itens já adicionados
    const rows = itemsWrap ? [...itemsWrap.querySelectorAll("[data-item]")] : [];
    const itens = rows
        .map((r, idx) => {
            const material = r.querySelector(".item-material")?.value?.trim();
            const quantidade = r.querySelector(".item-qty")?.value?.trim();

            if (!material && !quantidade) return null; // linha vazia
            return `  ${idx + 1}) ${material || "(material não selecionado)"} — ${quantidade || "(quantidade não informada)"
                }`;
        })
        .filter(Boolean);

    return `Olá! Minha lista ficou grande no formulário, vou enviar por aqui para agilizar:

• Nome: ${nome}
• Empresa: ${empresa}
• Itens:
${itens.length ? itens.join("\n") : "  (nenhum item preenchido)"}
• Prazo desejado: ${prazo}
• Local de entrega: ${local}
${obs ? `• Observações: ${obs}` : ""}

Pode me retornar com as melhores opções (preço e prazo)?`;
};

const updateLimitUI = () => {
    const count = getItemsCount();
    const reached = count >= MAX_ITEMS;

    if (addItemBtn) addItemBtn.disabled = reached;

    if (limitHint) {
        limitHint.style.display = reached ? "block" : "none";
    }

    if (sendListWhatsBtn) {
        sendListWhatsBtn.disabled = !reached; // só habilita quando atingir o limite
    }
};

if (addItemBtn && itemsWrap) {
    addItemBtn.addEventListener("click", () => {
        const count = getItemsCount();

        if (count >= MAX_ITEMS) {
            updateLimitUI();
            return;
        }

        const row = createItemRow();
        itemsWrap.appendChild(row);

        // rolar até o novo item
        row.scrollIntoView({ behavior: "smooth", block: "nearest" });

        updateLimitUI();
    });

    // Delegação para remover
    itemsWrap.addEventListener("click", (e) => {
        const btn = e.target.closest("[data-remove]");
        if (!btn) return;

        const row = btn.closest("[data-item]");
        const all = itemsWrap.querySelectorAll("[data-item]");

        // não deixa ficar sem nenhum item
        if (all.length <= 1) return;

        row.remove();
        updateLimitUI();
    });

    // estado inicial
    updateLimitUI();
}

// Botão do aviso -> manda lista no WhatsApp puxando o que já foi preenchido
if (sendListWhatsBtn) {
    sendListWhatsBtn.addEventListener("click", () => {
        const msg = buildCurrentListMessage();
        openWhatsApp(msg);
    });
}

// ====== Ano no footer ======
const yearEl = $("#year");
if (yearEl) yearEl.textContent = new Date().getFullYear();

// ====== Menu mobile ======
const hamburger = $("#hamburger");
const mobileMenu = $("#mobileMenu");

if (hamburger && mobileMenu) {
    hamburger.addEventListener("click", () => {
        mobileMenu.classList.toggle("show");
    });

    mobileMenu.querySelectorAll("a").forEach((a) => {
        a.addEventListener("click", () => mobileMenu.classList.remove("show"));
    });
}

// ====== Modal ======
const modal = $("#quoteModal");
const closeModalBtn = $("#closeModal");
const closeBackdrop = $("#closeModalBackdrop");

const openModal = () => {
    if (!modal) return;
    modal.classList.add("show");
    modal.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";

    // garante estado do limite ao abrir
    updateLimitUI();
};

const closeModal = () => {
    if (!modal) return;
    modal.classList.remove("show");
    modal.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
};

[
    "#openQuoteTop",
    "#openQuoteHero",
    "#openQuoteCard",
    "#openQuoteHow",
    "#openQuoteBottom",
    "#openQuoteMobile",
].forEach((id) => {
    const el = $(id);
    if (el) el.addEventListener("click", openModal);
});

if (closeModalBtn) closeModalBtn.addEventListener("click", closeModal);
if (closeBackdrop) closeBackdrop.addEventListener("click", closeModal);

document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && modal?.classList.contains("show")) closeModal();
});

// ====== Form -> WhatsApp ======
const form = $("#quoteForm");

if (form) {
    form.addEventListener("submit", (e) => {
        e.preventDefault();

        const data = new FormData(form);
        const nome = data.get("nome");
        const empresa = data.get("empresa");
        const prazo = data.get("prazo");
        const local = data.get("local");
        const obs = data.get("obs");

        // pega todos os itens preenchidos (com material + quantidade)
        const rows = itemsWrap ? [...itemsWrap.querySelectorAll("[data-item]")] : [];
        const itens = rows
            .map((r, idx) => {
                const material = r.querySelector(".item-material")?.value?.trim();
                const quantidade = r.querySelector(".item-qty")?.value?.trim();

                if (!material || !quantidade) return null;
                return `  ${idx + 1}) ${material} — ${quantidade}`;
            })
            .filter(Boolean);

        if (itens.length === 0) {
            alert("Adicione pelo menos 1 material com quantidade.");
            return;
        }

        const msg = `Olá! Quero uma cotação.

• Nome: ${nome}
• Empresa: ${empresa}
• Itens:
${itens.join("\n")}
• Prazo desejado: ${prazo}
• Local de entrega: ${local}
${obs ? `• Observações: ${obs}` : ""}

Pode me retornar com as melhores opções (preço e prazo) para esses itens?`;

        closeModal();
        openWhatsApp(msg);
    });
}

// ====== Botão WhatsApp no footer ======
const openWhatsFooter = $("#openWhatsFooter");
if (openWhatsFooter) {
    openWhatsFooter.addEventListener("click", (e) => {
        e.preventDefault();
        openWhatsApp("Olá! Quero entender como funciona a cotação centralizada de cimento e aço.");
    });
}
