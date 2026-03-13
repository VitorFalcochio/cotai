import { collectNotice, deriveCompanies, mapBy, safeQuery } from "./adminCommon.js";
import { assertSupabaseConfigured, supabase } from "./supabaseClient.js";

export async function fetchAdminUsers() {
  const notices = new Set();
  const [profilesResult, companiesResult] = await Promise.all([
    safeQuery(
      (client) =>
        client
          .from("profiles")
          .select("*")
          .order("created_at", { ascending: false }),
      { fallbackData: [], missingMessage: "Tabela profiles ausente. Lista de usuários indisponível." }
    ),
    safeQuery(
      (client) => client.from("companies").select("id, name, plan, status"),
      { fallbackData: [], missingMessage: "Tabela companies ausente. Empresa do usuário derivada do company_id." }
    )
  ]);

  const derivedCompanies = deriveCompanies({ companies: companiesResult.data, profiles: profilesResult.data, requests: [] });
  collectNotice(notices, profilesResult);
  if (derivedCompanies.length === 0 || companiesResult.status !== "missing") {
    collectNotice(notices, companiesResult);
  }
  const companiesMap = mapBy(derivedCompanies, "id");

  const rows = profilesResult.data.map((profile) => ({
    id: profile.id,
    name: profile.full_name || profile.name || profile.email || "Usuario",
    email: profile.email || "-",
    company: companiesMap.get(profile.company_id)?.name || profile.company_id || "-",
    role: profile.role || "member",
    lastLogin: profile.last_login_at || profile.updated_at || null,
    status: profile.status || "active"
  }));

  return { rows, notices: Array.from(notices) };
}

export async function updateUser(userId, patch) {
  assertSupabaseConfigured();
  const { error } = await supabase.from("profiles").update(patch).eq("id", userId);
  if (error) throw error;
}
