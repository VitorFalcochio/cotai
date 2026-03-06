import { LOGIN_PATH } from "../config.js";
import { requireAuth, signOut } from "../auth.js";
import { buildWhatsappMessage, createRequest } from "../requests.js";
import { copyText, initSidebar, openWhatsApp, qs, setLoading, setText, showFeedback, toggleHidden } from "../ui.js";

async function init() {
  const session = await requireAuth(LOGIN_PATH);
  if (!session) return;

  initSidebar();

  qs("#logoutButton")?.addEventListener("click", async () => {
    await signOut();
    window.location.replace(LOGIN_PATH);
  });

  const form = qs("#newRequestForm");
  const submitButton = qs("#newRequestSubmit");
  const resultCard = qs("#requestResult");
  const messageBox = qs("#requestMessage");
  const requestIdBox = qs("#generatedRequestId");
  const copyButton = qs("#copyRequestMessage");
  const whatsappButton = qs("#openRequestWhats");

  let whatsappMessage = "";

  form?.addEventListener("submit", async (event) => {
    event.preventDefault();
    showFeedback("#newRequestFeedback", "");
    setLoading(submitButton, true, "Salvar pedido");

    const data = new FormData(form);
    const items = String(data.get("items") || "")
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);

    try {
      const request = await createRequest({
        customerName: String(data.get("customer_name") || "").trim(),
        deliveryMode: String(data.get("delivery_mode") || "").trim(),
        deliveryLocation: String(data.get("delivery_location") || "").trim(),
        notes: String(data.get("notes") || "").trim(),
        items
      });

      whatsappMessage = buildWhatsappMessage(request, items);
      setText(requestIdBox, request.requestCode);
      setText(messageBox, whatsappMessage);
      toggleHidden(resultCard, false);
      form.reset();
      showFeedback("#newRequestFeedback", "Pedido salvo com sucesso.", false);
    } catch (error) {
      showFeedback("#newRequestFeedback", error.message || "Nao foi possivel salvar o pedido.");
    } finally {
      setLoading(submitButton, false, "Salvar pedido");
    }
  });

  copyButton?.addEventListener("click", async () => {
    if (!whatsappMessage) return;

    try {
      await copyText(whatsappMessage);
      copyButton.textContent = "Copiado";
      window.setTimeout(() => {
        copyButton.textContent = "Copiar mensagem";
      }, 1200);
    } catch (error) {
      showFeedback("#newRequestFeedback", error.message || "Nao foi possivel copiar a mensagem.");
    }
  });

  whatsappButton?.addEventListener("click", () => {
    if (whatsappMessage) openWhatsApp(whatsappMessage);
  });
}

init().catch((error) => {
  showFeedback("#newRequestFeedback", error.message || "Erro ao iniciar a tela de pedido.");
});
