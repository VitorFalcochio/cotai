import { averageMinutes, collectNotice, safeQuery, startOfTodayIso } from "./adminCommon.js";

export async function fetchAdminWorker() {
  const notices = new Set();
  const todayIso = startOfTodayIso();

  const [messagesResult, quotesResult, heartbeatsResult] = await Promise.all([
    safeQuery(
      (client) =>
        client
          .from("worker_processed_messages")
          .select("id, message_id, request_id, processing_status, notes, created_at")
          .order("created_at", { ascending: false })
          .limit(120),
      { fallbackData: [], missingMessage: "Tabela worker_processed_messages ausente. Dedupe ainda nao esta visivel." }
    ),
    safeQuery(
      (client) =>
        client
          .from("request_quotes")
          .select("id, request_id, status, error_message, started_at, finished_at, created_at, updated_at")
          .order("created_at", { ascending: false })
          .limit(120),
      { fallbackData: [], missingMessage: "Tabela request_quotes ausente. Execucoes do worker indisponiveis." }
    ),
    safeQuery(
      (client) =>
        client
          .from("worker_heartbeats")
          .select("*")
          .order("created_at", { ascending: false })
          .limit(1),
      { fallbackData: [], missingMessage: "Tabela worker_heartbeats ausente. Status usando fallback por request_quotes." }
    )
  ]);

  [messagesResult, quotesResult, heartbeatsResult].forEach((result) => collectNotice(notices, result));

  const messages = messagesResult.data;
  const quotes = quotesResult.data;
  const latestHeartbeat = heartbeatsResult.data?.[0] || null;
  const latestActivity = latestHeartbeat?.created_at || quotes[0]?.updated_at || null;
  const isOnline = latestActivity ? Date.now() - new Date(latestActivity).getTime() < 10 * 60 * 1000 : false;

  const processedToday = messages.filter(
    (item) => item.processing_status === "PROCESSED" && item.created_at >= todayIso
  ).length;
  const ignoredToday = messages.filter(
    (item) => item.processing_status === "IGNORED" && item.created_at >= todayIso
  ).length;
  const failedRecent = quotes.filter((item) => item.status === "ERROR").slice(0, 8);
  const averageExecution = averageMinutes(
    quotes.filter((item) => item.status === "DONE"),
    "started_at",
    "finished_at"
  );

  return {
    metrics: {
      workerStatus: isOnline ? "Online" : "Offline",
      lastHeartbeat: latestActivity,
      processedToday,
      ignoredToday,
      failureCount: failedRecent.length,
      averageExecution
    },
    recentExecutions: quotes.slice(0, 12),
    recentFailures: failedRecent,
    notices: Array.from(notices)
  };
}
