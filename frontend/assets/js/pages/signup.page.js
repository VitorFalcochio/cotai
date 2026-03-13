import { DASHBOARD_PATH } from "../config.js";
import { redirectIfAuthenticated, signUp } from "../auth.js";
import { getReadableError, qs, runPageBoot, setLoading, showFeedback } from "../ui.js";

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

    if (password !== confirmPassword) {
      showFeedback("#signupFeedback", "As senhas não conferem.");
      setLoading(submitButton, false, "Criar conta");
      return;
    }

    try {
      const result = await signUp({ email, password, companyName });

      if (result.session) {
        window.location.replace(DASHBOARD_PATH);
        return;
      }

      showFeedback(
        "#signupFeedback",
        "Conta criada. Verifique seu e-mail para confirmar o acesso.",
        false
      );
      form.reset();
    } catch (error) {
      showFeedback("#signupFeedback", getReadableError(error, "Não foi possível criar a conta."));
    } finally {
      setLoading(submitButton, false, "Criar conta");
    }
  });
}

runPageBoot(init, { loadingMessage: "Preparando cadastro da Cotai." }).catch((error) => {
  showFeedback("#signupFeedback", getReadableError(error, "Erro ao iniciar a tela de cadastro."));
});
