// ====== CONFIG ======
// Troque para o seu número (com DDI +55). Ex: 5511999999999
const WHATSAPP_NUMBER = "5517996657737";

// ====== Helpers ======
const $ = (sel) => document.querySelector(sel);
const openWhatsApp = (text) => {
  const url = `https://wa.me/${WHATSAPP_NUMBER}?text=${encodeURIComponent(text)}`;
  window.open(url, "_blank");
};

// ====== Ano no footer ======
$("#year").textContent = new Date().getFullYear();

// ====== Menu mobile ======
const hamburger = $("#hamburger");
const mobileMenu = $("#mobileMenu");

hamburger.addEventListener("click", () => {
  mobileMenu.classList.toggle("show");
});

mobileMenu.querySelectorAll("a").forEach((a) => {
  a.addEventListener("click", () => mobileMenu.classList.remove("show"));
});

// ====== Modal ======
const modal = $("#quoteModal");
const closeModalBtn = $("#closeModal");
const closeBackdrop = $("#closeModalBackdrop");

const openModal = () => {
  modal.classList.add("show");
  modal.setAttribute("aria-hidden", "false");
  document.body.style.overflow = "hidden";
};
const closeModal = () => {
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

closeModalBtn.addEventListener("click", closeModal);
closeBackdrop.addEventListener("click", closeModal);

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && modal.classList.contains("show")) closeModal();
});

// ====== Form -> WhatsApp ======
const form = $("#quoteForm");

form.addEventListener("submit", (e) => {
  e.preventDefault();

  const data = new FormData(form);
  const nome = data.get("nome");
  const empresa = data.get("empresa");
  const material = data.get("material");
  const quantidade = data.get("quantidade");
  const prazo = data.get("prazo");
  const local = data.get("local");
  const obs = data.get("obs");

  const msg =
`Olá! Quero uma cotação.

• Nome: ${nome}
• Empresa: ${empresa}
• Material: ${material}
• Quantidade: ${quantidade}
• Prazo desejado: ${prazo}
• Local de entrega: ${local}
${obs ? `• Observações: ${obs}` : ""}

Pode me retornar com as melhores opções (preço e prazo)?`;

  closeModal();
  openWhatsApp(msg);
});

// ====== Botão WhatsApp no footer ======
const openWhatsFooter = $("#openWhatsFooter");
openWhatsFooter.addEventListener("click", (e) => {
  e.preventDefault();
  openWhatsApp("Olá! Quero entender como funciona a cotação centralizada de cimento e aço.");
});
