import { assertSupabaseConfigured, supabase } from "./supabaseClient.js";
import { getSession } from "./auth.js";
import { API_BASE_URL } from "./config.js";

export async function upsertSupplier(payload) {
  assertSupabaseConfigured();
  const session = await getSession();
  const userId = session?.user?.id;
  if (!userId) throw new Error("Sessao invalida.");

  const profileResult = await supabase.from("profiles").select("company_id").eq("id", userId).maybeSingle();
  if (profileResult.error) throw profileResult.error;
  const companyId = profileResult.data?.company_id;
  if (!companyId) throw new Error("Perfil sem company_id.");

  const row = {
    company_id: companyId,
    name: payload.name,
    region: payload.region || null,
    city: payload.city || null,
    state: payload.state || null,
    address_line: payload.address_line || null,
    postal_code: payload.postal_code || null,
    latitude: payload.latitude ?? null,
    longitude: payload.longitude ?? null,
    contact_name: payload.contact_name || null,
    contact_channel: payload.contact_channel || null,
    material_tags: payload.material_tags || [],
    average_delivery_days: payload.average_delivery_days || null,
    status: payload.status || "active"
  };

  if (payload.id) {
    const { error } = await supabase.from("suppliers").update(row).eq("id", payload.id);
    if (error) throw error;
    return payload.id;
  }

  const { data, error } = await supabase.from("suppliers").insert(row).select("id").single();
  if (error) throw error;
  return data.id;
}

export async function deleteSupplier(supplierId) {
  assertSupabaseConfigured();
  const { error } = await supabase.from("suppliers").delete().eq("id", supplierId);
  if (error) throw error;
}

export async function submitSupplierReview(payload) {
  const session = await getSession();
  if (!session?.access_token) {
    throw new Error("Sessao invalida. Faca login novamente.");
  }

  const response = await fetch(`${API_BASE_URL}/requests/${payload.request_id}/supplier-review`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${session.access_token}`
    },
    body: JSON.stringify(payload)
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.detail || "Não foi possível registrar a avaliação.");
  }
  return body;
}
