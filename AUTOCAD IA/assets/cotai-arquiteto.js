(function () {
  const APP_NAME = "CotaiStudio";
  const APP_CHAT_NAME = "Studio IA";
  const STORAGE_KEY = "cotai-studio-projects-v1";
  const SIDEBAR_KEY = "cotai-studio-sidebar-collapsed";
  const app = document.getElementById("app");

  const ARCH_STYLES = [
    ["Moderno", "Linhas retas, telhado embutido, grandes vaos."],
    ["Contemporaneo", "Mistura de materiais, design atual e fluido."],
    ["Classico", "Elegante, simetria, telhados aparentes."],
    ["Rustico", "Madeira, pedra, tijolo aparente, aconchego."],
    ["Minimalista", "Menos e mais, funcionalidade, cores neutras."],
  ];

  const PREFERENCES = [
    "Cozinha integrada",
    "Area gourmet",
    "Escritorio em casa",
    "Home theater",
    "Lavanderia separada",
    "Varanda gourmet",
    "Closet master",
    "Banheira na suite",
    "Pe direito duplo",
    "Iluminacao natural",
  ];

  const QUICK_PROMPTS = [
    "Deixe a cozinha maior",
    "Adicione um lavabo",
    "Quero mais privacidade na suite",
    "Reduza corredores",
  ];

  const PLAN_PALETTES = [
    ["#c8ccd3", "#f6d8bf", "#efc2ba", "#bde0d4", "#d6f0ed", "#a7bee0", "#bfd6ef", "#bac0f0", "#94d8d3"],
    ["#c8ccd3", "#f4d6bb", "#efb9a6", "#afe0cb", "#d4f2ea", "#a7c3e5", "#bdd7f1", "#c6beef", "#9fd7d1"],
    ["#c8ccd3", "#f6d9c2", "#eec0aa", "#bee2d2", "#dff2eb", "#9db9db", "#b7d1ed", "#cfc8f2", "#9ed8cf"],
  ];

  const state = {
    projects: loadProjects(),
    wizardStep: 1,
    draft: initialDraft(),
    tab: "plans",
    detailZoom: 1,
    activePlanLevels: {},
    toast: "",
    sidebarCollapsed: loadSidebarCollapsed(),
  };

  ensureSeedProject();
  render();
  window.addEventListener("hashchange", render);

  function initialDraft() {
    return {
      name: "",
      style: "Contemporaneo",
      lot: { width: 10, depth: 25 },
      targetArea: 150,
      requirements: {
        floors: 1,
        bedrooms: 3,
        suites: 1,
        bathrooms: 2,
        garageSpots: 2,
        hasPool: false,
      },
      preferences: [],
    };
  }

  function loadProjects() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : [];
    } catch (error) {
      return [];
    }
  }

  function persistProjects() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state.projects));
  }

  function loadSidebarCollapsed() {
    try {
      return localStorage.getItem(SIDEBAR_KEY) === "1";
    } catch (error) {
      return false;
    }
  }

  function persistSidebarCollapsed() {
    localStorage.setItem(SIDEBAR_KEY, state.sidebarCollapsed ? "1" : "0");
  }

  function ensureSeedProject() {
    if (state.projects.length) return;
    const seed = createProjectFromDraft({
      name: "Casa TEste",
      style: "Contemporaneo",
      lot: { width: 10, depth: 25 },
      targetArea: 150,
      requirements: {
        floors: 2,
        bedrooms: 3,
        suites: 1,
        bathrooms: 2,
        garageSpots: 2,
        hasPool: true,
      },
      preferences: ["Cozinha integrada", "Area gourmet", "Iluminacao natural"],
    });
    seed.status = "ready";
    seed.plans = generatePlans(seed);
    state.projects = [seed];
    persistProjects();
  }

  function currentRoute() {
    const hash = window.location.hash || "#dashboard";
    const clean = hash.replace(/^#/, "");
    const parts = clean.split("/");
    if (parts[0] === "project" && parts[1]) return { name: "project", projectId: parts[1] };
    if (parts[0] === "plan" && parts[1] && parts[2]) return { name: "plan", projectId: parts[1], planId: parts[2] };
    if (parts[0] === "projects") return { name: "projects" };
    if (parts[0] === "new-project") return { name: "new-project" };
    return { name: "dashboard" };
  }

  function navigate(hash) {
    window.location.hash = hash;
  }

  function createProjectFromDraft(draft) {
    const id = `proj_${Date.now().toString(36).slice(-6)}`;
    const createdAt = new Date().toISOString();
    return {
      id,
      shortId: id.replace("proj_", "") + "...",
      name: draft.name || "Novo Projeto",
      style: draft.style,
      lot: draft.lot,
      targetArea: draft.targetArea,
      requirements: draft.requirements,
      preferences: draft.preferences,
      status: "draft",
      createdAt,
      plans: [],
      chat: [{ role: "ai", text: "Posso ajustar a distribuicao da planta e comentar cada escolha arquitetonica." }],
    };
  }

  function generatePlans(project) {
    if (project.brainSource && Array.isArray(project.brainSource.variants) && project.brainSource.variants.length) {
      return buildPlansFromBrainVariants(project.brainSource);
    }

    if (project.brainSource && Array.isArray(project.brainSource.rooms) && project.brainSource.rooms.length) {
      return buildPlansFromBrainProject(project.brainSource);
    }

    const totalArea = Number(project.targetArea || 150);
    const baseRooms = [
      ["Garagem", 27.0],
      ["Hall", 13.0],
      ["Sala de Estar", 14.4],
      ["Sala de Jantar", 10.8],
      ["Cozinha", 10.8],
      ["Area de Servico", 6.3],
      ["Banheiro (Social)", 4.0],
      ["Varanda", 14.4],
      ["Suite", 16.0],
      ["Banheiro (Suite)", 6.0],
      ["Quarto 1", 12.0],
      ["Quarto 2", 12.0],
    ];
    const variants = [
      {
        id: "planta-a",
        name: "Planta A - Layout Compacto",
        description: "Layout otimizado para aproveitamento maximo de espaco. Ambientes bem resolvidos e foco em eficiencia.",
        notes: "Conceito compacto, com setorizacao clara e menor perda de area em circulacao.",
        tips: [
          "Ideal para terrenos mais estreitos e aproveitamento maximo.",
          "A distribuicao reduz percursos internos do dia a dia.",
          "A area social pode receber integracao maior com varanda.",
        ],
      },
      {
        id: "planta-b",
        name: "Planta B - Ambientes Integrados",
        description: "Conceito integrado com fluxo continuo entre sala, jantar e cozinha. Ideal para convivio.",
        notes: "Conceito integrado com fluxo continuo entre sala, jantar e cozinha. Ideal para familias que valorizam convivio.",
        tips: [
          "Voce pode pedir alteracoes especificas pelo chat.",
          "O tamanho dos comodos ja respeita o codigo de obras padrao.",
          "A exportacao em PDF gera a prancha em formato A3 escalada.",
        ],
      },
      {
        id: "planta-c",
        name: "Planta C - Distribuicao Classica",
        description: "Distribuicao tradicional com separacao mais clara entre setores social, intimo e servico.",
        notes: "Opcao com leitura mais classica, separando melhor a area intima da area de recepcao.",
        tips: [
          "Boa para quem prefere privacidade na ala intima.",
          "A cozinha pode ser reconfigurada para receber ilha ou mesa central.",
          "Varanda e gourmet podem ser ampliados na versao final.",
        ],
      },
    ];

    return variants.map((variant, index) => ({
      id: variant.id,
      title: variant.name,
      totalArea,
      description: variant.description,
      notes: variant.notes,
      tips: variant.tips,
      scale: "1m = 30px",
      rooms: buildPlanRooms(baseRooms, PLAN_PALETTES[index]),
    }));
  }

  function buildPlanRooms(baseRooms, palette) {
    const layouts = [
      { x: 90, y: 34, w: 190, h: 90 },
      { x: 34, y: 34, w: 84, h: 90 },
      { x: 34, y: 138, w: 82, h: 106 },
      { x: 118, y: 138, w: 70, h: 106 },
      { x: 188, y: 138, w: 92, h: 106 },
      { x: 34, y: 244, w: 68, h: 72 },
      { x: 102, y: 244, w: 86, h: 72 },
      { x: 188, y: 244, w: 92, h: 110 },
      { x: 34, y: 354, w: 118, h: 118 },
      { x: 152, y: 354, w: 52, h: 118 },
      { x: 34, y: 472, w: 120, h: 96 },
      { x: 154, y: 472, w: 126, h: 96 },
    ];

    return baseRooms.map((item, index) => ({
      name: item[0],
      area: item[1],
      color: palette[index % palette.length],
      ...layouts[index],
    }));
  }

  function buildPlansFromBrainProject(brainProject) {
    const levels = [...new Set((brainProject.rooms || []).map((room) => Number(room.level || 0)))].sort((a, b) => a - b);
    const plans = levels.map((level, index) => {
      const levelRooms = (brainProject.rooms || []).filter((room) => Number(room.level || 0) === level);
      const palette = PLAN_PALETTES[index % PLAN_PALETTES.length];
      return {
        id: `brain-level-${level}`,
        title: level === 0 ? "Planta IA - Térreo" : `Planta IA - Pavimento ${level + 1}`,
        totalArea: levelRooms.reduce((sum, room) => sum + Number(room.width || 0) * Number(room.depth || 0), 0),
        description: brainProject.design_strategy
          ? `Estudo gerado pelo cérebro arquitetônico com estratégia ${brainProject.design_strategy.replaceAll("_", " ")}.`
          : "Estudo arquitetônico estruturado a partir do pipeline semântico da IA.",
        notes: (brainProject.processing_notes || []).join(" ") || "Planta importada do pipeline real da AUTOCAD IA.",
        tips: brainProject.constraints
          ? Object.entries(brainProject.constraints).map(([key, value]) => `${key}: ${String(value)}`)
          : ["Você pode continuar refinando esta planta pelo chat."],
        scale: "1m = 30px",
        rooms: toPlanRoomsFromBrainRooms(levelRooms, palette),
      };
    });

    return plans.length ? plans : generatePlans({ targetArea: brainProject.constraints?.target_area || 150 });
  }

  function buildPlansFromBrainVariants(payload) {
    return (payload.variants || []).map((variant, index) => buildPlanFromBrainVariant(variant, index));
  }

  function buildPlanFromBrainVariant(variant, index) {
    const brainProject = variant.project || {};
    const levels = [...new Set((brainProject.rooms || []).map((room) => Number(room.level || 0)))].sort((a, b) => a - b);
    const fallbackLevels = levels.length ? levels : [0];
    const palette = PLAN_PALETTES[index % PLAN_PALETTES.length];
    const selectedLevel = fallbackLevels[0];
    const selectedRooms = (brainProject.rooms || []).filter((room) => Number(room.level || 0) === selectedLevel);

    return {
      id: `variant-${variant.id || index + 1}`,
      title: `Planta ${String.fromCharCode(65 + index)} - ${variant.label || "Solucao IA"}`,
      totalArea: Number(
        (
          brainProject.constraints?.target_area ||
          (brainProject.rooms || []).reduce((sum, room) => sum + Number(room.width || 0) * Number(room.depth || 0), 0)
        ).toFixed(1)
      ),
      description: brainProject.design_strategy
        ? `Solucao ${String(variant.label || "").toLowerCase()} baseada na estrategia ${brainProject.design_strategy.replaceAll("_", " ")}.`
        : `Solucao arquitetonica gerada pelo solver de variantes do ${APP_NAME}.`,
      notes: (brainProject.processing_notes || []).join(" ") || "Variante gerada pelo solver arquitetonico.",
      tips: buildVariantTips(variant, brainProject),
      scale: "1m = 30px",
      layoutKind: "brain",
      strategy: brainProject.design_strategy || "",
      processingNotes: brainProject.processing_notes || [],
      constraints: brainProject.constraints || {},
      qualityScore: variant.quality_score || null,
      plot: { width: Number(brainProject.width || 12), depth: Number(brainProject.depth || 8) },
      rooms: toPlanRoomsFromBrainRooms(selectedRooms, palette),
      levels: fallbackLevels.map((level, levelIndex) => ({
        id: `level-${level}`,
        level,
        label: level === 0 ? "Terreo" : `Pavimento ${levelIndex + 1}`,
        rooms: toPlanRoomsFromBrainRooms(
          (brainProject.rooms || []).filter((room) => Number(room.level || 0) === level),
          PLAN_PALETTES[(index + levelIndex) % PLAN_PALETTES.length]
        ),
      })),
    };
  }

  function buildVariantTips(variant, brainProject) {
    const tips = [];
    if (variant.quality_score?.overall_score) {
      tips.push(`Score geral desta solucao: ${variant.quality_score.overall_score}.`);
    }
    if (variant.quality_score?.layout_integrity_score) {
      tips.push(`Integridade geometrica: ${variant.quality_score.layout_integrity_score}.`);
    }
    if (brainProject.constraints?.wet_stack_bias) {
      tips.push(`Wet stack configurado em modo ${brainProject.constraints.wet_stack_bias}.`);
    }
    if (brainProject.constraints?.private_distribution) {
      tips.push(`Distribuicao intima prioriza ${brainProject.constraints.private_distribution.replaceAll("_", " ")}.`);
    }
    tips.push("Use o chat para pedir ajustes em corredores, escadas e areas molhadas.");
    return tips;
  }

  function toPlanRoomsFromBrainRooms(rooms, palette) {
    if (!rooms.length) return [];
    const minX = Math.min(...rooms.map((room) => Number(room.x || 0)));
    const minY = Math.min(...rooms.map((room) => Number(room.y || 0)));
    const maxX = Math.max(...rooms.map((room) => Number(room.x || 0) + Number(room.width || 0)));
    const maxY = Math.max(...rooms.map((room) => Number(room.y || 0) + Number(room.depth || 0)));
    const innerWidth = 250;
    const innerHeight = 534;
    const scale = Math.min(innerWidth / Math.max(maxX - minX, 1), innerHeight / Math.max(maxY - minY, 1));
    const offsetX = 34;
    const offsetY = 34;

    return rooms.map((room, index) => ({
      name: room.name,
      area: Number((Number(room.width || 0) * Number(room.depth || 0)).toFixed(1)),
      color: palette[index % palette.length],
      role: room.role || "",
      zone: room.zone || "",
      cluster: room.cluster || "",
      adjacency: room.adjacency || [],
      sourceWidth: Number(room.width || 0),
      sourceDepth: Number(room.depth || 0),
      sourceX: Number(room.x || 0),
      sourceY: Number(room.y || 0),
      x: offsetX + (Number(room.x || 0) - minX) * scale,
      y: offsetY + (Number(room.y || 0) - minY) * scale,
      w: Math.max(Number(room.width || 0) * scale, 28),
      h: Math.max(Number(room.depth || 0) * scale, 24),
    }));
  }

  function createProjectFromBrainPayload(payload) {
    if (payload && Array.isArray(payload.variants) && payload.variants.length) {
      return createProjectFromBrainVariantsPayload(payload);
    }

    const createdAt = new Date().toISOString();
    const id = `proj_${Date.now().toString(36).slice(-6)}`;
    const targetArea = Number(payload.constraints?.target_area || payload.rooms?.reduce((sum, room) => {
      return sum + Number(room.width || 0) * Number(room.depth || 0);
    }, 0) || 180);
    const style = payload.design_strategy ? payload.design_strategy.replaceAll("_", " ") : "Estudo IA";

    return {
      id,
      shortId: id.replace("proj_", "") + "...",
      name: payload.title || "Projeto importado",
      style,
      lot: { width: Number(payload.width || 12), depth: Number(payload.depth || 25) },
      targetArea: Number(targetArea.toFixed(1)),
      requirements: {
        floors: Number(payload.floors || 1),
        bedrooms: (payload.rooms || []).filter((room) => /quarto|suite/i.test(room.name || "")).length,
        suites: (payload.rooms || []).filter((room) => /suite/i.test(room.name || "")).length,
        bathrooms: (payload.rooms || []).filter((room) => /banheiro|lavabo|wc/i.test(room.name || "")).length,
        garageSpots: (payload.rooms || []).some((room) => /garagem/i.test(room.name || "")) ? 2 : 0,
        hasPool: (payload.rooms || []).some((room) => /piscina/i.test(room.name || "")),
      },
      preferences: [],
      status: "ready",
      createdAt,
      brainSource: payload,
      plans: buildPlansFromBrainProject(payload).map((plan) => ({
        ...plan,
        layoutKind: "brain",
        strategy: payload.design_strategy || "",
        processingNotes: payload.processing_notes || [],
        constraints: payload.constraints || {},
        qualityScore: payload.quality_score || null,
        plot: { width: Number(payload.width || 12), depth: Number(payload.depth || 8) },
      })),
      chat: [
        { role: "ai", text: "Projeto importado do cérebro arquitetônico. Posso comentar a setorização, a circulação e os núcleos molhados." },
      ],
    };
  }

  function createProjectFromBrainVariantsPayload(payload) {
    const createdAt = new Date().toISOString();
    const id = `proj_${Date.now().toString(36).slice(-6)}`;
    const first = payload.variants[0]?.project || {};
    const allRooms = payload.variants.flatMap((variant) => variant.project?.rooms || []);
    const targetArea = Number(
      (
        first.constraints?.target_area ||
        allRooms.reduce((sum, room) => sum + Number(room.width || 0) * Number(room.depth || 0), 0) / Math.max(payload.variants.length, 1) ||
        180
      ).toFixed(1)
    );

    return {
      id,
      shortId: id.replace("proj_", "") + "...",
      name: payload.title || first.title || "Projeto importado",
      style: first.design_strategy ? first.design_strategy.replaceAll("_", " ") : "Estudo IA",
      lot: { width: Number(first.width || 12), depth: Number(first.depth || 25) },
      targetArea,
      requirements: {
        floors: Number(first.floors || 1),
        bedrooms: (first.rooms || []).filter((room) => /quarto|suite/i.test(room.name || "")).length,
        suites: (first.rooms || []).filter((room) => /suite/i.test(room.name || "")).length,
        bathrooms: (first.rooms || []).filter((room) => /banheiro|lavabo|wc/i.test(room.name || "")).length,
        garageSpots: (first.rooms || []).some((room) => /garagem/i.test(room.name || "")) ? 2 : 0,
        hasPool: (first.rooms || []).some((room) => /piscina/i.test(room.name || "")),
      },
      preferences: [],
      status: "ready",
      createdAt,
      brainSource: payload,
      plans: buildPlansFromBrainVariants(payload),
      chat: [
        { role: "ai", text: "Importei tres solucoes reais do solver arquitetonico. Posso comparar circulacao, areas molhadas e estrategia de implantacao." },
      ],
    };
  }

  function getDisplayedPlanRooms(plan) {
    if (!Array.isArray(plan.levels) || !plan.levels.length) {
      return plan.rooms || [];
    }
    const activeLevel = state.activePlanLevels[plan.id] ?? plan.levels[0].level;
    const current = plan.levels.find((level) => level.level === activeLevel) || plan.levels[0];
    return current.rooms || [];
  }

  function getDisplayedPlanLevel(plan) {
    if (!Array.isArray(plan.levels) || !plan.levels.length) return null;
    const activeLevel = state.activePlanLevels[plan.id] ?? plan.levels[0].level;
    return plan.levels.find((level) => level.level === activeLevel) || plan.levels[0];
  }

  function icon(name) {
    const icons = {
      dashboard: '<svg class="icon" viewBox="0 0 24 24" fill="none"><rect x="3" y="3" width="7" height="7" rx="1.5" stroke="currentColor" stroke-width="1.8"/><rect x="14" y="3" width="7" height="7" rx="1.5" stroke="currentColor" stroke-width="1.8"/><rect x="3" y="14" width="7" height="7" rx="1.5" stroke="currentColor" stroke-width="1.8"/><rect x="14" y="14" width="7" height="7" rx="1.5" stroke="currentColor" stroke-width="1.8"/></svg>',
      plusSquare: '<svg class="icon" viewBox="0 0 24 24" fill="none"><rect x="3" y="3" width="18" height="18" rx="3" stroke="currentColor" stroke-width="1.8"/><path d="M12 8v8M8 12h8" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>',
      folder: '<svg class="icon" viewBox="0 0 24 24" fill="none"><path d="M3 8.8C3 7.806 3.806 7 4.8 7h4.287c.477 0 .934-.19 1.272-.528l.87-.87A1.8 1.8 0 0 1 12.501 5H19.2c.994 0 1.8.806 1.8 1.8v9.4A1.8 1.8 0 0 1 19.2 18H4.8A1.8 1.8 0 0 1 3 16.2V8.8Z" stroke="currentColor" stroke-width="1.8"/></svg>',
      gear: '<svg class="icon" viewBox="0 0 24 24" fill="none"><path d="M12 8.6A3.4 3.4 0 1 0 12 15.4A3.4 3.4 0 1 0 12 8.6Z" stroke="currentColor" stroke-width="1.8"/><path d="M19.4 12a7.54 7.54 0 0 0-.1-1.24l2.02-1.58-1.9-3.3-2.4.98a7.85 7.85 0 0 0-2.16-1.24L14.5 2h-5l-.36 3.62c-.78.28-1.5.7-2.16 1.24l-2.4-.98-1.9 3.3 2.02 1.58A7.54 7.54 0 0 0 4.6 12c0 .42.04.83.1 1.24l-2.02 1.58 1.9 3.3 2.4-.98c.66.54 1.38.96 2.16 1.24L9.5 22h5l.36-3.62c.78-.28 1.5-.7 2.16-1.24l2.4.98 1.9-3.3-2.02-1.58c.06-.41.1-.82.1-1.24Z" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/></svg>',
      help: '<svg class="icon" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.8"/><path d="M9.4 9.3a2.85 2.85 0 1 1 5.22 1.6c-.6.78-1.54 1.18-2.11 1.8-.36.39-.51.76-.51 1.6" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/><circle cx="12" cy="17.2" r="1" fill="currentColor"/></svg>',
      spark: '<svg class="icon" viewBox="0 0 24 24" fill="none"><path d="m12 3 1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3Z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/><path d="M19 4v2M20 5h-2M5 17v2M6 18H4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>',
      pencil: '<svg class="icon" viewBox="0 0 24 24" fill="none"><path d="M4 20h4l10.5-10.5a2.12 2.12 0 0 0-3-3L5 17v3Z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/></svg>',
      layers: '<svg class="icon" viewBox="0 0 24 24" fill="none"><path d="m12 4 8 4-8 4-8-4 8-4Z" stroke="currentColor" stroke-width="1.8"/><path d="m4 12 8 4 8-4" stroke="currentColor" stroke-width="1.8"/><path d="m4 16 8 4 8-4" stroke="currentColor" stroke-width="1.8"/></svg>',
      chat: '<svg class="icon" viewBox="0 0 24 24" fill="none"><path d="M7 17.5H5a2 2 0 0 1-2-2V6.8A2.8 2.8 0 0 1 5.8 4h12.4A2.8 2.8 0 0 1 21 6.8v8.4A2.8 2.8 0 0 1 18.2 18H11l-4 3v-3.5Z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/></svg>',
      star: '<svg class="icon" viewBox="0 0 24 24" fill="none"><path d="m12 4.8 2.3 4.66 5.14.75-3.72 3.63.88 5.13L12 16.6l-4.6 2.42.88-5.13L4.56 10.2l5.14-.75L12 4.8Z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/></svg>',
      share: '<svg class="icon" viewBox="0 0 24 24" fill="none"><circle cx="18" cy="5" r="2.5" stroke="currentColor" stroke-width="1.8"/><circle cx="6" cy="12" r="2.5" stroke="currentColor" stroke-width="1.8"/><circle cx="18" cy="19" r="2.5" stroke="currentColor" stroke-width="1.8"/><path d="m8.2 10.9 7.6-4.3M8.2 13.1l7.6 4.3" stroke="currentColor" stroke-width="1.8"/></svg>',
      download: '<svg class="icon" viewBox="0 0 24 24" fill="none"><path d="M12 4v9M8.5 10.5 12 14l3.5-3.5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/><path d="M4 18.5h16" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>',
      zoomIn: '<svg class="icon" viewBox="0 0 24 24" fill="none"><circle cx="10.5" cy="10.5" r="5.5" stroke="currentColor" stroke-width="1.8"/><path d="M14.5 14.5 20 20M10.5 8v5M8 10.5h5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>',
      zoomOut: '<svg class="icon" viewBox="0 0 24 24" fill="none"><circle cx="10.5" cy="10.5" r="5.5" stroke="currentColor" stroke-width="1.8"/><path d="M14.5 14.5 20 20M8 10.5h5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>',
      expand: '<svg class="icon" viewBox="0 0 24 24" fill="none"><path d="M8 4H4v4M20 8V4h-4M16 20h4v-4M4 16v4h4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>',
      home: '<svg class="icon" viewBox="0 0 24 24" fill="none"><path d="m4 11.2 8-6.2 8 6.2v8.3a1.5 1.5 0 0 1-1.5 1.5H5.5A1.5 1.5 0 0 1 4 19.5v-8.3Z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/><path d="M9 21v-5.5h6V21" stroke="currentColor" stroke-width="1.8"/></svg>',
      back: '<svg class="icon" viewBox="0 0 24 24" fill="none"><path d="m14.5 5.5-6 6 6 6" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>',
      send: '<svg class="icon" viewBox="0 0 24 24" fill="none"><path d="m3 20 18-8L3 4l2.5 7.2L16 12l-10.5.8L3 20Z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/></svg>',
      panel: '<svg class="icon" viewBox="0 0 24 24" fill="none"><rect x="3.5" y="4" width="17" height="16" rx="3" stroke="currentColor" stroke-width="1.8"/><path d="M9 4.8v14.4M12.8 8h4.2M12.8 12h4.2M12.8 16h2.8" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>',
    };
    return icons[name] || "";
  }

  function render() {
    const route = currentRoute();
    app.innerHTML = `
      <div class="architect-shell ${state.sidebarCollapsed ? "is-sidebar-collapsed" : ""}">
        ${renderSidebar(route)}
        <main class="architect-main">${renderRoute(route)}</main>
      </div>
      <input type="file" id="brainImportInput" accept=".json,application/json" hidden />
      <div class="toast ${state.toast ? "is-visible" : ""}" id="toast">${state.toast || ""}</div>
    `;
    bindGlobalEvents(route);
  }

  function renderSidebar(route) {
    return `
      <aside class="architect-sidebar ${state.sidebarCollapsed ? "is-collapsed" : ""}">
        <div class="architect-brand">
          <div class="brand-lockup">
            <div class="brand-mark"></div>
            <div class="brand-copy"><strong>${APP_NAME}</strong></div>
          </div>
          <button class="sidebar-toggle" data-sidebar-toggle aria-label="Alternar barra lateral">
            ${icon("panel")}
          </button>
        </div>
        <div class="sidebar-group">
          <p class="sidebar-caption">Menu</p>
          <div class="sidebar-nav">
            ${sidebarLink("dashboard", "Dashboard", route.name === "dashboard", "dashboard")}
            ${sidebarLink("new-project", "Novo Projeto", route.name === "new-project", "plusSquare")}
            ${sidebarLink("projects", "Meus Projetos", route.name === "projects" || route.name === "project" || route.name === "plan", "folder")}
          </div>
        </div>
        <div class="sidebar-group" style="align-self:end;">
          <div class="sidebar-support">
            ${sidebarLink("settings", "Configuracoes", false, "gear", true)}
            ${sidebarLink("help", "Ajuda", false, "help", true)}
          </div>
        </div>
      </aside>
    `;
  }

  function sidebarLink(hash, label, active, iconName, disabled) {
    return `<button class="sidebar-link ${active ? "is-active" : ""}" data-nav="${hash}" ${disabled ? 'data-disabled="true"' : ""}>${icon(iconName)}<span>${label}</span></button>`;
  }

  function renderRoute(route) {
    if (route.name === "dashboard") return renderDashboard();
    if (route.name === "new-project") return renderWizard();
    if (route.name === "projects") return renderProjects();
    if (route.name === "project") return renderProjectDetail(route.projectId);
    if (route.name === "plan") return renderPlanDetail(route.projectId, route.planId);
    return renderDashboard();
  }

  function renderDashboard() {
    const finished = state.projects.filter((project) => project.plans.length).length;
    const recent = state.projects.slice().sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt)).slice(0, 1);

    return `
      <section class="screen">
        <div class="page-head">
          <div>
            <h1>Bem-vindo ao ${APP_NAME}</h1>
            <p>Crie plantas arquitetonicas inteligentes em segundos com IA.</p>
          </div>
          <div class="page-actions">
            <button class="btn btn-ghost" data-import-brain>Importar JSON IA</button>
            <button class="btn btn-primary" data-nav="new-project">${icon("plusSquare")}<span>Novo Projeto</span></button>
          </div>
        </div>

        <div class="metric-grid">
          <article class="metric-card">
            <div class="metric-icon">${icon("folder")}</div>
            <div>
              <strong>${state.projects.length}</strong>
              <span>Projetos criados</span>
            </div>
          </article>
          <article class="metric-card">
            <div class="metric-icon is-success">${icon("home")}</div>
            <div>
              <strong>${finished}</strong>
              <span>Plantas finalizadas</span>
            </div>
          </article>
        </div>

        <h2 class="section-title">${icon("pencil")}<span>Seus Projetos Recentes</span></h2>
        <div class="recent-grid">
          ${recent.length ? recent.map((project) => renderProjectCard(project, true)).join("") : `
            <div class="empty-projects">
              <div>
                <h3>Nenhum projeto ainda</h3>
                <p class="muted">Comece um novo projeto para ver suas plantas aqui.</p>
              </div>
            </div>
          `}
        </div>
      </section>
    `;
  }

  function renderProjects() {
    return `
      <section class="screen">
        <div class="page-head">
          <div>
            <h1>Meus Projetos</h1>
            <p>Gerencie seus estudos, acompanhe opcoes geradas e abra o chat do arquiteto.</p>
          </div>
          <div class="page-actions">
            <button class="btn btn-ghost" data-import-brain>Importar JSON IA</button>
            <button class="btn btn-primary" data-nav="new-project">${icon("plusSquare")}<span>Novo Projeto</span></button>
          </div>
        </div>
        <div class="projects-grid">
          ${state.projects.length ? state.projects.map((project) => renderProjectCard(project, false)).join("") : `
            <div class="empty-projects">
              <div>
                <h3>Seu painel esta vazio</h3>
                <p class="muted">Crie o primeiro projeto para gerar opcoes de planta.</p>
              </div>
            </div>
          `}
        </div>
      </section>
    `;
  }

  function renderProjectCard(project, compact) {
    const date = formatDate(project.createdAt);
    const summary = `${project.requirements.bedrooms} quartos, ${project.requirements.bathrooms} banheiros`;
    const action = compact ? `#project/${project.id}` : `#project/${project.id}`;
    return `
      <article class="project-card">
        <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:12px;">
          <h3>${escapeHtml(project.name)}</h3>
          ${project.plans.length ? '<span class="status-badge">Pronto</span>' : ""}
        </div>
        <ul class="project-meta">
          <li>Area:<strong>${project.targetArea}m²</strong></li>
          <li>Estilo:<strong>${escapeHtml(project.style)}</strong></li>
          <li>Ambientes:<strong>${summary}</strong></li>
        </ul>
        <div class="project-footer">
          <span>${date}</span>
          <button class="round-arrow" data-link="${action}">→</button>
        </div>
      </article>
    `;
  }

  function renderWizard() {
    const maxArea = Number(state.draft.lot.width) * Number(state.draft.lot.depth);
    return `
      <section class="screen wizard-wrap">
        <h1>Novo Projeto</h1>
        <div class="stepper">
          ${stepItem(1, "Basico")}
          ${stepItem(2, "Terreno")}
          ${stepItem(3, "Ambientes")}
          ${stepItem(4, "Preferencias")}
        </div>
        <div class="wizard-card">
          ${renderWizardStep(maxArea)}
        </div>
        <div class="wizard-footer">
          <button class="btn btn-ghost" data-wizard-back ${state.wizardStep === 1 ? "disabled" : ""}>Voltar</button>
          <button class="btn btn-primary" data-wizard-next>${state.wizardStep === 4 ? "Concluir" : "Proximo Passo"}</button>
        </div>
      </section>
    `;
  }

  function stepItem(step, label) {
    const isDone = state.wizardStep > step;
    const isActive = state.wizardStep === step;
    return `
      <div class="stepper-item ${isDone ? "is-done" : ""} ${isActive ? "is-active" : ""}">
        <div class="stepper-ball">${isDone ? "✓" : step}</div>
        <span>${label}</span>
      </div>
    `;
  }

  function renderWizardStep(maxArea) {
    if (state.wizardStep === 1) {
      return `
        <div class="wizard-section">
          <label class="field">
            <span>Nome do Projeto *</span>
            <input type="text" placeholder="Ex: Casa de Praia da Familia" value="${escapeAttr(state.draft.name)}" data-draft-name />
          </label>
          <div class="field">
            <span>Estilo Arquitetonico</span>
            <div class="style-grid">
              ${ARCH_STYLES.map(([title, description]) => `
                <button class="style-card ${state.draft.style === title ? "is-selected" : ""}" data-style="${title}">
                  <strong>${title}</strong>
                  <small>${description}</small>
                </button>
              `).join("")}
            </div>
          </div>
        </div>
      `;
    }

    if (state.wizardStep === 2) {
      return `
        <div class="wizard-section">
          <div class="info-banner">${icon("pencil")}<span>Defina as dimensoes do terreno e a area total que deseja construir. A IA usara isso como limite maximo.</span></div>
          <div class="terrain-grid">
            <label class="field">
              <span>Frente do Terreno (m)</span>
              <input type="number" min="1" value="${state.draft.lot.width}" data-draft-lot="width" />
            </label>
            <label class="field">
              <span>Fundo do Terreno (m)</span>
              <input type="number" min="1" value="${state.draft.lot.depth}" data-draft-lot="depth" />
            </label>
          </div>
          <label class="field">
            <span>Area Construida Desejada (m²)</span>
            <input type="number" min="1" value="${state.draft.targetArea}" data-draft-target />
            <small>Area maxima permitida pelo terreno: ${maxArea} m²</small>
          </label>
        </div>
      `;
    }

    if (state.wizardStep === 3) {
      return `
        <div class="counter-grid">
          ${counterCard("Andares", "floors", state.draft.requirements.floors)}
          ${counterCard("Quartos Totais", "bedrooms", state.draft.requirements.bedrooms)}
          ${counterCard("Sendo Suites", "suites", state.draft.requirements.suites)}
          ${counterCard("Banheiros", "bathrooms", state.draft.requirements.bathrooms)}
          ${counterCard("Vagas Garagem", "garageSpots", state.draft.requirements.garageSpots)}
          <article class="counter-card">
            <div>
              <strong>Area de Piscina</strong>
              <small>Incluir piscina no quintal</small>
            </div>
            <button class="switch ${state.draft.requirements.hasPool ? "is-on" : ""}" data-toggle-pool>
              <span></span>
            </button>
          </article>
        </div>
      `;
    }

    return `
      <div class="wizard-section">
        <h2>Adicione suas preferencias</h2>
        <p class="muted" style="margin:8px 0 26px;">A IA usara essas tags para moldar o layout ao seu gosto.</p>
        <div class="preferences-grid">
          ${PREFERENCES.map((preference) => `
            <button class="preference-pill ${state.draft.preferences.includes(preference) ? "is-selected" : ""}" data-preference="${preference}">
              ${preference}
            </button>
          `).join("")}
        </div>
      </div>
    `;
  }

  function counterCard(label, key, value) {
    return `
      <article class="counter-card">
        <strong>${label}</strong>
        <div class="counter-control">
          <button data-counter="${key}" data-direction="-1">−</button>
          <strong>${value}</strong>
          <button data-counter="${key}" data-direction="1">+</button>
        </div>
      </article>
    `;
  }

  function renderProjectDetail(projectId) {
    const project = findProject(projectId);
    if (!project) {
      return `<section class="screen"><div class="empty-projects"><div><h3>Projeto nao encontrado</h3></div></div></section>`;
    }

    return `
      <section class="screen">
        <div class="detail-shell">
          <div class="detail-head">
            <div>
              <div class="project-tag"><span>Projeto</span><span>${project.shortId}</span></div>
              <h1 class="detail-title">${escapeHtml(project.name)}</h1>
            </div>
            <div class="summary-pill">
              <div><small>Area Total</small><strong>${project.targetArea}m²</strong></div>
              <div><small>Terreno</small><strong>${project.lot.width}x${project.lot.depth}m</strong></div>
              <div><small>Estilo</small><strong>${escapeHtml(project.style)}</strong></div>
            </div>
          </div>

          <div class="detail-tabs">
            <button class="detail-tab ${state.tab === "plans" ? "is-active" : ""}" data-tab="plans">${icon("layers")}<span>Plantas Geradas</span></button>
            <button class="detail-tab ${state.tab === "chat" ? "is-active" : ""}" data-tab="chat">${icon("chat")}<span>${APP_CHAT_NAME}</span></button>
          </div>

          <div class="detail-body">
            ${state.tab === "plans" ? renderPlansTab(project) : renderChat(project)}
          </div>
        </div>
      </section>
    `;
  }

  function renderPlansTab(project) {
    if (!project.plans.length) {
      return `
        <div class="empty-card">
          <div>
            <div class="empty-icon">${icon("spark")}</div>
            <h3>Pronto para a magica?</h3>
            <p>Nossa IA analisou seus requisitos e esta pronta para gerar opcoes de plantas baixas exclusivas para o seu terreno.</p>
            <button class="btn btn-primary" data-generate-plans="${project.id}">${icon("spark")}<span>Gerar 3 Opcoes de Planta</span></button>
          </div>
        </div>
      `;
    }

    return `
      <div class="plan-grid">
        ${project.plans.map((plan) => `
          <article class="plan-card">
            <h3>${escapeHtml(plan.title)}</h3>
            <small>${plan.totalArea.toFixed(1)}m2 de area construida</small>
            ${plan.qualityScore?.overall_score ? `<div class="plan-card-score">Score ${escapeHtml(String(plan.qualityScore.overall_score))}</div>` : ""}
            <div class="mini-plan">${renderPlanSvg(plan, true)}</div>
            <p>"${escapeHtml(plan.description)}"</p>
            ${Array.isArray(plan.levels) && plan.levels.length > 1 ? `<span class="plan-card-meta">${plan.levels.length} pavimentos renderizados</span>` : ""}
            <button class="btn btn-ghost" data-open-plan="#plan/${project.id}/${plan.id}">Ver detalhes</button>
          </article>
        `).join("")}
      </div>
    `;
  }

  function renderChat(project) {
    return `
      <div class="chat-shell">
        <div class="chat-history" id="chat-history">
          ${project.chat.map((message) => `
            <div class="chat-bubble ${message.role === "user" ? "is-user" : "is-ai"}">${escapeHtml(message.text)}</div>
          `).join("")}
        </div>
        <div class="quick-prompts">
          ${QUICK_PROMPTS.map((prompt) => `<button data-prompt="${prompt}">${prompt}</button>`).join("")}
        </div>
        <form class="chat-compose" data-chat-form="${project.id}">
          <input type="text" name="message" placeholder="Peça ajustes como: deixe a cozinha maior" />
          <button class="btn btn-primary" type="submit">${icon("send")}<span>Enviar</span></button>
        </form>
      </div>
    `;
  }

  function renderPlanDetail(projectId, planId) {
    const project = findProject(projectId);
    const plan = project ? project.plans.find((item) => item.id === planId) : null;
    const displayedRooms = plan ? getDisplayedPlanRooms(plan) : [];
    const displayedLevel = plan ? getDisplayedPlanLevel(plan) : null;
    if (!project || !plan) {
      return `<section class="screen"><div class="empty-projects"><div><h3>Planta nao encontrada</h3></div></div></section>`;
    }

    return `
      <section class="screen">
        <div class="plan-view">
          <aside class="plan-panel is-left">
            <button class="detail-tab" data-link="#project/${project.id}" style="margin-bottom:14px;">${icon("back")}<span>${escapeHtml(plan.title)}</span></button>
            <div class="plan-area">
              <strong>${plan.totalArea.toFixed(1)} m2</strong>
              <span>Area total construida</span>
            </div>
            ${displayedLevel ? `<div class="plan-level-meta">Exibindo: <strong>${escapeHtml(displayedLevel.label)}</strong></div>
              <div class="plan-level-switcher">
                ${plan.levels.map((level) => `
                  <button class="plan-level-pill ${(displayedLevel.level === level.level) ? "is-active" : ""}" data-plan-level="${plan.id}" data-level="${level.level}">
                    ${escapeHtml(level.label)}
                  </button>
                `).join("")}
              </div>
            ` : ""}
            <h2>Lista de Ambientes</h2>
            <div class="rooms-list">
              ${displayedRooms.map((room) => `
                <div class="room-row">
                  <span class="room-dot" style="background:${room.color}"></span>
                  <strong>${escapeHtml(room.name)}</strong>
                  <span class="room-pill">${room.area.toFixed(1)}m2</span>
                </div>
              `).join("")}
            </div>
            ${plan.qualityScore ? `
              <h2 style="margin-top:28px;">Score da Planta</h2>
              <div class="plan-card-soft plan-score-card" style="margin-top:18px;">
                ${Object.entries(plan.qualityScore).map(([key, value]) => `
                  <div class="plan-score-row">
                    <span>${escapeHtml(key.replaceAll("_", " ").replace(" score", ""))}</span>
                    <strong>${escapeHtml(String(value))}</strong>
                  </div>
                `).join("")}
              </div>
            ` : ""}
          </aside>

          <section class="plan-canvas-wrap">
            <div class="plan-toolbar">
              <div class="plan-note">${icon("help")}<span>Visualize em escala. Use o scroll para zoom.</span></div>
              <div class="plan-actions">
                <button class="btn-inline">${icon("star")}<span>Favoritar</span></button>
                <button class="btn-inline">${icon("share")}</button>
                <button class="btn-inline is-dark">${icon("download")}<span>Exportar PDF</span></button>
              </div>
            </div>
            <div class="plan-stage">
              <div class="plan-zoom">
                <button data-zoom="in">${icon("zoomIn")}</button>
                <button data-zoom="out">${icon("zoomOut")}</button>
                <button data-zoom="reset">${icon("expand")}</button>
              </div>
              <div class="plan-stage-inner" style="transform:scale(${state.detailZoom});">
                ${renderPlanSvg(plan, false)}
              </div>
            </div>
            <div class="plan-scale">? <span>${plan.scale}</span></div>
          </section>

          <aside class="plan-panel is-right">
            <h2>Notas da IA</h2>
            <div class="plan-card-soft" style="margin:18px 0 28px;">
              <p>${escapeHtml(plan.notes)}</p>
            </div>
            ${plan.strategy ? `
              <h2>Estrategia</h2>
              <div class="plan-card-soft" style="margin:18px 0 28px;">
                <p>${escapeHtml(plan.strategy.replaceAll("_", " "))}</p>
              </div>
            ` : ""}
            ${Array.isArray(plan.processingNotes) && plan.processingNotes.length ? `
              <h2>Processamento</h2>
              <div class="plan-card-soft" style="margin:18px 0 28px;">
                <ul class="tips-list">
                  ${plan.processingNotes.map((note) => `<li>${escapeHtml(note)}</li>`).join("")}
                </ul>
              </div>
            ` : ""}
            <h2>Dicas de Edicao</h2>
            <div class="plan-card-soft" style="margin-top:18px;">
              <ul class="tips-list">
                ${plan.tips.map((tip) => `<li>${escapeHtml(tip)}</li>`).join("")}
              </ul>
            </div>
            ${plan.constraints && Object.keys(plan.constraints).length ? `
              <h2 style="margin-top:28px;">Restricoes</h2>
              <div class="plan-card-soft" style="margin-top:18px;">
                <ul class="tips-list">
                  ${Object.entries(plan.constraints).map(([key, value]) => `<li><strong>${escapeHtml(key)}</strong>: ${escapeHtml(String(value))}</li>`).join("")}
                </ul>
              </div>
            ` : ""}
          </aside>
        </div>
      </section>
    `;
  }

  function renderPlanSvg(plan, mini) {
    const displayRooms = getDisplayedPlanRooms(plan);
    if (plan.layoutKind === "brain") {
      return renderTechnicalPlanSvg(plan, mini);
    }

    const width = 320;
    const height = 610;
    const stroke = mini ? 1.4 : 2.8;
    const fontBase = mini ? 7 : 10;
    const areaBase = mini ? 6 : 8;

    return `
      <svg viewBox="0 0 ${width} ${height}" width="${mini ? 160 : 320}" height="${mini ? 250 : 610}" aria-label="${escapeAttr(plan.title)}">
        <rect x="18" y="18" width="264" height="550" rx="10" fill="#fff" stroke="#17233c" stroke-width="${stroke}" />
        ${displayRooms.map((room) => {
          const cx = room.x + room.w / 2;
          const cy = room.y + room.h / 2;
          const titleSize = Math.max(fontBase, Math.min(fontBase + 2, room.w / 14));
          return `
            <g>
              <rect x="${room.x}" y="${room.y}" width="${room.w}" height="${room.h}" fill="${room.color}" stroke="#17233c" stroke-width="${stroke}" />
              <text x="${cx}" y="${cy - 6}" text-anchor="middle" font-size="${titleSize}" font-weight="700" fill="#18253d">${escapeHtml(room.name)}</text>
              <text x="${cx}" y="${cy + 12}" text-anchor="middle" font-size="${areaBase}" fill="#476082">${room.area.toFixed(1)}m²</text>
            </g>
          `;
        }).join("")}
      </svg>
    `;
  }

  function renderTechnicalPlanSvg(plan, mini) {
    const displayRooms = getDisplayedPlanRooms(plan);
    const width = 360;
    const height = 650;
    const wallStroke = mini ? 1.5 : 3.2;
    const innerStroke = mini ? 0.8 : 1.4;
    const plotWidth = plan.plot?.width || 12;
    const plotDepth = plan.plot?.depth || 8;
    const minX = Math.min(...displayRooms.map((room) => room.x));
    const minY = Math.min(...displayRooms.map((room) => room.y));
    const maxX = Math.max(...displayRooms.map((room) => room.x + room.w));
    const maxY = Math.max(...displayRooms.map((room) => room.y + room.h));

    const openingsMarkup = displayRooms.map((room) => {
      const windowSpan = Math.max(Math.min(room.w * 0.28, mini ? 18 : 26), mini ? 8 : 12);
      const doorSpan = Math.max(Math.min(room.w * 0.24, mini ? 14 : 18), mini ? 6 : 10);
      const wx = room.x + (room.w - windowSpan) / 2;
      const topWindow = `<line x1="${wx}" y1="${room.y + (mini ? 1.4 : 2.2)}" x2="${wx + windowSpan}" y2="${room.y + (mini ? 1.4 : 2.2)}" stroke="#7ab7ff" stroke-width="${mini ? 1.2 : 2.2}" stroke-linecap="round" />`;
      const doorX = room.x + room.w / 2;
      const doorY = room.y + room.h;
      const doorArc = `M ${doorX} ${doorY} Q ${doorX + (mini ? 7 : 10)} ${doorY - (mini ? 7 : 10)} ${doorX + doorSpan} ${doorY}`;
      const bottomDoor = `<path d="${doorArc}" fill="none" stroke="#ff7685" stroke-width="${mini ? 1 : 1.8}" stroke-linecap="round" />`;
      const roleLabel = room.role || "";
      if (["bathroom", "powder_room"].includes(roleLabel)) {
        return `${topWindow}<line x1="${room.x + room.w - (mini ? 9 : 14)}" y1="${room.y + (mini ? 4 : 6)}" x2="${room.x + room.w - (mini ? 3 : 6)}" y2="${room.y + (mini ? 4 : 6)}" stroke="#7ab7ff" stroke-width="${mini ? 1 : 1.8}" />${bottomDoor}`;
      }
      if (["garage", "pool"].includes(roleLabel)) {
        return `<line x1="${room.x + 6}" y1="${doorY - (mini ? 1 : 2)}" x2="${room.x + room.w - 6}" y2="${doorY - (mini ? 1 : 2)}" stroke="#7ab7ff" stroke-width="${mini ? 1.2 : 2.2}" stroke-linecap="round" />`;
      }
      return `${topWindow}${bottomDoor}`;
    }).join("");

    const roleOverlayMarkup = displayRooms.map((room) => {
      if (room.role === "circulation") {
        return `
          <g opacity="${mini ? "0.18" : "0.28"}">
            ${Array.from({ length: 6 }).map((_, index) => {
              const y = room.y + 4 + index * ((room.h - 8) / 5);
              return `<line x1="${room.x + 4}" y1="${y}" x2="${room.x + room.w - 4}" y2="${y}" stroke="#4a7cff" stroke-width="${mini ? 0.8 : 1.2}" stroke-dasharray="${mini ? "2 2" : "4 3"}" />`;
            }).join("")}
          </g>
        `;
      }
      if (room.role === "stairs") {
        const arrowX = room.x + room.w * 0.5;
        return `
          <g opacity="${mini ? "0.85" : "1"}">
            <line x1="${arrowX}" y1="${room.y + room.h - 8}" x2="${arrowX}" y2="${room.y + 10}" stroke="#355fd6" stroke-width="${mini ? 1 : 1.8}" stroke-linecap="round" />
            <path d="M ${arrowX - 5} ${room.y + 16} L ${arrowX} ${room.y + 8} L ${arrowX + 5} ${room.y + 16}" fill="none" stroke="#355fd6" stroke-width="${mini ? 1 : 1.8}" stroke-linecap="round" stroke-linejoin="round" />
          </g>
        `;
      }
      return "";
    }).join("");

    const roomsMarkup = displayRooms.map((room) => {
      const cx = room.x + room.w / 2;
      const cy = room.y + room.h / 2;
      const titleSize = mini ? Math.max(6, Math.min(9, room.w / 14)) : Math.max(8, Math.min(12, room.w / 11));
      const detailSize = mini ? 5.6 : 7.4;
      const fillOpacity = room.role === "circulation" ? 0.34 : room.role === "stairs" ? 0.42 : 0.62;
      return `
        <g>
          <rect x="${room.x}" y="${room.y}" width="${room.w}" height="${room.h}" rx="${mini ? 2 : 4}" fill="${room.color}" fill-opacity="${fillOpacity}" stroke="#15223b" stroke-width="${wallStroke}" />
          <rect x="${room.x + (mini ? 1.8 : 3)}" y="${room.y + (mini ? 1.8 : 3)}" width="${Math.max(room.w - (mini ? 3.6 : 6), 2)}" height="${Math.max(room.h - (mini ? 3.6 : 6), 2)}" fill="none" stroke="rgba(21,34,59,0.28)" stroke-width="${innerStroke}" />
          <text x="${cx}" y="${cy - (mini ? 2 : 6)}" text-anchor="middle" font-size="${titleSize}" font-weight="700" fill="#17233c">${escapeHtml(room.name)}</text>
          <text x="${cx}" y="${cy + (mini ? 9 : 11)}" text-anchor="middle" font-size="${detailSize}" fill="#445d85">${room.area.toFixed(1)}m??</text>
          ${!mini ? `<text x="${cx}" y="${cy + 22}" text-anchor="middle" font-size="6.4" fill="#6a7f9d">${escapeHtml(room.zone || room.role || "")}</text>` : ""}
        </g>
      `;
    }).join("");

    const circulationRooms = displayRooms.filter((room) => ["circulation", "stairs", "family_lounge"].includes(room.role));
    const adjLines = circulationRooms.flatMap((hub) => {
      const targets = displayRooms.filter((room) => room !== hub && (hub.adjacency || []).some((name) => {
        const lowered = name.toLowerCase();
        return room.name.toLowerCase() === lowered || room.name.toLowerCase().includes(lowered) || lowered.includes(room.name.toLowerCase());
      }));
      const hx = hub.x + hub.w / 2;
      const hy = hub.y + hub.h / 2;
      return targets.slice(0, 4).map((target) => {
        const tx = target.x + target.w / 2;
        const ty = target.y + target.h / 2;
        return `<path d="M ${hx} ${hy} L ${hx} ${ty} L ${tx} ${ty}" fill="none" stroke="rgba(47,107,255,0.28)" stroke-width="${mini ? 0.9 : 1.6}" stroke-dasharray="${mini ? "2 2" : "4 4"}" />`;
      });
    }).join("");

    return `
      <svg viewBox="0 0 ${width} ${height}" width="${mini ? 168 : 360}" height="${mini ? 250 : 650}" aria-label="${escapeAttr(plan.title)}">
        <rect x="20" y="18" width="292" height="592" rx="16" fill="#ffffff" stroke="#dbe4f3" stroke-width="1.4" />
        <rect x="34" y="34" width="264" height="564" rx="10" fill="none" stroke="rgba(21,34,59,0.16)" stroke-width="${mini ? 1 : 1.4}" stroke-dasharray="${mini ? "3 3" : "6 6"}" />
        <rect x="${Math.max(minX - 6, 24)}" y="${Math.max(minY - 6, 28)}" width="${Math.min(maxX - minX + 12, 278)}" height="${Math.min(maxY - minY + 12, 576)}" rx="${mini ? 4 : 8}" fill="none" stroke="rgba(21,34,59,0.18)" stroke-width="${mini ? 1 : 1.4}" />
        ${roomsMarkup}
        ${roleOverlayMarkup}
        ${openingsMarkup}
        ${adjLines}
        ${!mini ? `
          <g>
            <line x1="34" y1="22" x2="298" y2="22" stroke="#6c81a4" stroke-width="1" />
            <line x1="34" y1="18" x2="34" y2="28" stroke="#6c81a4" stroke-width="1" />
            <line x1="298" y1="18" x2="298" y2="28" stroke="#6c81a4" stroke-width="1" />
            <text x="150" y="16" text-anchor="middle" font-size="8" fill="#5d7399">${plotWidth}m</text>
            <line x1="312" y1="34" x2="312" y2="598" stroke="#6c81a4" stroke-width="1" />
            <line x1="306" y1="34" x2="318" y2="34" stroke="#6c81a4" stroke-width="1" />
            <line x1="306" y1="598" x2="318" y2="598" stroke="#6c81a4" stroke-width="1" />
            <text x="320" y="320" font-size="8" fill="#5d7399" transform="rotate(90 320 320)">${plotDepth}m</text>
          </g>
        ` : ""}
      </svg>
    `;
  }

  function bindGlobalEvents(route) {
    app.querySelectorAll("[data-nav]").forEach((button) => {
      button.addEventListener("click", () => {
        if (button.dataset.disabled === "true") {
          showToast("Funcao preparada para a proxima fase.");
          return;
        }
        navigate(`#${button.dataset.nav}`);
      });
    });

    app.querySelectorAll("[data-link]").forEach((button) => {
      button.addEventListener("click", () => navigate(button.dataset.link));
    });

    const importTrigger = app.querySelector("[data-import-brain]");
    const importInput = app.querySelector("#brainImportInput");
    if (importTrigger && importInput) {
      importTrigger.addEventListener("click", () => importInput.click());
      importInput.addEventListener("change", async (event) => {
        const file = event.target.files && event.target.files[0];
        if (!file) return;
        try {
          const text = await file.text();
          const payload = JSON.parse(text);
          if (!payload || (!Array.isArray(payload.rooms) && !Array.isArray(payload.variants))) {
            throw new Error("JSON invalido para importacao arquitetonica.");
          }
          const project = createProjectFromBrainPayload(payload);
          state.projects.unshift(project);
          persistProjects();
          showToast("Projeto importado do cérebro arquitetônico.");
          navigate(`#project/${project.id}`);
        } catch (error) {
          showToast(error.message || "Nao foi possivel importar o JSON.");
        } finally {
          importInput.value = "";
        }
      });
    }

    const sidebarToggle = app.querySelector("[data-sidebar-toggle]");
    if (sidebarToggle) {
      sidebarToggle.addEventListener("click", () => {
        state.sidebarCollapsed = !state.sidebarCollapsed;
        persistSidebarCollapsed();
        render();
      });
    }

    app.querySelectorAll("[data-open-plan]").forEach((button) => {
      button.addEventListener("click", () => navigate(button.dataset.openPlan.replace(/^#/, "#")));
    });

    if (route.name === "new-project") bindWizardEvents();
    if (route.name === "project") bindProjectDetailEvents(route.projectId);
    if (route.name === "plan") bindPlanEvents();
  }

  function bindWizardEvents() {
    const nameInput = app.querySelector("[data-draft-name]");
    if (nameInput) {
      nameInput.addEventListener("input", (event) => {
        state.draft.name = event.target.value;
      });
    }

    app.querySelectorAll("[data-style]").forEach((button) => {
      button.addEventListener("click", () => {
        state.draft.style = button.dataset.style;
        render();
      });
    });

    app.querySelectorAll("[data-draft-lot]").forEach((input) => {
      input.addEventListener("input", () => {
        const key = input.dataset.draftLot;
        state.draft.lot[key] = Number(input.value || 0);
      });
    });

    const targetInput = app.querySelector("[data-draft-target]");
    if (targetInput) {
      targetInput.addEventListener("input", (event) => {
        state.draft.targetArea = Number(event.target.value || 0);
      });
    }

    app.querySelectorAll("[data-counter]").forEach((button) => {
      button.addEventListener("click", () => {
        const key = button.dataset.counter;
        const delta = Number(button.dataset.direction);
        const next = Math.max(0, Number(state.draft.requirements[key]) + delta);
        state.draft.requirements[key] = next;
        if (key === "suites" && next > state.draft.requirements.bedrooms) {
          state.draft.requirements.bedrooms = next;
        }
        if (key === "bedrooms" && next < state.draft.requirements.suites) {
          state.draft.requirements.suites = next;
        }
        render();
      });
    });

    const poolToggle = app.querySelector("[data-toggle-pool]");
    if (poolToggle) {
      poolToggle.addEventListener("click", () => {
        state.draft.requirements.hasPool = !state.draft.requirements.hasPool;
        render();
      });
    }

    app.querySelectorAll("[data-preference]").forEach((button) => {
      button.addEventListener("click", () => {
        const value = button.dataset.preference;
        const exists = state.draft.preferences.includes(value);
        state.draft.preferences = exists
          ? state.draft.preferences.filter((item) => item !== value)
          : state.draft.preferences.concat(value);
        render();
      });
    });

    const back = app.querySelector("[data-wizard-back]");
    if (back) {
      back.addEventListener("click", () => {
        if (state.wizardStep > 1) {
          state.wizardStep -= 1;
          render();
        }
      });
    }

    const next = app.querySelector("[data-wizard-next]");
    if (next) {
      next.addEventListener("click", () => {
        if (state.wizardStep === 1 && !state.draft.name.trim()) {
          showToast("Digite o nome do projeto para continuar.");
          return;
        }
        if (state.wizardStep < 4) {
          state.wizardStep += 1;
          render();
          return;
        }
        const project = createProjectFromDraft({
          name: state.draft.name.trim(),
          style: state.draft.style,
          lot: { ...state.draft.lot },
          targetArea: state.draft.targetArea,
          requirements: { ...state.draft.requirements },
          preferences: [...state.draft.preferences],
        });
        state.projects.unshift(project);
        persistProjects();
        state.wizardStep = 1;
        state.draft = initialDraft();
        state.tab = "plans";
        showToast("Projeto criado com sucesso.");
        navigate(`#project/${project.id}`);
      });
    }
  }

  function bindProjectDetailEvents(projectId) {
    app.querySelectorAll("[data-tab]").forEach((button) => {
      button.addEventListener("click", () => {
        state.tab = button.dataset.tab;
        render();
      });
    });

    const generateButton = app.querySelector(`[data-generate-plans="${projectId}"]`);
    if (generateButton) {
      generateButton.addEventListener("click", () => {
        const project = findProject(projectId);
        if (!project) return;
        project.plans = generatePlans(project);
        project.status = "ready";
        persistProjects();
        showToast("Plantas geradas com sucesso.");
        render();
      });
    }

    const form = app.querySelector(`[data-chat-form="${projectId}"]`);
    if (form) {
      form.addEventListener("submit", (event) => {
        event.preventDefault();
        const input = form.elements.message;
        sendChat(projectId, input.value);
        input.value = "";
      });
    }

    app.querySelectorAll("[data-prompt]").forEach((button) => {
      button.addEventListener("click", () => sendChat(projectId, button.dataset.prompt));
    });
  }

  function bindPlanEvents() {
    app.querySelectorAll("[data-zoom]").forEach((button) => {
      button.addEventListener("click", () => {
        if (button.dataset.zoom === "in") state.detailZoom = Math.min(1.8, Number((state.detailZoom + 0.1).toFixed(2)));
        if (button.dataset.zoom === "out") state.detailZoom = Math.max(0.7, Number((state.detailZoom - 0.1).toFixed(2)));
        if (button.dataset.zoom === "reset") state.detailZoom = 1;
        render();
      });
    });

    app.querySelectorAll("[data-plan-level]").forEach((button) => {
      button.addEventListener("click", () => {
        state.activePlanLevels[button.dataset.planLevel] = Number(button.dataset.level);
        render();
      });
    });
  }

  function sendChat(projectId, text) {
    const value = (text || "").trim();
    if (!value) return;
    const project = findProject(projectId);
    if (!project) return;
    project.chat.push({ role: "user", text: value });
    project.chat.push({ role: "ai", text: mockChatReply(value) });
    persistProjects();
    render();
  }

  function mockChatReply(prompt) {
    const lower = prompt.toLowerCase();
    if (lower.includes("cozinha")) {
      return "Posso ampliar a cozinha aproximando jantar e area gourmet, reduzindo a perda em circulacao.";
    }
    if (lower.includes("lavabo")) {
      return "Uma boa opcao e encaixar o lavabo junto ao hall social, preservando privacidade da area intima.";
    }
    if (lower.includes("privacidade")) {
      return "Posso reposicionar a suite para o fundo do lote e criar um filtro de circulacao entre social e intimo.";
    }
    if (lower.includes("corredor")) {
      return "Vou buscar uma setorizacao mais integrada para encurtar percursos e liberar area util para os ambientes.";
    }
    return "Entendi. Posso ajustar a planta pensando em fluxo, conforto e melhor aproveitamento do terreno.";
  }

  function findProject(projectId) {
    return state.projects.find((project) => project.id === projectId);
  }

  function showToast(message) {
    state.toast = message;
    render();
    window.clearTimeout(state.toastTimer);
    state.toastTimer = window.setTimeout(() => {
      state.toast = "";
      render();
    }, 2200);
  }

  function formatDate(value) {
    try {
      return new Intl.DateTimeFormat("pt-BR", {
        day: "2-digit",
        month: "short",
        year: "numeric",
      }).format(new Date(value));
    } catch (error) {
      return value;
    }
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function escapeAttr(value) {
    return escapeHtml(value);
  }
})();
