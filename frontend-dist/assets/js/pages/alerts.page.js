import { bootClientWorkspace } from "../clientPage.js";
import { runPageBoot, setText, showFeedback } from "../ui.js";

async function init() {
  const boot = await bootClientWorkspace();
  if (!boot) return;

  try {
    setText("#alertsTitle", `Alertas de ${boot.companyLabel}`);
  } catch (error) {
    showFeedback("#alertsFeedback", error.message || "Nao foi possivel carregar alertas.");
  }
}

runPageBoot(init, { loadingMessage: "Verificando alertas da operacao." });
