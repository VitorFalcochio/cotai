from __future__ import annotations

import json
import sys
import time
from typing import Any

from .agent.engine import AgentQuoteEngine
from .config import Settings, load_settings, validate_settings
from .services.ai_service import AIService
from .services.search_service import SearchService
from .services.supabase_service import SupabaseService
from .utils.logger import log_event
from .utils.telemetry import telemetry
from ..shared.request_parser import parse_request_message


def request_item_name(item_row: dict[str, Any]) -> str:
    return str(item_row.get("item_name") or item_row.get("description") or item_row.get("item") or "").strip()


def build_quote_results(search_service: SearchService, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    engine = AgentQuoteEngine(search_service)
    results: list[dict[str, Any]] = []
    for item in items:
        item_name = request_item_name(item)
        if not item_name:
            continue
        results.append(engine.build_item_quote(item))
    return results


def run_test_mode() -> int:
    from .testing import InMemoryAIService, InMemorySearchService, InMemorySupabase

    settings = load_settings()
    supabase = InMemorySupabase()
    thread = supabase.create_chat_thread(user_id="user-1", company_id="company-1", title="Nova cotacao")
    supabase.create_internal_request(
        company_id="company-1",
        user_id="user-1",
        thread_id=thread["id"],
        customer_name="Cotai Teste",
        notes="Preciso de 20 sacos de cimento e 3 m3 de areia fina",
        items=[
            {"name": "cimento cp2 50kg", "normalized_name": "cimento cp2 50kg", "quantity": 20.0, "unit": "saco", "raw": "20 saco cimento cp2 50kg"},
            {"name": "areia fina", "normalized_name": "areia fina", "quantity": 3.0, "unit": "m3", "raw": "3 m3 areia fina"},
        ],
    )
    app = WorkerApp(
        settings,
        supabase=supabase,
        search=InMemorySearchService(),
        ai=InMemoryAIService(),
    )
    app.process_pending_requests()
    snapshot = {
        "requests": list(supabase.requests.values()),
        "request_items": supabase.request_items,
        "request_quotes": list(supabase.request_quotes.values()),
        "quote_results": supabase.quote_results,
        "heartbeats": supabase.heartbeats,
        "chat_messages": supabase.chat_messages,
    }
    print(json.dumps(snapshot, ensure_ascii=False, indent=2))
    return 0


class WorkerApp:
    def __init__(
        self,
        settings: Settings,
        supabase: SupabaseService | Any | None = None,
        search: SearchService | Any | None = None,
        ai: AIService | Any | None = None,
    ) -> None:
        self.settings = settings
        self.supabase = supabase or SupabaseService(settings)
        self.search = search or SearchService(settings)
        self.ai = ai or AIService(settings)
        self._last_heartbeat_at = 0.0

    def close(self) -> None:
        for service in (self.supabase, self.search, self.ai):
            closer = getattr(service, "close", None)
            if callable(closer):
                closer()

    def healthcheck(self) -> int:
        payload = {
            "supabase": self.supabase.healthcheck(),
            "legacy_google_sheets_enabled": self.settings.legacy_google_sheets_enabled,
        }
        payload["ok"] = payload["supabase"].get("ok")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if payload["ok"] else 1

    def _emit_heartbeat(self, status: str, **details: Any) -> None:
        now = time.time()
        if status == "online" and now - self._last_heartbeat_at < self.settings.heartbeat_seconds:
            return
        heartbeat = {
            "poll_seconds": self.settings.poll_seconds,
            "requests_per_cycle": self.settings.requests_per_cycle,
            **details,
        }
        try:
            self.supabase.record_heartbeat("cotai-worker", status, heartbeat)
        except Exception as exc:  # noqa: BLE001
            log_event(self.settings, "ERROR", "Failed to record worker heartbeat", status=status, error=str(exc))
        self._last_heartbeat_at = now
        log_event(self.settings, "INFO", "Worker heartbeat", status=status, **heartbeat)

    def _publish_chat_update(self, request_row: dict[str, Any], content: str, status: str) -> None:
        thread_id = request_row.get("chat_thread_id")
        if not thread_id:
            return
        try:
            self.supabase.insert_chat_message(
                thread_id,
                "assistant",
                content,
                {"request_id": request_row.get("id"), "request_code": request_row.get("request_code"), "status": status},
            )
            self.supabase.update_chat_thread(thread_id, {"status": status})
        except Exception as exc:  # noqa: BLE001
            log_event(self.settings, "ERROR", "Failed to persist chat assistant update", request_id=request_row.get("id"), error=str(exc))

    def _send_quote_reply(self, request_row: dict[str, Any], reply_text: str, request_quote_id: Any) -> None:
        self._publish_chat_update(request_row, reply_text, "DONE")
        log_event(
            self.settings,
            "INFO",
            "Quote response published to internal chat",
            request_id=request_row.get("request_code"),
            request_quote_id=request_quote_id,
            thread_id=request_row.get("chat_thread_id"),
        )
        telemetry.record("worker_quote_reply_published")

    def process_pending_requests(self) -> None:
        pending = self.supabase.fetch_pending_requests(self.settings.requests_per_cycle)
        for request_row in pending:
            request_id = request_row["id"]
            request_code = request_row.get("request_code") or str(request_id)
            claimed = self.supabase.claim_request(request_id)
            if not claimed:
                continue

            quote_execution = self.supabase.get_or_create_active_quote_execution(request_id)
            request_quote_id = quote_execution["id"]
            self.supabase.mark_request_quoting(request_id)
            self.supabase.update_quote_execution(request_quote_id, {"status": "QUOTING", "started_at": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())})

            try:
                items = self.supabase.get_request_items(request_id)
                quote_results = build_quote_results(self.search, items)
                if not quote_results:
                    raise RuntimeError("No request items found for quotation.")

                self.supabase.replace_quote_results(request_id, request_quote_id, quote_results)
                reply_text, ai_provider = self.ai.summarize_quote(request_code, quote_results)
                self.supabase.complete_quote_execution(
                    request_quote_id=request_quote_id,
                    status="DONE",
                    response_text=reply_text,
                    source_summary=ai_provider,
                )
                self.supabase.mark_request_done(request_id)
                self._send_quote_reply(claimed, reply_text, request_quote_id)
                log_event(
                    self.settings,
                    "INFO",
                    "Request quoted successfully",
                    request_id=request_code,
                    request_quote_id=request_quote_id,
                    item_count=len(quote_results),
                    ai_provider=ai_provider,
                )
                telemetry.record("worker_request_completed", status="done", ai_provider=ai_provider)
            except Exception as exc:  # noqa: BLE001
                self.supabase.complete_quote_execution(
                    request_quote_id=request_quote_id,
                    status="ERROR",
                    error_message=str(exc),
                )
                self.supabase.mark_request_error(request_id, str(exc))
                self._publish_chat_update(claimed, f"Nao foi possivel concluir a cotacao do pedido {request_code}. {str(exc)}", "ERROR")
                log_event(
                    self.settings,
                    "ERROR",
                    "Request processing failed",
                    request_id=request_code,
                    request_quote_id=request_quote_id,
                    error=str(exc),
                )
                telemetry.record("worker_request_completed", status="error")

    def run_forever(self) -> int:
        log_event(
            self.settings,
            "INFO",
            "Worker started",
            supabase_url=self.settings.supabase_url,
            legacy_google_sheets_enabled=self.settings.legacy_google_sheets_enabled,
        )

        try:
            while True:
                try:
                    self.process_pending_requests()
                    self._emit_heartbeat("online")
                except KeyboardInterrupt:
                    log_event(self.settings, "INFO", "Worker interrupted")
                    return 0
                except Exception as exc:  # noqa: BLE001
                    self._emit_heartbeat("degraded", error=str(exc))
                    log_event(self.settings, "ERROR", "Worker main loop failed", error=repr(exc))
                time.sleep(self.settings.poll_seconds)
        finally:
            self.close()


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    settings = load_settings()
    validate_settings(settings)

    if settings.test_mode:
        return run_test_mode()

    app = WorkerApp(settings)

    if args and args[0].lower() == "healthcheck":
        try:
            return app.healthcheck()
        finally:
            app.close()

    return app.run_forever()


if __name__ == "__main__":
    raise SystemExit(main())
