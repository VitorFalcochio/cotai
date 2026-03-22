import { DASHBOARD_PATH } from "../config.js";
import { redirectIfAuthenticated, signUp } from "../auth.js";
import { getReadableError, qs, runPageBoot, setLoading, showFeedback } from "../ui.js";

const PENDING_SIGNUP_EMAIL_KEY = "cotai_pending_signup_email";

async function init() {
  await redirectIfAuthenticated(DASHBOARD_PATH);

  const form = qs("#signupForm");
  const submitButton = qs("#signupSubmit");

  form?.addEventListener("submit", async (event) => {
    event.preventDefault();
    showFeedback("#signupFeedback", "");
    setLoading(submitButton, true, "Criar conta", "Criando conta...");

    const data = new FormData(form);
    const companyName = String(data.get("company_name") || "").trim();
    const email = String(data.get("email") || "").trim();
    const password = String(data.get("password") || "");
    const confirmPassword = String(data.get("confirm_password") || "");

    if (companyName.length < 3) {
      showFeedback("#signupFeedback", "Informe o nome da empresa com pelo menos 3 caracteres.");
      setLoading(submitButton, false, "Criar conta");
      return;
    }

    if (password !== confirmPassword) {
      showFeedback("#signupFeedback", "As senhas nao conferem.");
      setLoading(submitButton, false, "Criar conta");
      return;
    }

    try {
      const result = await signUp({ email, password, companyName });

      if (result.session) {
        window.location.replace(DASHBOARD_PATH);
        return;
      }

      sessionStorage.setItem(PENDING_SIGNUP_EMAIL_KEY, email);
      showFeedback("#signupFeedback", `Conta criada para ${email}. Verifique seu e-mail e depois entre para continuar.`, false);
      form.reset();
    } catch (error) {
      showFeedback("#signupFeedback", getReadableError(error, "Nao foi possivel criar a conta."));
    } finally {
      setLoading(submitButton, false, "Criar conta");
    }
  });
}

runPageBoot(init, { loadingMessage: "Preparando cadastro da Cotai." }).catch((error) => {
  showFeedback("#signupFeedback", getReadableError(error, "Erro ao iniciar a tela de cadastro."));
});
