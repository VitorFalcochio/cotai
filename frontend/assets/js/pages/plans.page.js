import { LOGIN_PATH } from "../config.js";
import { getProfile, isAdminRole, requireAuth } from "../auth.js";
import { getPlanConfig, PLAN_ORDER } from "../planCatalog.js";
import { assertSupabaseConfigured, supabase } from "../supabaseClient.js";
import { initSidebar, runPageBoot, setLoading, showFeedback } from "../ui.js";

let currentPlanKey = "silver";
let currentSubscriptionId = "";
let canManagePlan = false;
let currentCompanyId = "";

function applyPlanState() {
  PLAN_ORDER.forEach((planKey) => {
    const card = document.querySelector(`[data-plan-card="${planKey}"]`);
    const button = document.querySelector(`[data-plan-select="${planKey}"]`);
    const isCurrent = planKey === currentPlanKey;
    card?.classList.toggle("is-current-plan", isCurrent);
    if (!button) return;
    button.disabled = isCurrent || !canManagePlan;
    button.textContent = isCurrent ? "Plano atual" : getPlanConfig(planKey).ctaLabel;
  });
}

async function loadPlanContext(userId) {
  const profile = await getProfile(userId);
  if (!profile?.company_id) {
    throw new Error("Seu perfil ainda nao esta vinculado a uma empresa.");
  }

  currentCompanyId = profile.company_id;
  canManagePlan = isAdminRole(profile.role);

  const { data: company, error: companyError } = await supabase
    .from("companies")
    .select("id, plan")
    .eq("id", currentCompanyId)
    .maybeSingle();
  if (companyError) throw companyError;

  const { data: subscriptions, error: subscriptionError } = await supabase
    .from("billing_subscriptions")
    .select("id, plan, status, created_at")
    .eq("company_id", currentCompanyId)
    .order("created_at", { ascending: false })
    .limit(1);

  if (subscriptionError && !String(subscriptionError.message || "").toLowerCase().includes("does not exist")) {
    throw subscriptionError;
  }

  const latestSubscription = subscriptions?.[0] || null;
  currentSubscriptionId = latestSubscription?.id || "";
  currentPlanKey = company?.plan || latestSubscription?.plan || profile.plan || "silver";
  applyPlanState();

  if (!canManagePlan) {
    showFeedback("#plansFeedback", "Somente owner ou admin pode alterar o plano da empresa.");
  }
}

async function savePlanSelection(planKey, button) {
  if (!currentCompanyId) return;
  if (planKey === currentPlanKey) return;

  const plan = getPlanConfig(planKey);
  setLoading(button, true, plan.ctaLabel, "Atualizando...");
  showFeedback("#plansFeedback", "", true);

  try {
    const { error: companyError } = await supabase
      .from("companies")
      .update({ plan: plan.key })
      .eq("id", currentCompanyId);
    if (companyError) throw companyError;

    const payload = {
      company_id: currentCompanyId,
      plan: plan.key,
      status: "active",
      monthly_amount: plan.price,
      mrr: plan.price,
      amount_cents: plan.price * 100,
    };

    if (currentSubscriptionId) {
      const { error: billingError } = await supabase
        .from("billing_subscriptions")
        .update(payload)
        .eq("id", currentSubscriptionId);
      if (billingError && !String(billingError.message || "").toLowerCase().includes("does not exist")) {
        throw billingError;
      }
    } else {
      const { data: inserted, error: billingInsertError } = await supabase
        .from("billing_subscriptions")
        .insert(payload)
        .select("id")
        .single();
      if (billingInsertError && !String(billingInsertError.message || "").toLowerCase().includes("does not exist")) {
        throw billingInsertError;
      }
      currentSubscriptionId = inserted?.id || currentSubscriptionId;
    }

    currentPlanKey = plan.key;
    applyPlanState();
    showFeedback("#plansFeedback", `Plano ${plan.label} ativado com sucesso.`, false);
  } catch (error) {
    showFeedback("#plansFeedback", error.message || "Nao foi possivel atualizar o plano.");
  } finally {
    setLoading(button, false, planKey === currentPlanKey ? "Plano atual" : plan.ctaLabel);
  }
}

async function init() {
  assertSupabaseConfigured();
  const session = await requireAuth(LOGIN_PATH);
  if (!session) return;

  initSidebar();
  await loadPlanContext(session.user.id);

  document.querySelectorAll("[data-plan-select]").forEach((button) => {
    button.addEventListener("click", async () => {
      if (!canManagePlan) {
        showFeedback("#plansFeedback", "Somente owner ou admin pode alterar o plano da empresa.");
        return;
      }
      await savePlanSelection(button.dataset.planSelect, button);
    });
  });
}

runPageBoot(init, { loadingMessage: "Carregando configuracao dos planos." }).catch((error) => {
  showFeedback("#plansFeedback", error.message || "Nao foi possivel carregar os planos.");
});
