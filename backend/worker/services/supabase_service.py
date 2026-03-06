from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import requests
from requests import HTTPError

from ..config import Settings
from ..utils.retry import retry_call


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


class SupabaseService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.session = requests.Session()
        self.rest_url = f"{settings.supabase_url}/rest/v1"
        self.auth_url = f"{settings.supabase_url}/auth/v1"

    def _headers(self, prefer: str | None = None) -> dict[str, str]:
        headers = {
            "apikey": self.settings.supabase_service_role_key,
            "Authorization": f"Bearer {self.settings.supabase_service_role_key}",
            "Content-Type": "application/json",
            "Accept-Profile": self.settings.supabase_schema,
            "Content-Profile": self.settings.supabase_schema,
        }
        if prefer:
            headers["Prefer"] = prefer
        return headers

    def _request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        timeout = kwargs.pop("timeout", self.settings.request_timeout_seconds)

        def do_request() -> requests.Response:
            response = self.session.request(method, url, timeout=timeout, **kwargs)
            if response.status_code in {408, 409, 425, 429, 500, 502, 503, 504}:
                response.raise_for_status()
            return response

        return retry_call(
            do_request,
            attempts=self.settings.retry_attempts,
            backoff_seconds=self.settings.retry_backoff_seconds,
            max_backoff_seconds=max(self.settings.retry_backoff_seconds, self.settings.request_timeout_seconds),
        )

    def close(self) -> None:
        self.session.close()

    def _table_url(self, table: str) -> str:
        return f"{self.rest_url}/{table}"

    def healthcheck(self) -> dict[str, Any]:
        checks: dict[str, Any] = {}
        try:
            auth_response = self._request(
                "GET",
                f"{self.auth_url}/settings",
                headers={"apikey": self.settings.supabase_service_role_key},
                timeout=self.settings.healthcheck_timeout_seconds,
            )
            checks["auth"] = {"ok": auth_response.ok, "status_code": auth_response.status_code}
        except Exception as exc:  # noqa: BLE001
            checks["auth"] = {"ok": False, "error": str(exc)}

        try:
            rest_response = self._request(
                "GET",
                self._table_url("requests"),
                params={"select": "id", "limit": 1},
                headers=self._headers(),
                timeout=self.settings.healthcheck_timeout_seconds,
            )
            checks["requests_table"] = {"ok": rest_response.ok, "status_code": rest_response.status_code}
        except Exception as exc:  # noqa: BLE001
            checks["requests_table"] = {"ok": False, "error": str(exc)}

        for table in ("request_items", "quote_results", "request_quotes", "worker_processed_messages"):
            try:
                response = self._request(
                    "GET",
                    self._table_url(table),
                    params={"select": "*", "limit": 1},
                    headers=self._headers(),
                    timeout=self.settings.healthcheck_timeout_seconds,
                )
                checks[table] = {"ok": response.ok, "status_code": response.status_code}
            except Exception as exc:  # noqa: BLE001
                checks[table] = {"ok": False, "error": str(exc)}

        checks["ok"] = all(item.get("ok") for item in checks.values())
        return checks

    def table_exists(self, table: str) -> bool:
        try:
            response = self._request(
                "GET",
                self._table_url(table),
                params={"select": "*", "limit": 1},
                headers=self._headers(),
                timeout=self.settings.healthcheck_timeout_seconds,
            )
            return response.ok
        except Exception:
            return False

    def get_request_by_code(self, request_code: str) -> dict[str, Any] | None:
        response = self._request(
            "GET",
            self._table_url("requests"),
            params={"select": "*", "request_code": f"eq.{request_code}", "limit": 1},
            headers=self._headers(),
        )
        response.raise_for_status()
        payload = response.json()
        return payload[0] if isinstance(payload, list) and payload else None

    def resolve_worker_company_id(self) -> str | None:
        if self.settings.worker_company_id:
            return self.settings.worker_company_id

        response = self._request(
            "GET",
            self._table_url("companies"),
            params={"select": "id,status", "status": "eq.active", "order": "created_at.asc", "limit": 2},
            headers=self._headers(),
        )
        response.raise_for_status()
        rows = response.json()
        if not isinstance(rows, list) or not rows:
            return None
        if len(rows) == 1:
            return rows[0].get("id")
        raise RuntimeError(
            "WORKER_COMPANY_ID is required because multiple active companies exist and inbound WhatsApp messages cannot be mapped automatically."
        )

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
        payload = {
            "request_code": request_code,
            "company_id": company_id,
            "customer_name": customer_name,
            "delivery_mode": delivery_mode,
            "delivery_location": delivery_location,
            "notes": notes,
            "status": "RECEIVED",
            "source_channel": "WHATSAPP",
            "origin_chat_id": origin_chat_id,
            "updated_at": utc_now_iso(),
        }
        response = self._request(
            "POST",
            self._table_url("requests"),
            headers=self._headers(prefer="return=representation"),
            json=payload,
        )
        try:
            response.raise_for_status()
        except HTTPError as exc:
            if response.status_code == 409:
                existing = self.get_request_by_code(request_code)
                if existing is not None:
                    return existing
            if response.status_code >= 400:
                raise RuntimeError(f"Failed to create request: {response.text}") from exc
            raise exc
        payload = response.json()
        if not isinstance(payload, list) or not payload:
            raise RuntimeError("Supabase did not return the inserted request.")
        return payload[0]

    def update_request(self, request_id: Any, payload: dict[str, Any]) -> dict[str, Any] | None:
        merged_payload = {"updated_at": utc_now_iso(), **payload}
        response = self._request(
            "PATCH",
            self._table_url("requests"),
            params={"id": f"eq.{request_id}"},
            headers=self._headers(prefer="return=representation"),
            json=merged_payload,
        )
        response.raise_for_status()
        rows = response.json()
        return rows[0] if isinstance(rows, list) and rows else None

    def fetch_pending_requests(self, limit: int) -> list[dict[str, Any]]:
        response = self._request(
            "GET",
            self._table_url("requests"),
            params={
                "select": "*",
                "status": "in.(NEW,RECEIVED)",
                "order": "created_at.asc",
                "limit": limit,
            },
            headers=self._headers(),
        )
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, list) else []

    def claim_request(self, request_id: Any) -> dict[str, Any] | None:
        response = self._request(
            "PATCH",
            self._table_url("requests"),
            params={"id": f"eq.{request_id}", "status": "in.(NEW,RECEIVED)"},
            headers=self._headers(prefer="return=representation"),
            json={"status": "QUOTING", "updated_at": utc_now_iso()},
        )
        response.raise_for_status()
        rows = response.json()
        return rows[0] if isinstance(rows, list) and rows else None

    def get_request_items(self, request_id: Any) -> list[dict[str, Any]]:
        response = self._request(
            "GET",
            self._table_url("request_items"),
            params={"select": "*", "request_id": f"eq.{request_id}", "order": "line_number.asc.nullslast"},
            headers=self._headers(),
        )
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, list) else []

    def insert_request_items(self, request_id: Any, items: list[dict[str, Any]] | list[str]) -> None:
        normalized_items: list[dict[str, Any]] = []
        for index, item in enumerate(items, start=1):
            if isinstance(item, dict):
                item_name = str(item.get("name") or item.get("item_name") or item.get("description") or item.get("raw") or "").strip()
                raw_text = str(item.get("raw") or item_name).strip()
                normalized_items.append(
                    {
                        "request_id": request_id,
                        "item_name": item_name or raw_text,
                        "raw_text": raw_text or item_name,
                        "qty": item.get("quantity"),
                        "unit": item.get("unit"),
                        "line_number": index,
                    }
                )
            else:
                raw_text = str(item).strip()
                normalized_items.append(
                    {
                        "request_id": request_id,
                        "item_name": raw_text,
                        "raw_text": raw_text,
                        "line_number": index,
                    }
                )

        payload_variants = [
            normalized_items,
            [
                {
                    "request_id": row["request_id"],
                    "item_name": row["item_name"],
                    "line_number": row["line_number"],
                }
                for row in normalized_items
            ],
        ]

        last_error: Exception | None = None
        for payload in payload_variants:
            try:
                response = self._request(
                    "POST",
                    self._table_url("request_items"),
                    headers=self._headers(prefer="return=minimal"),
                    json=payload,
                )
                response.raise_for_status()
                return
            except Exception as exc:  # noqa: BLE001
                last_error = exc

        if last_error is not None:
            raise last_error

    def ensure_request_items(self, request_id: Any, items: list[dict[str, Any]] | list[str]) -> None:
        existing = self.get_request_items(request_id)
        existing_names = {
            str(item.get("item_name") or item.get("description") or "").strip().casefold()
            for item in existing
            if str(item.get("item_name") or item.get("description") or "").strip()
        }
        pending: list[dict[str, Any]] | list[str] = []
        for item in items:
            if isinstance(item, dict):
                item_name = str(item.get("name") or item.get("item_name") or item.get("description") or item.get("raw") or "").strip()
                if item_name and item_name.casefold() not in existing_names:
                    pending.append(item)
            else:
                item_name = str(item).strip()
                if item_name and item_name.casefold() not in existing_names:
                    pending.append(item_name)
        if pending:
            self.insert_request_items(request_id, pending)

    def is_message_processed(self, message_id: str) -> bool:
        response = self._request(
            "GET",
            self._table_url("worker_processed_messages"),
            params={"select": "message_id", "message_id": f"eq.{message_id}", "limit": 1},
            headers=self._headers(),
        )
        response.raise_for_status()
        payload = response.json()
        return isinstance(payload, list) and len(payload) > 0

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
        response = self._request(
            "POST",
            self._table_url("worker_processed_messages"),
            headers=self._headers(prefer="return=minimal,resolution=ignore-duplicates"),
            json={
                "message_id": message_id,
                "chat_id": chat_id,
                "request_id": request_id,
                "request_quote_id": request_quote_id,
                "payload_hash": payload_hash,
                "processing_status": processing_status,
                "notes": notes,
                "created_at": utc_now_iso(),
            },
        )
        response.raise_for_status()

    def get_latest_quote_execution(self, request_id: Any) -> dict[str, Any] | None:
        response = self._request(
            "GET",
            self._table_url("request_quotes"),
            params={
                "select": "*",
                "request_id": f"eq.{request_id}",
                "order": "created_at.desc",
                "limit": 1,
            },
            headers=self._headers(),
        )
        response.raise_for_status()
        rows = response.json()
        return rows[0] if isinstance(rows, list) and rows else None

    def create_quote_execution(self, request_id: Any, status: str = "RECEIVED") -> dict[str, Any]:
        response = self._request(
            "POST",
            self._table_url("request_quotes"),
            headers=self._headers(prefer="return=representation"),
            json={
                "request_id": request_id,
                "status": status,
                "started_at": utc_now_iso(),
                "created_at": utc_now_iso(),
                "updated_at": utc_now_iso(),
            },
        )
        response.raise_for_status()
        rows = response.json()
        if not isinstance(rows, list) or not rows:
            raise RuntimeError("Supabase did not return the inserted request quote execution.")
        return rows[0]

    def get_or_create_active_quote_execution(self, request_id: Any) -> dict[str, Any]:
        latest = self.get_latest_quote_execution(request_id)
        if latest and latest.get("status") in {"RECEIVED", "QUOTING"}:
            return latest
        return self.create_quote_execution(request_id=request_id, status="RECEIVED")

    def update_quote_execution(self, request_quote_id: Any, payload: dict[str, Any]) -> dict[str, Any] | None:
        merged_payload = {"updated_at": utc_now_iso(), **payload}
        response = self._request(
            "PATCH",
            self._table_url("request_quotes"),
            params={"id": f"eq.{request_quote_id}"},
            headers=self._headers(prefer="return=representation"),
            json=merged_payload,
        )
        response.raise_for_status()
        rows = response.json()
        return rows[0] if isinstance(rows, list) and rows else None

    def replace_quote_results(self, request_id: Any, request_quote_id: Any, quote_results: list[dict[str, Any]]) -> None:
        delete_response = self._request(
            "DELETE",
            self._table_url("quote_results"),
            params={"request_quote_id": f"eq.{request_quote_id}"},
            headers=self._headers(prefer="return=minimal"),
        )
        delete_response.raise_for_status()

        rows = []
        position = 0
        for item_result in quote_results:
            item_name = item_result.get("item_name", "")
            for offer in item_result.get("offers", []):
                position += 1
                rows.append(
                    {
                        "request_id": request_id,
                        "request_quote_id": request_quote_id,
                        "item_name": item_name,
                        "title": offer.get("title"),
                        "supplier": offer.get("supplier"),
                        "price": offer.get("price"),
                        "link": offer.get("link"),
                        "source": offer.get("source") or item_result.get("source"),
                        "position": position,
                        "raw_payload": offer,
                    }
                )

        if not rows:
            return

        payload_variants = [
            rows,
            [
                {
                    "request_id": row["request_id"],
                    "request_quote_id": row["request_quote_id"],
                    "item_name": row["item_name"],
                    "title": row["title"],
                    "supplier_name": row["supplier"],
                    "price": row["price"],
                    "result_url": row["link"],
                    "source_name": row["source"],
                    "position": row["position"],
                    "raw_payload": row["raw_payload"],
                }
                for row in rows
            ],
        ]

        last_error: Exception | None = None
        for payload in payload_variants:
            try:
                response = self._request(
                    "POST",
                    self._table_url("quote_results"),
                    headers=self._headers(prefer="return=minimal"),
                    json=payload,
                )
                response.raise_for_status()
                return
            except Exception as exc:  # noqa: BLE001
                last_error = exc

        if last_error is not None:
            raise last_error

    def complete_quote_execution(
        self,
        request_quote_id: Any,
        status: str,
        response_text: str = "",
        source_summary: str = "",
        error_message: str = "",
    ) -> None:
        payload = {
            "status": status,
            "finished_at": utc_now_iso(),
            "response_text": response_text or None,
            "source_summary": source_summary or None,
            "error_message": error_message or None,
        }
        self.update_quote_execution(request_quote_id, payload)

    def record_heartbeat(self, worker_name: str, status: str, details: dict[str, Any] | None = None) -> None:
        response = self._request(
            "POST",
            self._table_url("worker_heartbeats"),
            headers=self._headers(prefer="return=minimal"),
            json={
                "worker_name": worker_name,
                "status": status,
                "details": details or {},
                "created_at": utc_now_iso(),
            },
        )
        response.raise_for_status()

    def mark_request_received(self, request_id: Any) -> None:
        self.update_request(request_id, {"status": "RECEIVED"})

    def mark_request_quoting(self, request_id: Any) -> None:
        self.update_request(request_id, {"status": "QUOTING"})

    def mark_request_error(self, request_id: Any, error_message: str) -> None:
        self.update_request(request_id, {"status": "ERROR", "last_error": error_message[:500]})

    def mark_request_done(self, request_id: Any) -> None:
        self.update_request(
            request_id,
            {
                "status": "DONE",
                "last_error": None,
                "processed_at": utc_now_iso(),
            },
        )
