import { fetchAdminWorker } from "../adminWorker.js";
import { bootAdminPage, runAdminPageBoot } from "../adminPage.js";
import { formatDateTime, setHTML, setText, showFeedback } from "../ui.js";

function renderExecutions(rows) {
  if (!rows.length) {
    return '<tr><td colspan="6" class="app-empty">Nenhuma execucao recente encontrada.</td></tr>';
  }

  return rows
    .map(
      (row) => `
        <tr>
          <td>${row.id}</td>
          <td>${row.request_id || "-"}</td>
          <td>${row.status}</td>
          <td>${formatDateTime(row.started_at)}</td>
          <td>${formatDateTime(row.finished_at)}</td>
          <td>${row.error_message || "-"}</td>
        </tr>
      `
    )
    .join("");
}

function renderFailures(rows) {
  if (!rows.length) {
    return '<tr><td colspan="4" class="app-empty">Nenhuma falha recente.</td></tr>';
  }

  return rows
    .map(
      (row) => `
        <tr>
          <td>${row.request_id || "-"}</td>
          <td>${row.status}</td>
          <td>${row.error_message || "Erro sem detalhes"}</td>
          <td>${formatDateTime(row.updated_at || row.created_at)}</td>
        </tr>
      `
    )
    .join("");
}

async function init() {
  await bootAdminPage();

  try {
    const payload = await fetchAdminWorker();
    setText("#workerStatusValue", payload.metrics.workerStatus);
    setText("#workerHeartbeatValue", formatDateTime(payload.metrics.lastHeartbeat));
    setText("#workerProcessedToday", String(payload.metrics.processedToday));
    setText("#workerIgnoredToday", String(payload.metrics.ignoredToday));
    setText("#workerFailureCount", String(payload.metrics.failureCount));
    setText(
      "#workerAverageExecution",
      payload.metrics.averageExecution === null ? "Sem historico suficiente" : `${Math.round(payload.metrics.averageExecution * 10) / 10} min`
    );

    setHTML("#adminWorkerExecutionsBody", renderExecutions(payload.recentExecutions));
    setHTML("#adminWorkerFailuresBody", renderFailures(payload.recentFailures));

    if (payload.notices.length) {
      showFeedback("#adminWorkerFeedback", payload.notices.join(" "));
    }
  } catch (error) {
    showFeedback("#adminWorkerFeedback", error.message || "Não foi possível carregar a operação do worker.");
  }
}

runAdminPageBoot(init, "Carregando a operação do worker.").catch((error) => {
  showFeedback("#adminWorkerFeedback", error.message || "Erro ao iniciar a página do worker.");
});
