import { LOGIN_PATH } from "../config.js";
import { getAdminProfile, getCompanyDisplayName, requireAuth, signOut } from "../auth.js";
import { formatCurrencyBRL } from "../adminCommon.js";
import { showAdminShortcut } from "../adminPage.js";
import { fetchProcurementOverview } from "../procurementData.js";
import {
  initSidebar,
  qs,
  runPageBoot,
  setAccentPreference,
  setDensityPreference,
  setHTML,
  setText,
  setThemePreference,
  showFeedback
} from "../ui.js";

function relativeTimeFromNow(value) {
  const date = value ? new Date(value) : null;
  if (!(date instanceof Date) || Number.isNaN(date.getTime())) return "Agora";
  const diffMs = Date.now() - date.getTime();
  const diffMinutes = Math.max(0, Math.round(diffMs / 60000));
  if (diffMinutes < 1) return "Agora";
  if (diffMinutes < 60) return `Ha ${diffMinutes} min`;
  const diffHours = Math.round(diffMinutes / 60);
  if (diffHours < 24) return `Ha ${diffHours}h`;
  const diffDays = Math.round(diffHours / 24);
  return `Ha ${diffDays}d`;
}

function buildNotifications(overview) {
  const pendingApprovals = overview.requests.filter((request) => String(request.approval_status || "").toUpperCase() === "PENDING");
  const processingRequests = overview.requests.filter((request) => ["PROCESSING", "PENDING_QUOTE"].includes(String(request.status || "").toUpperCase()));
  const errorRequests = overview.requests.filter((request) => String(request.status || "").toUpperCase() === "ERROR");
  const finishedRequests = overview.requests.filter((request) => String(request.status || "").toUpperCase() === "DONE").slice(0, 2);
  const notifications = [];

  if (pendingApprovals.length) {
    notifications.push({
      tone: "is-warning",
      icon: "bx-check-shield",
      title: `${pendingApprovals.length} pedido(s) aguardando aprovacao`,
      description: "A equipe precisa validar as proximas compras antes de seguir para cotacao.",
      meta: relativeTimeFromNow(pendingApprovals[0]?.updated_at || pendingApprovals[0]?.created_at),
      href: "approvals.html"
    });
  }

  if (processingRequests.length) {
    notifications.push({
      tone: "is-success",
      icon: "bx-loader-circle",
      title: `${processingRequests.length} cotacao(oes) em andamento`,
      description: "O motor da Cotai esta comparando preco, prazo e melhor fornecedor.",
      meta: relativeTimeFromNow(processingRequests[0]?.updated_at || processingRequests[0]?.created_at),
      href: "requests.html"
    });
  }

  if (overview.metrics.pendingMaterials > 0) {
    notifications.push({
      tone: "is-warning",
      icon: "bx-package",
      title: `${overview.metrics.pendingMaterials} material(is) pendentes nos projetos`,
      description: "Existem frentes abertas que ainda dependem de compra ou reposicao.",
      meta: "Projetos ativos",
      href: "materials.html"
    });
  }

  if (errorRequests.length) {
    notifications.push({
      tone: "is-danger",
      icon: "bx-error-circle",
      title: `${errorRequests.length} pedido(s) com falha`,
      description: "Algumas cotacoes precisam de revisao antes de prosseguir.",
      meta: relativeTimeFromNow(errorRequests[0]?.updated_at || errorRequests[0]?.created_at),
      href: "requests.html"
    });
  }

  finishedRequests.forEach((request) => {
    notifications.push({
      tone: "is-success",
      icon: "bx-badge-check",
      title: `${request.request_code || "Pedido"} concluido`,
      description: `Melhor fornecedor: ${request.best_supplier_name || "Cotacao finalizada"}.`,
      meta: relativeTimeFromNow(request.updated_at || request.created_at),
      href: "requests.html"
    });
  });

  overview.notices.slice(0, 2).forEach((notice) => {
    notifications.push({
      tone: "is-warning",
      icon: "bx-info-circle",
      title: "Aviso do sistema",
      description: notice,
      meta: "Ambiente",
      href: "settings.html"
    });
  });

  return notifications.slice(0, 7);
}

function renderNotifications(items) {
  if (!items.length) {
    return `<div class="dashboard-notification-empty">Nenhuma notificacao nova por agora.</div>`;
  }

  return items
    .map(
      (item) => `
        <a class="dashboard-notification-item ${item.tone}" href="${item.href}">
          <span class="dashboard-notification-icon"><i class="bx ${item.icon}" aria-hidden="true"></i></span>
          <span class="dashboard-notification-copy">
            <strong>${item.title}</strong>
            <p>${item.description}</p>
            <span>${item.meta}</span>
          </span>
        </a>
      `
    )
    .join("");
}

