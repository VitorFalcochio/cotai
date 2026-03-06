from __future__ import annotations

import json
import re
import sys
import time
import unicodedata
from typing import Any

from .config import Settings, load_settings, validate_settings
from .services.ai_service import AIService
from .services.dedupe_service import DedupeService
from .services.search_service import SearchService
from .services.supabase_service import SupabaseService
from .services.whatsapp_service import WhatsAppService
from .utils.hashing import sha256_payload
from .utils.logger import log_event


def clean_text(text: str) -> str:
    text = re.sub(r"[\u200e\u200f\u202a-\u202e]", "", text or "")
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", clean_text(text).lower())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def extract_text(message: dict[str, Any]) -> str:
    candidates = [message.get("body"), message.get("text"), message.get("message"), message.get("caption")]
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()

    nested = message.get("content")
    if isinstance(nested, dict):
        for key in ("text", "body"):
            value = nested.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def extract_chat_id(chat: dict[str, Any]) -> str:
    for field in ("id", "chatId"):
        raw = chat.get(field)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
        if isinstance(raw, dict):
            for key in ("_serialized", "id"):
                value = raw.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
    return ""


def get_timestamp(message: dict[str, Any]) -> int:
    for key in ("timestamp", "t", "time", "messageTimestamp"):
        value = message.get(key)
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return 0


def is_incoming(message: dict[str, Any], accept_from_me: bool = False) -> bool:
    if accept_from_me:
        return True
    if "fromMe" in message:
        return not bool(message.get("fromMe"))
    if "isFromMe" in message:
        return not bool(message.get("isFromMe"))
    return True


def extract_message_id(message: dict[str, Any], chat_id: str) -> str:
    for key in ("id", "_id", "messageId"):
        value = message.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            for sub_key in ("_serialized", "id", "_id"):
                sub_value = value.get(sub_key)
                if isinstance(sub_value, str) and sub_value.strip():
                    return sub_value.strip()
    timestamp = get_timestamp(message)
    return f"{chat_id}:{timestamp}:{sha256_payload({'text': extract_text(message)})[:12]}"


def extract_request_code(text: str) -> str | None:
    match = re.search(r"pedido\s*(?:id)?\s*:\s*([A-Za-z0-9][A-Za-z0-9\-_/]*)", text, flags=re.IGNORECASE)
    return match.group(1).strip() if match else None


def canonical_delivery_mode(label: str | None) -> str | None:
    normalized = normalize_text(label or "")
    if not normalized:
        return None
    if "retirada" in normalized:
        return "RETIRADA"
    if "entrega" in normalized:
        return "ENTREGA"
    return None


def parse_item_line(line: str) -> dict[str, Any] | None:
    raw = re.sub(r"^[\-\*\•\s]+", "", line or "").strip()
    raw = re.sub(r"^\d+[\)\.]\s*", "", raw).strip()
    if not raw:
        return None

    units_pattern = r"(?:sacos?|un|m2|m²|m3|m³|m|latas?|caixas?|kg|g|l|barras?)"
    patterns = (
        rf"^(?P<name>.+?)\s*[-–—]\s*(?P<qty>\d+(?:[\.,]\d+)?)\s*(?P<unit>{units_pattern})\b",
        rf"^(?P<qty>\d+(?:[\.,]\d+)?)\s*(?P<unit>{units_pattern})\b\s*(?:de\s+)?(?P<name>.+)$",
        rf"^(?P<name>.+?)\s*\((?P<qty>\d+(?:[\.,]\d+)?)\s*(?P<unit>{units_pattern})\)\s*$",
    )

    for pattern in patterns:
        match = re.match(pattern, raw, flags=re.IGNORECASE)
        if not match:
            continue
        quantity = float(match.group("qty").replace(",", "."))
        unit = match.group("unit").lower().replace("m²", "m2").replace("m³", "m3")
        name = match.group("name").strip(" -")
        return {"raw": raw, "name": name, "quantity": quantity, "unit": unit}

    return {"raw": raw, "name": raw, "quantity": None, "unit": None}


