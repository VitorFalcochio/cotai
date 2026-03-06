import { collectNotice, mapBy, safeQuery } from "./adminCommon.js";

function eventDate(row) {
  return row?.created_at || row?.updated_at || row?.occurred_at || null;
}

export async function fetchAdminLogs(filters = {}) {
  const notices = new Set();
  const [auditLogsResult, workerMessagesResult, quoteLogsResult, companiesResult] = await Promise.all([
    safeQuery(
      (client) =>
        client
          .from("admin_audit_logs")
          .select("*")
          .order("created_at", { ascending: false })
          .limit(120),
      { fallbackData: [], missingMessage: "Tabela admin_audit_logs ausente. Usando eventos do worker como fallback." }
    ),
    safeQuery(
      (client) =>
        client
          .from("worker_processed_messages")
          .select("id, request_id, processing_status, notes, created_at, chat_id, message_id")
          .order("created_at", { ascending: false })
          .limit(120),
      { fallbackData: [], missingMessage: "Tabela worker_processed_messages ausente. Logs de dedupe indisponiveis." }
    ),
    safeQuery(
      (client) =>
        client
          .from("request_quotes")
          .select("id, request_id, status, error_message, created_at, updated_at")
          .order("created_at", { ascending: false })
          .limit(120),
      { fallbackData: [], missingMessage: "Tabela request_quotes ausente. Logs de execucao indisponiveis." }
    ),
    safeQuery(
      (client) => client.from("companies").select("id, name"),
      { fallbackData: [], missingMessage: "Tabela companies ausente. Filtro por empresa limitado." }
    )
  ]);

  [auditLogsResult, workerMessagesResult, quoteLogsResult, companiesResult].forEach((result) =>
    collectNotice(notices, result)
  );

  const companyMap = mapBy(companiesResult.data, "id");

  const fallbackEvents = [
    ...workerMessagesResult.data.map((item) => ({
      id: `worker-${item.id}`,
      createdAt: item.created_at,
      type: "worker",
      company: "-",
      actor: item.message_id || item.chat_id || "worker",
      message: `${item.processing_status}: ${item.notes || "evento de dedupe"}`
    })),
    ...quoteLogsResult.data.map((item) => ({
      id: `quote-${item.id}`,
      createdAt: item.updated_at || item.created_at,
      type: "request_quote",
      company: "-",
      actor: item.request_id || "request",
      message: item.error_message || `Execucao ${item.status}`
    }))
  ];

  const baseEvents = auditLogsResult.data.length
    ? auditLogsResult.data.map((item) => ({
        id: item.id,
        createdAt: eventDate(item),
        type: item.event_type || item.type || "admin",
        company: companyMap.get(item.company_id)?.name || item.company_id || "-",
        actor: item.actor_email || item.actor_id || "-",
        message: item.description || item.message || "Evento administrativo"
      }))
    : fallbackEvents;

  const rows = baseEvents.filter((item) => {
    if (filters.type && filters.type !== "all" && item.type !== filters.type) return false;
    if (filters.company && filters.company !== "all" && item.company !== filters.company) return false;
    if (filters.startDate && item.createdAt && new Date(item.createdAt) < new Date(filters.startDate)) return false;
    if (filters.endDate && item.createdAt && new Date(item.createdAt) > new Date(`${filters.endDate}T23:59:59`)) return false;
    if (
      filters.requestId &&
      !String(item.actor || "").includes(filters.requestId) &&
      !String(item.message || "").includes(filters.requestId)
    ) {
      return false;
    }
    return true;
  });

  const companies = Array.from(new Set(rows.map((item) => item.company).filter(Boolean)));
  const types = Array.from(new Set(rows.map((item) => item.type).filter(Boolean)));

  return { rows, companies, types, notices: Array.from(notices) };
}