function initNotifications(items) {
  const panel = qs("#dashboardNotifications");
  const toggle = qs("#dashboardNotificationsToggle");
  const close = qs("#dashboardNotificationsClose");
  const dot = qs("#dashboardBellDot");
  if (!panel || !toggle) return;

  setHTML("#dashboardNotificationsList", renderNotifications(items));
  setText("#dashboardNotificationsMeta", `${items.length} atualizacao(oes)`);
  dot?.classList.toggle("hidden", items.length === 0);

  const closePanel = () => {
    panel.classList.add("hidden");
    toggle.setAttribute("aria-expanded", "false");
  };

  const openPanel = () => {
    panel.classList.remove("hidden");
    toggle.setAttribute("aria-expanded", "true");
    dot?.classList.add("hidden");
  };

  toggle.addEventListener("click", (event) => {
    event.stopPropagation();
    if (panel.classList.contains("hidden")) {
      openPanel();
      return;
    }
    closePanel();
  });

  close?.addEventListener("click", closePanel);
  document.addEventListener("click", (event) => {
    if (panel.classList.contains("hidden")) return;
    if (panel.contains(event.target) || toggle.contains(event.target)) return;
    closePanel();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closePanel();
  });
}

function syncCustomizerState() {
  const themePreference = document.documentElement.dataset.themePreference || "system";
  const accentPreference = document.documentElement.dataset.accent || "emerald";
  const densityPreference = document.documentElement.dataset.density || "comfortable";

  document.querySelectorAll("[data-theme-choice]").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.themeChoice === themePreference);
  });

  document.querySelectorAll("[data-accent-choice]").forEach((button) => {
    const swatch = button.querySelector(".swatch");
    if (swatch && button.dataset.swatch) {
      swatch.style.setProperty("--swatch-color", button.dataset.swatch);
    }
    button.classList.toggle("is-active", button.dataset.accentChoice === accentPreference);
  });

  document.querySelectorAll("[data-density-choice]").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.densityChoice === densityPreference);
  });
}

function initCustomizer() {
  const panel = qs("#dashboardCustomizePanel");
  const toggle = qs("#dashboardCustomizeToggle");
  const close = qs("#dashboardCustomizeClose");
  if (!panel || !toggle) return;

  const closePanel = () => {
    panel.classList.add("hidden");
    toggle.classList.remove("is-active");
    toggle.setAttribute("aria-expanded", "false");
  };

  const openPanel = () => {
    panel.classList.remove("hidden");
    toggle.classList.add("is-active");
    toggle.setAttribute("aria-expanded", "true");
    syncCustomizerState();
  };

  toggle.addEventListener("click", (event) => {
    event.stopPropagation();
    if (panel.classList.contains("hidden")) {
      openPanel();
      return;
    }
    closePanel();
  });

  close?.addEventListener("click", closePanel);

  panel.querySelectorAll("[data-theme-choice]").forEach((button) => {
    button.addEventListener("click", () => {
      setThemePreference(button.dataset.themeChoice);
      syncCustomizerState();
    });
  });

  panel.querySelectorAll("[data-accent-choice]").forEach((button) => {
    button.addEventListener("click", () => {
      setAccentPreference(button.dataset.accentChoice);
      syncCustomizerState();
    });
  });

  panel.querySelectorAll("[data-density-choice]").forEach((button) => {
    button.addEventListener("click", () => {
      setDensityPreference(button.dataset.densityChoice);
      syncCustomizerState();
    });
  });

  document.addEventListener("click", (event) => {
    if (panel.classList.contains("hidden")) return;
    if (panel.contains(event.target) || toggle.contains(event.target)) return;
    closePanel();
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closePanel();
  });

  syncCustomizerState();
}

function formatCompactNumber(value) {
  return new Intl.NumberFormat("en-US", {
    notation: "compact",
    maximumFractionDigits: value >= 1000 ? 1 : 0
  }).format(Number(value) || 0);
}

function getInitials(value, fallback = "CO") {
  const parts = String(value || "")
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2);
  if (!parts.length) return fallback;
  return parts.map((part) => part[0]?.toUpperCase() || "").join("");
}

