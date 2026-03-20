import { assertSupabaseConfigured, supabase } from "./supabaseClient.js";
import { safeQuery } from "./adminCommon.js";

export async function fetchAdminSnapshots() {
  const snapshotsResult = await safeQuery(
    (client) =>
      client
        .from("supplier_price_snapshots")
        .select("*")
        .order("captured_at", { ascending: false })
        .limit(300),
    {
      fallbackData: [],
      missingMessage: "A tabela supplier_price_snapshots ainda não está disponível.",
      permissionMessage: "Sem permissão para visualizar os snapshots de preço.",
      errorMessage: "Não foi possível carregar os snapshots de preço."
    }
  );

  return {
    rows: snapshotsResult.data || [],
    notices: snapshotsResult.notice ? [snapshotsResult.notice] : []
  };
}

export async function upsertSnapshot(payload) {
  assertSupabaseConfigured();

  const row = {
    company_id: payload.company_id || null,
    item_name: payload.item_name,
    normalized_item_name: payload.normalized_item_name,
    query: payload.query,
    provider: payload.provider,
    source_name: payload.source_name,
    supplier_name: payload.supplier_name,
    title: payload.title,
    price: payload.price ?? null,
    unit_price: payload.unit_price ?? null,
    currency: payload.currency || "BRL",
    delivery_days: payload.delivery_days ?? null,
    delivery_label: payload.delivery_label || null,
    result_url: payload.result_url || null,
    metadata: payload.metadata || {}
  };

  if (payload.id) {
    const { error } = await supabase.from("supplier_price_snapshots").update(row).eq("id", payload.id);
    if (error) throw error;
    return payload.id;
  }

  const { data, error } = await supabase.from("supplier_price_snapshots").insert(row).select("id").single();
  if (error) throw error;
  return data.id;
}

export async function deleteSnapshot(snapshotId) {
  assertSupabaseConfigured();
  const { error } = await supabase.from("supplier_price_snapshots").delete().eq("id", snapshotId);
  if (error) throw error;
}
