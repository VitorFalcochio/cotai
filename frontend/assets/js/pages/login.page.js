import { DASHBOARD_PATH } from "../config.js";
import { redirectIfAuthenticated, signIn } from "../auth.js";
import { getReadableError, qs, runPageBoot, setLoading, showFeedback } from "../ui.js";

const PENDING_SIGNUP_EMAIL_KEY = "cotai_pending_signup_email";

async function init() {
  await redirectIfAuthenticated(DASHBOARD_PATH);

  const form = qs("#loginForm");
  const submitButton = qs("#loginSubmit");
  const emailInput = qs("#email");

  const pendingEmail = String(sessionStorage.getItem(PENDING_SIGNUP_EMAIL_KEY) || "").trim();
  if (pendingEmail && emailInput && !emailInput.value) {
    emailInput.value = pendingEmail;
  }

  form?.addEventListener("submit", async (event) => {
    event.preventDefault();
    showFeedback("#loginFeedback", "");
    setLoading(submitButton, true, "Entrar", "Entrando...");

    const data = new FormData(form);
    const email = String(data.get("email") || "").trim();
    const password = String(data.get("password") || "");

    try {
      await signIn(email, password);
      sessionStorage.removeItem(PENDING_SIGNUP_EMAIL_KEY);
      window.location.replace(DASHBOARD_PATH);
    } catch (error) {
      showFeedback("#loginFeedback", getReadableError(error, "Nao foi possivel entrar."));
      setLoading(submitButton, false, "Entrar");
    }
  });
}

runPageBoot(init, { loadingMessage: "Preparando acesso seguro." }).catch((error) => {
  showFeedback("#loginFeedback", getReadableError(error, "Erro ao iniciar a tela de login."));
});