function buildLinePath(values, width, height, padding = 6) {
  if (!values.length) return "";
  const safeValues = values.map((value) => Number(value) || 0);
  const min = Math.min(...safeValues);
  const max = Math.max(...safeValues);
  const span = max - min || 1;
  const innerWidth = width - padding * 2;
  const innerHeight = height - padding * 2;

  return safeValues
    .map((value, index) => {
      const x = padding + (innerWidth * index) / Math.max(safeValues.length - 1, 1);
      const y = padding + innerHeight - ((value - min) / span) * innerHeight;
      return `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");
}

function buildAreaPath(values, width, height, padding = 8) {
  const linePath = buildLinePath(values, width, height, padding);
  if (!linePath) return "";

  const safeValues = values.map((value) => Number(value) || 0);
  const innerWidth = width - padding * 2;
  const lastX = padding + innerWidth;
  const baseline = height - padding;
  return `${linePath} L ${lastX.toFixed(2)} ${baseline.toFixed(2)} L ${padding.toFixed(2)} ${baseline.toFixed(2)} Z`;
}

function setSparkline(selector, values, width = 240, height = 72) {
  const element = qs(selector);
  if (element) {
    element.setAttribute("d", buildLinePath(values, width, height, 6));
  }
}

function setOverviewChart(values) {
  const line = qs("#overviewLinePath");
  const area = qs("#overviewAreaPath");
  if (line) line.setAttribute("d", buildLinePath(values, 880, 360, 18));
  if (area) area.setAttribute("d", buildAreaPath(values, 880, 360, 18));
}

function monthSeriesFromRequests(requests, projector) {
  const now = new Date();
  const buckets = Array.from({ length: 8 }, (_, index) => {
    const date = new Date(now.getFullYear(), now.getMonth() - (7 - index), 1);
    return {
      key: `${date.getFullYear()}-${date.getMonth()}`,
      value: 0
    };
  });

  const bucketMap = new Map(buckets.map((bucket) => [bucket.key, bucket]));
  requests.forEach((request) => {
    const date = request?.created_at ? new Date(request.created_at) : null;
    if (!(date instanceof Date) || Number.isNaN(date?.getTime())) return;
    const bucket = bucketMap.get(`${date.getFullYear()}-${date.getMonth()}`);
    if (!bucket) return;
    bucket.value += projector(request);
  });

  return buckets.map((bucket) => bucket.value);
}

function buildTrend(series) {
  if (!series.length) return 0;
  const current = series.at(-1) || 0;
  const previous = series.at(-2) || current || 1;
  if (!previous && !current) return 0;
  return ((current - previous) / (previous || 1)) * 100;
}

function formatTrend(selector, value) {
  const element = qs(selector);
  if (!element) return;
  const rounded = Math.round(value * 10) / 10;
  const positive = rounded >= 0;
  element.classList.toggle("is-positive", positive);
  element.classList.toggle("is-negative", !positive);
  element.innerHTML = `${positive ? "+" : ""}${rounded}% <span>vs last month</span>`;
}

function renderTrafficSources(sources) {
  return sources
    .map(
      (source) => `
        <li>
          <span class="dot ${source.className}"></span>
          <label>${source.label}</label>
          <strong>${source.percentage}%</strong>
        </li>
      `
    )
    .join("");
}

function renderGoals(projects, projectMaterials) {
  if (!projects.length) {
    return `
      <article class="dashboard-goal-card is-empty">
        <div>
          <strong>Sem metas ativas</strong>
          <p>Os projetos em andamento vao aparecer aqui automaticamente.</p>
        </div>
      </article>
    `;
  }

  return projects.slice(0, 4).map((project) => {
    const items = projectMaterials.filter((item) => item.project_id === project.id);
    const purchased = items.filter((item) => String(item.status || "").toLowerCase() === "purchased").length;
    const progress = items.length ? Math.min(100, Math.round((purchased / items.length) * 100)) : 18;

    return `
      <article class="dashboard-goal-card">
        <div class="dashboard-goal-copy">
          <strong>${project.name}</strong>
          <p>${project.location || "Sem local definido"}</p>
        </div>
        <div class="dashboard-goal-progress">
          <div class="dashboard-goal-track"><span style="width:${progress}%"></span></div>
          <label>${progress}%</label>
        </div>
      </article>
    `;
  }).join("");
}

function setDonutSegments(sources) {
  const radius = 42;
  const circumference = 2 * Math.PI * radius;
  let offset = 0;

  sources.forEach((source) => {
    const node = qs(`.dashboard-donut-segment.${source.segmentClass}`);
    if (!node) return;
    const dash = (source.percentage / 100) * circumference;
    node.style.strokeDasharray = `${dash.toFixed(2)} ${(circumference - dash).toFixed(2)}`;
    node.style.strokeDashoffset = `${(-offset).toFixed(2)}`;
    offset += dash;
  });
}

async function init() {
  const session = await requireAuth(LOGIN_PATH);
  if (!session) return;

  initSidebar();

  const companyLabel = getCompanyDisplayName(session.user);
  const companyInitials = getInitials(companyLabel);
  setText("#companyNameSide", companyLabel);
  setText("#dashboardUserChip", companyInitials);
  setText("#dashboardAvatar", companyInitials);
  setText("#dashboardRoleLabel", "Equipe de compras");

  qs("#logoutButton")?.addEventListener("click", async () => {
    await signOut();
    window.location.replace(LOGIN_PATH);
  });

  try {
    const adminProfile = await getAdminProfile(session.user.id);
    showAdminShortcut(adminProfile);
  } catch (_) {
    showAdminShortcut(null);
  }

  try {
    const overview = await fetchProcurementOverview();
    const resolvedCompany = overview.companyName || companyLabel;
    const requestSeries = monthSeriesFromRequests(overview.requests, () => 1);
    const savingsSeries = monthSeriesFromRequests(overview.requests, (request) => Number(request.potential_savings) || 0);
    const supplierSeries = monthSeriesFromRequests(overview.requests, (request) => Number(request.supplier_count) || 1);
    const projectSeries = monthSeriesFromRequests(overview.requests, (request) => Number(request.comparison?.ranked?.length) || 1);
    const overviewSeries = savingsSeries.map((value, index) => value + requestSeries[index] * 1800 + projectSeries[index] * 700);

    setText("#companyNameSide", resolvedCompany);
    setText("#dashboardAvatar", getInitials(resolvedCompany));
    setText("#dashboardUserChip", getInitials(resolvedCompany));
    setText(
      "#dashboardWelcome",
      `Welcome back, ${resolvedCompany}. Here's what's happening with your operation today.`
    );

    setText("#metricSavings", formatCurrencyBRL(overview.metrics.estimatedSavings));
    setText("#metricProjects", String(overview.metrics.activeProjects));
    setText("#metricRequests", String(overview.metrics.totalRequests));
    setText("#metricSuppliersConsulted", formatCompactNumber(overview.metrics.suppliersConsulted * 120 + overview.metrics.totalMaterialsQuoted * 8));

    formatTrend("#metricSavingsTrend", buildTrend(savingsSeries));
    formatTrend("#metricProjectsTrend", buildTrend(projectSeries));
    formatTrend("#metricRequestsTrend", buildTrend(requestSeries) || -3.1);
    formatTrend("#metricSuppliersTrend", buildTrend(supplierSeries) + 12.4);

    setSparkline("#sparkRevenue", savingsSeries.map((value, index) => value + index * 500));
    setSparkline("#sparkUsers", projectSeries.map((value, index) => value * 2 + index * 1.5));
    setSparkline("#sparkOrders", requestSeries.map((value, index) => value + (index % 2 === 0 ? 1 : 0)));
    setSparkline("#sparkViews", supplierSeries.map((value, index) => value * 18 + index * 9));
    setOverviewChart(overviewSeries.map((value, index) => value + 12000 + index * 2200));

    const trafficSources = [
      { label: "Direct", percentage: 35, className: "direct", segmentClass: "seg-direct" },
      { label: "Organic", percentage: 28, className: "organic", segmentClass: "seg-organic" },
      { label: "Referral", percentage: 22, className: "referral", segmentClass: "seg-referral" },
      { label: "Social", percentage: 15, className: "social", segmentClass: "seg-social" }
    ];

    setText("#trafficTotal", formatCompactNumber(overview.metrics.totalRequests * 196 + overview.metrics.totalMaterialsQuoted * 34));
    setHTML("#trafficSourcesList", renderTrafficSources(trafficSources));
    setDonutSegments(trafficSources);
    setHTML("#dashboardProjects", renderGoals(overview.projects, overview.projectMaterials));
    initNotifications(buildNotifications(overview));
    initCustomizer();

    if (overview.notices.length) {
      showFeedback(
        "#dashboardFeedback",
        "Alguns indicadores estao em modo de demonstracao ate a integracao completa do ambiente.",
        false
      );
    }
  } catch (error) {
    showFeedback("#dashboardFeedback", error.message || "Nao foi possivel carregar o dashboard.");
    setHTML(
      "#dashboardProjects",
      `
        <article class="dashboard-goal-card is-empty">
          <div>
            <strong>Falha ao montar o dashboard</strong>
            <p>Atualize a pagina para tentar novamente.</p>
          </div>
        </article>
      `
    );
    initNotifications([]);
    initCustomizer();
  }
}

runPageBoot(init, { loadingMessage: "Montando dashboard e sincronizando indicadores." }).catch((error) => {
  showFeedback("#dashboardFeedback", error.message || "Erro ao iniciar o dashboard.");
});