def parse_request_message(text: str) -> dict[str, Any]:
    cleaned = clean_text(text)
    normalized = normalize_text(cleaned)
    parsed: dict[str, Any] = {
        "has_trigger": "#cotai" in normalized,
        "request_code": extract_request_code(cleaned),
        "delivery_mode": None,
        "delivery_location": None,
        "items": [],
    }
    if not parsed["has_trigger"]:
        return parsed

    lines = [line.strip() for line in cleaned.split("\n") if line.strip()]
    item_lines: list[str] = []
    in_items = False

    for line in lines:
        normalized_line = normalize_text(line)
        if normalized_line.startswith("#cotai") or "pedidoid" in normalized_line or "pedido id" in normalized_line:
            continue
        if normalized_line.startswith("entrega"):
            parsed["delivery_mode"] = "ENTREGA"
            delivery_context = line.split(":", 1)[-1].strip()
            if delivery_context and not parsed["delivery_location"]:
                parsed["delivery_location"] = delivery_context
            continue
        if normalized_line.startswith("retirada"):
            parsed["delivery_mode"] = "RETIRADA"
            pickup_context = line.split(":", 1)[-1].strip()
            if pickup_context and not parsed["delivery_location"]:
                parsed["delivery_location"] = pickup_context
            continue
        if normalized_line.startswith(("local", "cep", "endereco", "cidade", "bairro")):
            parsed["delivery_location"] = line.split(":", 1)[-1].strip()
            continue
        if any(normalized_line.startswith(prefix) for prefix in ("itens", "materiais", "lista", "produtos")):
            in_items = True
            inline = line.split(":", 1)[1].strip() if ":" in line else ""
            if inline:
                item_lines.extend([part.strip() for part in re.split(r"[;|]", inline) if part.strip()])
            continue
        if in_items or line.startswith("-") or line.startswith("•") or re.match(r"^\d+[\)\.]\s+", line):
            item_lines.append(line)

    parsed["items"] = [item for item in (parse_item_line(line) for line in item_lines) if item]
    return parsed


def request_item_name(item_row: dict[str, Any]) -> str:
    return str(item_row.get("item_name") or item_row.get("description") or item_row.get("item") or "").strip()


