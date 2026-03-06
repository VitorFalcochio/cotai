from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class InMemorySupabase:
    worker_company_id: str = "company-1"
    requests: dict[str, dict[str, Any]] = field(default_factory=dict)
    request_items: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    request_quotes: dict[str, dict[str, Any]] = field(default_factory=dict)
    quote_results: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    processed_messages: set[str] = field(default_factory=set)
    heartbeats: list[dict[str, Any]] = field(default_factory=list)
    _request_counter: int = 0
    _quote_counter: int = 0

    def healthcheck(self) -> dict[str, Any]:
        return {"ok": True}

    def close(self) -> None:
        return None

    def get_request_by_code(self, request_code: str) -> dict[str, Any] | None:
        return self.requests.get(request_code)

    def resolve_worker_company_id(self) -> str | None:
        return self.worker_company_id

    def create_request_from_message(
        self,
        request_code: str,
        company_id: str | None,
        customer_name: str,
        delivery_mode: str | None,
        delivery_location: str | None,
        notes: str,
        origin_chat_id: str,
    ) -> dict[str, Any]:
        existing = self.requests.get(request_code)
        if existing is not None:
            return existing
        self._request_counter += 1
        request_id = f"req-{self._request_counter}"
        row = {
            "id": request_id,
            "request_code": request_code,
            "company_id": company_id,
            "customer_name": customer_name,
            "delivery_mode": delivery_mode,
            "delivery_location": delivery_location,
            "notes": notes,
            "status": "RECEIVED",
            "origin_chat_id": origin_chat_id,
        }
        self.requests[request_code] = row
        return row

    def update_request(self, request_id: Any, payload: dict[str, Any]) -> dict[str, Any] | None:
        for row in self.requests.values():
            if row["id"] == request_id:
                row.update(payload)
                return row
        return None

    def get_request_items(self, request_id: Any) -> list[dict[str, Any]]:
        return list(self.request_items.get(str(request_id), []))

    def insert_request_items(self, request_id: Any, items: list[str]) -> None:
        rows = self.request_items.setdefault(str(request_id), [])
        next_line = len(rows) + 1
        for index, item in enumerate(items, start=next_line):
            if isinstance(item, dict):
                rows.append(
                    {
                        "request_id": request_id,
                        "item_name": item.get("name") or item.get("item_name") or item.get("raw"),
                        "raw_text": item.get("raw") or item.get("name") or item.get("item_name"),
                        "line_number": index,
                    }
                )
            else:
                rows.append({"request_id": request_id, "item_name": item, "raw_text": item, "line_number": index})

    def ensure_request_items(self, request_id: Any, items: list[dict[str, Any]] | list[str]) -> None:
        existing = {row["item_name"].casefold() for row in self.get_request_items(request_id)}
        pending = []
        for item in items:
            name = item.get("name") if isinstance(item, dict) else item
            if name.casefold() not in existing:
                pending.append(item)
        if pending:
            self.insert_request_items(request_id, pending)

    def is_message_processed(self, message_id: str) -> bool:
        return message_id in self.processed_messages

    def record_processed_message(
        self,
        message_id: str,
        chat_id: str,
        request_id: Any | None,
        request_quote_id: Any | None,
        payload_hash: str,
        processing_status: str,
        notes: str = "",
    ) -> None:
        self.processed_messages.add(message_id)

    def fetch_pending_requests(self, limit: int) -> list[dict[str, Any]]:
        pending = [row for row in self.requests.values() if row.get("status") in {"NEW", "RECEIVED"}]
        return pending[:limit]

    def claim_request(self, request_id: Any) -> dict[str, Any] | None:
        for row in self.requests.values():
            if row["id"] == request_id and row.get("status") in {"NEW", "RECEIVED"}:
                row["status"] = "QUOTING"
                return row
        return None

    def get_latest_quote_execution(self, request_id: Any) -> dict[str, Any] | None:
        matches = [row for row in self.request_quotes.values() if row["request_id"] == request_id]
        return matches[-1] if matches else None

    def create_quote_execution(self, request_id: Any, status: str = "RECEIVED") -> dict[str, Any]:
        self._quote_counter += 1
        quote_id = f"rq-{self._quote_counter}"
        row = {"id": quote_id, "request_id": request_id, "status": status}
        self.request_quotes[quote_id] = row
        return row

    def get_or_create_active_quote_execution(self, request_id: Any) -> dict[str, Any]:
        latest = self.get_latest_quote_execution(request_id)
        if latest and latest.get("status") in {"RECEIVED", "QUOTING"}:
            return latest
        return self.create_quote_execution(request_id, status="RECEIVED")

    def update_quote_execution(self, request_quote_id: Any, payload: dict[str, Any]) -> dict[str, Any] | None:
        row = self.request_quotes.get(str(request_quote_id))
        if row is None:
            return None
        row.update(payload)
        return row

    def replace_quote_results(self, request_id: Any, request_quote_id: Any, quote_results: list[dict[str, Any]]) -> None:
        self.quote_results[str(request_quote_id)] = quote_results

    def complete_quote_execution(
        self,
        request_quote_id: Any,
        status: str,
        response_text: str = "",
        source_summary: str = "",
        error_message: str = "",
    ) -> None:
        row = self.request_quotes[str(request_quote_id)]
        row.update(
            {
                "status": status,
                "response_text": response_text,
                "source_summary": source_summary,
                "error_message": error_message,
            }
        )

    def mark_request_quoting(self, request_id: Any) -> None:
        self.update_request(request_id, {"status": "QUOTING"})

    def mark_request_error(self, request_id: Any, error_message: str) -> None:
        self.update_request(request_id, {"status": "ERROR", "last_error": error_message})

    def mark_request_done(self, request_id: Any) -> None:
        self.update_request(request_id, {"status": "DONE", "last_error": None})

    def record_heartbeat(self, worker_name: str, status: str, details: dict[str, Any] | None = None) -> None:
        self.heartbeats.append({"worker_name": worker_name, "status": status, "details": details or {}})


class InMemorySearchService:
    def quote_item(self, item_name: str) -> tuple[list[dict[str, Any]], str]:
        return (
            [
                {
                    "title": f"{item_name} premium",
                    "price": 10.0,
                    "supplier": "Local Supplier",
                    "link": "https://example.test/item",
                    "source": "catalog",
                }
            ],
            "catalog",
        )

    def suggest_search_term(self, item_name: str) -> str:
        return item_name


class InMemoryAIService:
    def summarize_quote(self, request_code: str, results: list[dict[str, Any]]) -> tuple[str, str]:
        return f"Resumo local para {request_code} com {len(results)} item(ns).", "local"


@dataclass
class InMemoryWhatsAppService:
    chats: list[dict[str, Any]] = field(default_factory=list)
    messages: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    sent_messages: list[dict[str, Any]] = field(default_factory=list)
    fail_sends: bool = False

    def healthcheck(self) -> dict[str, Any]:
        return {"ok": True}

    def close(self) -> None:
        return None

    def list_chats(self) -> list[dict[str, Any]]:
        return list(self.chats)

    def get_messages(self, chat_id: str, limit: int = 25) -> list[dict[str, Any]]:
        return list(self.messages.get(chat_id, []))[:limit]

    def send_text(self, chat_id: str, text: str) -> dict[str, Any]:
        if self.fail_sends:
            raise RuntimeError("Simulated send failure")
        payload = {"chat_id": chat_id, "text": text}
        self.sent_messages.append(payload)
        return payload
