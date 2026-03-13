import { formatDateTime } from "./ui.js";

function currency(value) {
  const numeric = Number(value);
  return Number.isFinite(numeric)
    ? new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(numeric)
    : "-";
}

export function buildQuoteReport({ companyName, request, comparison, results }) {
  const rows = (results || [])
    .map(
      (row) => `
        <tr>
          <td>${row.item_name || "-"}</td>
          <td>${row.supplier_name || row.supplier || "-"}</td>
          <td>${currency(row.unit_price ?? row.price)}</td>
          <td>${currency(row.total_price ?? row.price)}</td>
          <td>${row.delivery_label || (row.delivery_days ? `${row.delivery_days} dia(s)` : "-")}</td>
          <td>${row.origin_label || row.source_name || "-"}</td>
          <td>${row.is_best_price ? "Melhor preço" : row.is_best_delivery ? "Melhor prazo" : row.is_best_overall ? "Melhor opção" : "-"}</td>
        </tr>
      `
    )
    .join("");

  return `
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
      <meta charset="UTF-8" />
      <title>Relatorio ${request.request_code || request.id}</title>
      <style>
        body { font-family: Arial, sans-serif; margin: 32px; color: #1a2433; }
        h1, h2 { margin: 0 0 12px; }
        .meta, .summary { margin-bottom: 24px; }
        .cards { display: flex; gap: 12px; margin: 16px 0 24px; }
        .card { border: 1px solid #d8dde6; border-radius: 12px; padding: 12px 16px; min-width: 180px; }
        table { width: 100%; border-collapse: collapse; }
        th, td { border: 1px solid #d8dde6; padding: 10px; text-align: left; font-size: 12px; }
        th { background: #f3f6fb; }
      </style>
    </head>
    <body>
      <h1>Cotai - Relatorio de Cotacao</h1>
      <div class="meta">
        <strong>Empresa:</strong> ${companyName || "-"}<br />
        <strong>Pedido:</strong> ${request.request_code || request.id}<br />
        <strong>Data:</strong> ${formatDateTime(request.created_at || request.createdAt)}<br />
        <strong>Status:</strong> ${request.status || "-"}
      </div>
      <div class="cards">
        <div class="card"><strong>Melhor preço</strong><div>${comparison?.best_price_supplier?.supplier || "-"}</div></div>
        <div class="card"><strong>Melhor prazo</strong><div>${comparison?.best_delivery_supplier?.supplier || "-"}</div></div>
        <div class="card"><strong>Melhor opcao geral</strong><div>${comparison?.best_supplier?.supplier || "-"}</div></div>
        <div class="card"><strong>Economia potencial</strong><div>${currency(comparison?.potential_savings)}</div></div>
      </div>
      <div class="summary">
        <h2>Resumo</h2>
        <p>${request.notes || request.last_error || "Comparativo estruturado de fornecedores, preço e prazo."}</p>
      </div>
      <table>
        <thead>
          <tr>
            <th>Item</th>
            <th>Fornecedor</th>
            <th>Preco unitario</th>
            <th>Preco total</th>
            <th>Prazo</th>
            <th>Origem</th>
            <th>Destaque</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </body>
    </html>
  `;
}

export function exportQuoteCsv({ request, results }) {
  const header = ["request_code", "item_name", "supplier", "unit_price", "total_price", "delivery_days", "source", "highlight"];
  const lines = [header]
    .concat(
      (results || []).map((row) => [
        request.request_code || request.id,
        row.item_name || "",
        row.supplier_name || row.supplier || "",
        row.unit_price ?? row.price ?? "",
        row.total_price ?? row.price ?? "",
        row.delivery_days ?? "",
        row.origin_label || row.source_name || "",
        row.is_best_price ? "best_price" : row.is_best_delivery ? "best_delivery" : row.is_best_overall ? "best_overall" : ""
      ])
    )
    .map((line) => line.map((cell) => `"${String(cell ?? "").replaceAll('"', '""')}"`).join(","))
    .join("\n");

  const blob = new Blob([lines], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `cotai-${request.request_code || request.id}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

export function printQuoteReport(payload) {
  const report = buildQuoteReport(payload);
  const popup = window.open("", "_blank", "noopener,noreferrer,width=1100,height=800");
  if (!popup) {
    throw new Error("Não foi possível abrir a janela de exportação.");
  }
  popup.document.open();
  popup.document.write(report);
  popup.document.close();
  popup.focus();
  popup.print();
}
