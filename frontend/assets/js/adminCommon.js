import { getPlanPrice, formatPlanLabel as formatCatalogPlanLabel } from "./planCatalog.js";
import { assertSupabaseConfigured, supabase } from "./supabaseClient.js";

const MISSING_RESOURCE_PATTERNS = [
  "does not exist",
  "schema cache",
  "could not find",
  "relation",
  "unknown table"
];

const FORBIDDEN_PATTERNS = ["permission denied", "not allowed", "row-level security", "forbidden"];

export function ensureArray(value) {
  return Array.isArray(value) ? value : [];
}

export function isMissingResourceError(error) {
  const message = String(error?.message || error || "").toLowerCase();
  return MISSING_RESOURCE_PATTERNS.some((pattern) => message.includes(pattern));
}

export function isPermissionError(error) {
  const message = String(error?.message || error || "").toLowerCase();
  return FORBIDDEN_PATTERNS.some((pattern) => message.includes(pattern));
}

export async function safeQuery(buildQuery, options = {}) {
  const {
    fallbackData = null,
    missingMessage = "Tabela ainda não disponível neste projeto.",
    permissionMessage = "Sem permissao para visualizar estes dados com a politica atual do Supabase.",
    errorMessage = "Não foi possível carregar os dados administrativos."
  } = options;

  try {
    assertSupabaseConfigured();
    const result = await buildQuery(supabase);
    if (result?.error) throw result.error;

    return {
      data: result?.data ?? result ?? fallbackData,
      count: result?.count ?? null,
      status: "ok",
      notice: "",
      error: null
    };
  } catch (error) {
    if (isMissingResourceError(error)) {
      return {
        data: fallbackData,
        count: null,
        status: "missing",
        notice: missingMessage,
        error
      };
    }

    if (isPermissionError(error)) {
      return {
        data: fallbackData,
        count: null,
        status: "forbidden",
        notice: permissionMessage,
        error
      };
    }

    return {
      data: fallbackData,
      count: null,
      status: "error",
      notice: errorMessage,
      error
    };
  }
}

export function collectNotice(target, result) {
  if (result?.notice) {
    target.add(result.notice);
  }
}

export function mapBy(rows, key = "id") {
  return ensureArray(rows).reduce((accumulator, row) => {
    const value = row?.[key];
    if (value !== undefined && value !== null) {
      accumulator.set(value, row);
    }
    return accumulator;
  }, new Map());
}

export function groupCount(rows, key) {
  return ensureArray(rows).reduce((accumulator, row) => {
    const value = row?.[key];
    if (value !== undefined && value !== null) {
      accumulator.set(value, (accumulator.get(value) || 0) + 1);
    }
    return accumulator;
  }, new Map());
}

export function latestBy(rows, key, sortKey = "created_at") {
  return ensureArray(rows).reduce((accumulator, row) => {
    const value = row?.[key];
    if (!value) return accumulator;

    const current = accumulator.get(value);
    const currentTime = current ? new Date(current[sortKey] || 0).getTime() : 0;
    const nextTime = new Date(row?.[sortKey] || 0).getTime();

    if (!current || nextTime >= currentTime) {
      accumulator.set(value, row);
    }

    return accumulator;
  }, new Map());
}

export function startOfTodayIso() {
  const now = new Date();
  now.setHours(0, 0, 0, 0);
  return now.toISOString();
}

export function startOfMonthIso() {
  const now = new Date();
  now.setDate(1);
  now.setHours(0, 0, 0, 0);
  return now.toISOString();
}

export function averageMinutes(rows, startKey, endKey) {
  const durations = ensureArray(rows)
    .map((row) => {
      const start = new Date(row?.[startKey] || 0).getTime();
      const end = new Date(row?.[endKey] || 0).getTime();
      if (!start || !end || end <= start) return null;
      return (end - start) / 60000;
    })
    .filter((value) => Number.isFinite(value));

  if (!durations.length) return null;
  const total = durations.reduce((sum, value) => sum + value, 0);
  return total / durations.length;
}

export function formatCurrencyBRL(value) {
  if (value === null || value === undefined || value === "") return "Não integrado";
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
    maximumFractionDigits: 0
  }).format(Number(value) || 0);
}

export function formatPlanLabel(value) {
  const plan = String(value || "").trim();
  if (!plan) return "Sem plano";
  return formatCatalogPlanLabel(plan);
}

export function getPlanMonthlyAmount(value) {
  return getPlanPrice(value);
}

export function normalizeStatus(value, fallback = "unknown") {
  return String(value || fallback).toUpperCase();
}

export function deriveCompanies({ companies = [], profiles = [], requests = [] } = {}) {
  if (ensureArray(companies).length) {
    return ensureArray(companies).map((company) => ({
      id: company.id,
      name: company.name || `Empresa ${String(company.id || "").slice(0, 8)}`,
      plan: company.plan || "Sem plano",
      status: company.status || "active",
      created_at: company.created_at || null
    }));
  }

  const companyIds = new Set();
  ensureArray(profiles).forEach((profile) => {
    if (profile?.company_id) companyIds.add(profile.company_id);
  });
  ensureArray(requests).forEach((request) => {
    if (request?.company_id) companyIds.add(request.company_id);
  });

  return Array.from(companyIds).map((companyId) => {
    const companyProfiles = ensureArray(profiles).filter((profile) => profile?.company_id === companyId);
    const companyRequests = ensureArray(requests).filter((request) => request?.company_id === companyId);
    const seedProfile = companyProfiles[0];
    const seedRequest = companyRequests[0];
    return {
      id: companyId,
      name:
        seedProfile?.company_name ||
        seedProfile?.full_name ||
        seedRequest?.company_name ||
        `Empresa ${String(companyId).slice(0, 8)}`,
      plan: seedProfile?.plan || "Sem plano",
      status: seedProfile?.status || "active",
      created_at: seedProfile?.created_at || seedRequest?.created_at || null
    };
  });
}