def build_quote_results(search_service: SearchService, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for item in items:
        item_name = request_item_name(item)
        if not item_name:
            continue
        offers, source = search_service.quote_item(item_name)
        results.append(
            {
                "item_name": item_name,
                "offers": offers,
                "source": source,
                "not_found": len(offers) == 0,
                "suggestion": search_service.suggest_search_term(item_name),
            }
        )
    return results


def run_test_mode() -> int:
    from .testing import InMemoryAIService, InMemorySearchService, InMemorySupabase, InMemoryWhatsAppService

    settings = load_settings()
    supabase = InMemorySupabase()
    whatsapp = InMemoryWhatsAppService(
        chats=[{"id": "5511999999999@c.us"}],
        messages={
            "5511999999999@c.us": [
                {
                    "id": "wamid.test-1",
                    "timestamp": 1710000001,
                    "body": "#COTAI\nPedidoID: CT-0101\nEntrega: obra ativa\nItens:\n- 20 saco cimento cp2 50kg\n- 3 m3 areia fina",
                    "fromMe": False,
                }
            ]
        },
    )
    app = WorkerApp(
        settings,
        supabase=supabase,
        whatsapp=whatsapp,
        search=InMemorySearchService(),
        ai=InMemoryAIService(),
    )
    app.sync_whatsapp_inbox()
    app.process_pending_requests()
    snapshot = {
        "requests": list(supabase.requests.values()),
        "request_items": supabase.request_items,
        "request_quotes": list(supabase.request_quotes.values()),
        "quote_results": supabase.quote_results,
        "sent_messages": whatsapp.sent_messages,
        "heartbeats": supabase.heartbeats,
    }
    print(json.dumps(snapshot, ensure_ascii=False, indent=2))
    return 0


class WorkerApp:
    def __init__(
        self,
        settings: Settings,
        supabase: SupabaseService | Any | None = None,
        whatsapp: WhatsAppService | Any | None = None,
        search: SearchService | Any | None = None,
        ai: AIService | Any | None = None,
    ) -> None:
        self.settings = settings
        self.supabase = supabase or SupabaseService(settings)
        self.dedupe = DedupeService(self.supabase)
        self.whatsapp = whatsapp or WhatsAppService(settings)
        self.search = search or SearchService(settings)
        self.ai = ai or AIService(settings)
        self._last_heartbeat_at = 0.0

    def close(self) -> None:
        for service in (self.supabase, self.whatsapp, self.search, self.ai):
            closer = getattr(service, "close", None)
            if callable(closer):
                closer()

    def healthcheck(self) -> int:
        payload = {
            "supabase": self.supabase.healthcheck(),
            "waha": self.whatsapp.healthcheck(),
            "legacy_google_sheets_enabled": self.settings.legacy_google_sheets_enabled,
        }
        payload["ok"] = payload["supabase"].get("ok") and payload["waha"].get("ok")
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

    def _upsert_request_from_message(self, chat_id: str, parsed: dict[str, Any], text: str) -> dict[str, Any]:
        request_code = parsed["request_code"]
        request_row = self.supabase.get_request_by_code(request_code)
        if request_row is None:
            company_id = self.supabase.resolve_worker_company_id()
            if not company_id:
                raise RuntimeError(
                    "Worker could not resolve company_id for inbound WhatsApp request. Configure WORKER_COMPANY_ID or create one active company."
                )
            return self.supabase.create_request_from_message(
                request_code=request_code,
                company_id=company_id,
                customer_name=chat_id,
                delivery_mode=canonical_delivery_mode(parsed.get("delivery_mode")),
                delivery_location=parsed.get("delivery_location"),
                notes=text,
                origin_chat_id=chat_id,
            )

        self.supabase.update_request(
            request_row["id"],
            {
                "status": "RECEIVED",
                "origin_chat_id": chat_id,
                "source_channel": "WHATSAPP",
                "delivery_mode": canonical_delivery_mode(parsed.get("delivery_mode")) or request_row.get("delivery_mode"),
                "delivery_location": parsed.get("delivery_location") or request_row.get("delivery_location"),
                "notes": request_row.get("notes") or text,
                "last_error": None,
            },
        )
        return request_row

    def _sync_request_items(self, request_id: Any, parsed_items: list[dict[str, Any]]) -> None:
        if parsed_items:
            self.supabase.ensure_request_items(request_id, parsed_items)

    def handle_incoming_message(self, chat_id: str, message: dict[str, Any]) -> None:
        if not is_incoming(message, accept_from_me=self.settings.accept_from_me):
            return

        text = extract_text(message)
        if not text:
            return

        parsed = parse_request_message(text)
        if not parsed["has_trigger"]:
            return

        message_id = extract_message_id(message, chat_id)
        if self.dedupe.already_processed(message_id):
            log_event(self.settings, "DEBUG", "Duplicate WhatsApp message ignored", chat_id=chat_id, message_id=message_id)
            return

        request_code = parsed.get("request_code")
        payload_hash = sha256_payload({"chat_id": chat_id, "message": message, "parsed": parsed})

        if not request_code:
            self.whatsapp.send_text(chat_id, "Envie a mensagem com #COTAI e um PedidoID: CT-0001.")
            self.dedupe.mark_processed(
                message_id=message_id,
                chat_id=chat_id,
                request_id=None,
                request_quote_id=None,
                status="FAILED",
                payload={"reason": "missing_request_code", "text": text},
                notes="Message ignored because request code was missing.",
            )
            log_event(
                self.settings,
                "ERROR",
                "Missing request code in incoming message",
                chat_id=chat_id,
                message_id=message_id,
                payload_hash=payload_hash,
            )
            return

        request_row = self._upsert_request_from_message(chat_id, parsed, text)
        self._sync_request_items(request_row["id"], parsed.get("items", []))

        self.dedupe.mark_processed(
            message_id=message_id,
            chat_id=chat_id,
            request_id=request_row.get("id"),
            request_quote_id=None,
            status="PROCESSED",
            payload={"text": text, "parsed": parsed, "payload_hash": payload_hash},
            notes="Inbound WhatsApp message persisted to request.",
        )

        log_event(
            self.settings,
            "INFO",
            "Incoming WhatsApp request registered",
            request_id=request_code,
            request_db_id=request_row.get("id"),
            chat_id=chat_id,
            message_id=message_id,
            item_count=len(parsed.get("items", [])),
            payload_hash=payload_hash,
        )

    def sync_whatsapp_inbox(self) -> None:
        chats = self.whatsapp.list_chats()
        chat_ids = [extract_chat_id(chat) for chat in chats if isinstance(chat, dict)]
        chat_ids = [chat_id for chat_id in chat_ids if chat_id.endswith("@c.us")]
        if self.settings.force_phone:
            forced = f"{self.settings.force_phone}@c.us"
            if forced not in chat_ids:
                chat_ids.append(forced)

        for chat_id in chat_ids:
            try:
                messages = self.whatsapp.get_messages(chat_id, limit=25)
            except Exception as exc:  # noqa: BLE001
                log_event(self.settings, "ERROR", "Failed to fetch WhatsApp messages", chat_id=chat_id, error=str(exc))
                continue

            incoming = [msg for msg in messages if isinstance(msg, dict) and is_incoming(msg, self.settings.accept_from_me)]
            incoming.sort(key=get_timestamp)
            for message in incoming:
                try:
                    self.handle_incoming_message(chat_id, message)
                except Exception as exc:  # noqa: BLE001
                    message_id = extract_message_id(message, chat_id)
                    log_event(
                        self.settings,
                        "ERROR",
                        "Failed to process inbound message",
                        chat_id=chat_id,
                        message_id=message_id,
                        error=str(exc),
                    )

    def _send_quote_reply(self, origin_chat_id: str | None, reply_text: str, request_code: str, request_quote_id: Any) -> None:
        if not origin_chat_id:
            return
        try:
            self.whatsapp.send_text(origin_chat_id, reply_text)
            log_event(
                self.settings,
                "INFO",
                "Quote response sent",
                request_id=request_code,
                request_quote_id=request_quote_id,
                chat_id=origin_chat_id,
            )
        except Exception as exc:  # noqa: BLE001
            log_event(
                self.settings,
                "ERROR",
                "Quote response could not be delivered after persistence",
                request_id=request_code,
                request_quote_id=request_quote_id,
                chat_id=origin_chat_id,
                error=str(exc),
            )

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
            self.supabase.update_quote_execution(request_quote_id, {"status": "QUOTING"})

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
                self._send_quote_reply(claimed.get("origin_chat_id"), reply_text, request_code, request_quote_id)
                log_event(
                    self.settings,
                    "INFO",
                    "Request quoted successfully",
                    request_id=request_code,
                    request_quote_id=request_quote_id,
                    item_count=len(quote_results),
                    ai_provider=ai_provider,
                )
            except Exception as exc:  # noqa: BLE001
                self.supabase.complete_quote_execution(
                    request_quote_id=request_quote_id,
                    status="ERROR",
                    error_message=str(exc),
                )
                self.supabase.mark_request_error(request_id, str(exc))
                log_event(
                    self.settings,
                    "ERROR",
                    "Request processing failed",
                    request_id=request_code,
                    request_quote_id=request_quote_id,
                    error=str(exc),
                )

    def run_forever(self) -> int:
        log_event(
            self.settings,
            "INFO",
            "Worker started",
            waha_session=self.settings.waha_session,
            supabase_url=self.settings.supabase_url,
            legacy_google_sheets_enabled=self.settings.legacy_google_sheets_enabled,
        )

        try:
            while True:
                try:
                    self.sync_whatsapp_inbox()
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
    argv = argv or sys.argv[1:]
    settings = load_settings()

    if settings.test_mode:
        return run_test_mode()

    if argv and argv[0] == "healthcheck":
        try:
            validate_settings(settings)
        except Exception as exc:  # noqa: BLE001
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
            return 1
        app = WorkerApp(settings)
        return app.healthcheck()

    validate_settings(settings)
    app = WorkerApp(settings)
    return app.run_forever()


if __name__ == "__main__":
    raise SystemExit(main())
