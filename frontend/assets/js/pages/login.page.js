import { DASHBOARD_PATH } from "../config.js";
import { redirectIfAuthenticated, signIn } from "../auth.js";
import { getReadableError, qs, runPageBoot, setLoading, showFeedback } from "../ui.js";

async function init() {
  await redirectIfAuthenticated(DASHBOARD_PATH);

  const form = qs("#loginForm");
  const submitButton = qs("#loginSubmit");

  form?.addEventListener("submit", async (event) => {
    event.preventDefault();
    showFeedback("#loginFeedback", "");
    setLoading(submitButton, true, "Entrar", "Entrando...");

    const data = new FormData(form);
    const email = String(data.get("email") || "").trim();
    const password = String(data.get("password") || "");

    try {
      await signIn(email, password);
      window.location.replace(DASHBOARD_PATH);
    } catch (error) {
      showFeedback("#loginFeedback", getReadableError(error, "Não foi possível entrar."));
      setLoading(submitButton, false, "Entrar");
    }
  });
}

runPageBoot(init, { loadingMessage: "Preparando acesso seguro." }).catch((error) => {
  showFeedback("#loginFeedback", getReadableError(error, "Erro ao iniciar a tela de login."));
});
