from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from .request_parser import RequestParserService
from .supabase_service import SupabaseService


class ChatService:
    def __init__(self, supabase: SupabaseService, parser: RequestParserService) -> None:
        self.supabase = supabase
        self.parser = parser

    def handle_message(self, *, actor: dict[str, Any], thread_id: str | None, message: str) -> dict[str, Any]:
        profile = actor["profile"]
        company_id = profile.get("company_id")
        if not company_id:
            raise RuntimeError("Seu perfil ainda não está vinculado a uma empresa.")

        thread = self._load_or_create_thread(actor, thread_id, message)
        metadata = thread.get("metadata") or {}
        self.supabase.insert_chat_message(thread["id"], "user", message, {"kind": "prompt"})

        parsed = self.parser.parse_user_message(message)
        if not parsed["items"]:
            assistant_text = (
                "Não consegui identificar os materiais com segurança. "
                "Descreva os itens em linguagem direta, por exemplo: 50 sacos de cimento, 20 barras de ferro 10mm e 5 m3 de areia media."
            )
            updated_metadata = {
                **metadata,
                "draft_saved_at": datetime.now(UTC).isoformat(),
                "last_user_message": message,
                "timeline": self._append_timeline(metadata, "Rascunho salvo automaticamente."),
            }
            self.supabase.insert_chat_message(thread["id"], "assistant", assistant_text, {"status": "DRAFT"})
            self.supabase.update_chat_thread(thread["id"], {"status": "DRAFT", "metadata": {**updated_metadata, "pending_items": metadata.get("pending_items") or []}})
            return self.get_thread_payload(actor, thread["id"])

        items = self._merge_items(metadata.get("pending_items") or [], parsed["items"])
        confirmation = self.parser.build_confirmation(items)
        updated_metadata = {
            **metadata,
            "pending_items": items,
            "parse_provider": parsed["provider"],
            "confirmation_provider": confirmation["provider"],
            "last_user_message": message,
            "draft_saved_at": datetime.now(UTC).isoformat(),
            "timeline": self._append_timeline(metadata, f"{len(items)} item(ns) preparados para confirmacao."),
        }
        self.supabase.insert_chat_message(
            thread["id"],
            "assistant",
            confirmation["message"],
            {"status": "AWAITING_CONFIRMATION", "preview": confirmation["preview"]},
        )
        self.supabase.update_chat_thread(thread["id"], {"status": "AWAITING_CONFIRMATION", "metadata": updated_metadata})
        return self.get_thread_payload(actor, thread["id"])

    def update_draft(self, *, actor: dict[str, Any], thread_id: str, draft_data: dict[str, Any]) -> dict[str, Any]:
        thread = self.supabase.get_chat_thread(thread_id, actor["user"]["id"])
        if not thread:
            raise RuntimeError("Thread não encontrada.")

        metadata = thread.get("metadata") or {}
        items = [self.parser._normalize_item(item) for item in draft_data.get("items") or []]  # noqa: SLF001
        normalized_items = [item for item in items if item]
        next_status = "AWAITING_CONFIRMATION" if normalized_items else "DRAFT"
        merged_metadata = {
            **metadata,
            "pending_items": normalized_items,
            "delivery_mode": draft_data.get("delivery_mode") or metadata.get("delivery_mode"),
            "delivery_location": draft_data.get("delivery_location") or metadata.get("delivery_location"),
            "draft_notes": draft_data.get("notes") or metadata.get("draft_notes"),
            "priority": draft_data.get("priority") or metadata.get("priority"),
            "draft_saved_at": datetime.now(UTC).isoformat(),
            "timeline": self._append_timeline(metadata, "Rascunho atualizado manualmente."),
        }
        self.supabase.update_chat_thread(
            thread_id,
            {
                "title": draft_data.get("title") or thread.get("title"),
                "status": next_status,
                "metadata": merged_metadata,
            },
        )
        self.supabase.insert_chat_message(
            thread_id,
            "system",
            "Rascunho atualizado antes da confirmacao.",
            {"status": next_status, "kind": "draft_update"},
        )
        return self.get_thread_payload(actor, thread_id)

    def confirm_thread(self, *, actor: dict[str, Any], thread_id: str, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
        thread = self.supabase.get_chat_thread(thread_id, actor["user"]["id"])
        if not thread:
            raise RuntimeError("Thread não encontrada.")

        metadata = thread.get("metadata") or {}
        items = self._resolve_items(overrides.get("items") if overrides else None, metadata.get("pending_items") or [])
        if not items:
            raise RuntimeError("Não há itens pendentes para confirmar nesta conversa.")
        if thread.get("request_id"):
            return self.get_thread_payload(actor, thread_id)

        profile = actor["profile"]
        customer_name = profile.get("company_name") or profile.get("full_name") or actor["user"].get("email") or "Cliente Cotai"
        notes = str((overrides or {}).get("notes") or metadata.get("draft_notes") or metadata.get("last_user_message") or "Pedido criado pelo chatbot interno.")
        request_defaults = self.supabase.infer_request_defaults(
            notes=notes,
            items=items,
            priority=(overrides or {}).get("priority") or metadata.get("priority"),
        )
        duplicate_candidate = self.supabase.find_duplicate_request(company_id=profile["company_id"], items=items)
        request_row = self.supabase.create_internal_request(
            company_id=profile["company_id"],
            user_id=actor["user"]["id"],
            thread_id=thread_id,
            customer_name=customer_name,
            notes=notes,
            items=items,
            delivery_mode=(overrides or {}).get("delivery_mode") or metadata.get("delivery_mode"),
            delivery_location=(overrides or {}).get("delivery_location") or metadata.get("delivery_location"),
            project_name=(overrides or {}).get("project_name") or thread.get("title"),
            priority=request_defaults["priority"],
            sla_due_at=request_defaults["sla_due_at"],
            approval_required=request_defaults["approval_required"],
            approval_status=request_defaults["approval_status"],
            status=request_defaults["status"],
            duplicate_of_request_id=duplicate_candidate.get("request_id") if duplicate_candidate else None,
            duplicate_score=duplicate_candidate.get("score") if duplicate_candidate else None,
        )

        if request_defaults["approval_required"]:
            assistant_text = (
                f"Pedido {request_row['request_code']} registrado com prioridade {request_defaults['priority']}. "
                "Ele entrou em fila de aprovação antes da cotação."
            )
        else:
            assistant_text = f"Pedido {request_row['request_code']} confirmado. Vou iniciar a cotação agora."

        if duplicate_candidate:
            assistant_text += (
                f" Encontrei um pedido parecido ({duplicate_candidate['request_code']}) "
                f"com similaridade de {int(float(duplicate_candidate['score']) * 100)}%."
            )

        self.supabase.insert_chat_message(
            thread_id,
            "assistant",
            assistant_text,
            {
                "status": request_row.get("status"),
                "request_id": request_row["id"],
                "request_code": request_row["request_code"],
                "duplicate_candidate": duplicate_candidate,
                "approval_required": request_defaults["approval_required"],
            },
        )
        self.supabase.update_chat_thread(
            thread_id,
            {
                "request_id": request_row["id"],
                "status": "PROCESSING" if request_row.get("status") != "AWAITING_APPROVAL" else "AWAITING_APPROVAL",
                "metadata": {
                    **metadata,
                    "request_code": request_row["request_code"],
                    "pending_items": items,
                    "delivery_mode": (overrides or {}).get("delivery_mode") or metadata.get("delivery_mode"),
                    "delivery_location": (overrides or {}).get("delivery_location") or metadata.get("delivery_location"),
                    "draft_notes": notes,
                    "priority": request_defaults["priority"],
                    "duplicate_candidate": duplicate_candidate,
                    "approval_required": request_defaults["approval_required"],
                    "timeline": self._append_timeline(
                        metadata,
                        "Pedido confirmado e enviado para cotação." if not request_defaults["approval_required"] else "Pedido confirmado e aguardando aprovação.",
                    ),
                },
            },
        )
        return self.get_thread_payload(actor, thread_id)

    def get_thread_payload(self, actor: dict[str, Any], thread_id: str) -> dict[str, Any]:
        thread = self.supabase.get_chat_thread(thread_id, actor["user"]["id"])
        if not thread:
            raise RuntimeError("Thread não encontrada.")
        messages = self.supabase.list_chat_messages(thread_id)
        metadata = thread.get("metadata") or {}
        request_payload = None
        if thread.get("request_id"):
            request_payload = self.supabase.get_request_status_payload(thread["request_id"])
        return {
            "thread": thread,
            "messages": messages,
            "request": request_payload["request"] if request_payload else None,
            "latest_quote": request_payload["latest_quote"] if request_payload else None,
            "results": request_payload["results"] if request_payload else [],
            "comparison": request_payload["comparison"] if request_payload else {"supplier_count": 0, "best_supplier": None, "suppliers": []},
            "request_items": request_payload["items"] if request_payload else [],
            "detected_items": metadata.get("pending_items") or [],
            "draft": {
                "title": thread.get("title"),
                "items": metadata.get("pending_items") or [],
                "delivery_mode": metadata.get("delivery_mode") or "",
                "delivery_location": metadata.get("delivery_location") or "",
                "notes": metadata.get("draft_notes") or metadata.get("last_user_message") or "",
                "priority": metadata.get("priority") or "MEDIUM",
                "saved_at": metadata.get("draft_saved_at"),
            },
            "timeline": metadata.get("timeline") or [],
            "notifications": self._build_notifications(metadata, request_payload["request"] if request_payload else None),
            "duplicate_candidate": metadata.get("duplicate_candidate"),
        }

    def _build_notifications(self, metadata: dict[str, Any], request_row: dict[str, Any] | None) -> list[dict[str, str]]:
        notifications: list[dict[str, str]] = []
        duplicate_candidate = metadata.get("duplicate_candidate")
        if duplicate_candidate:
            notifications.append(
                {
                    "tone": "warning",
                    "message": f"Pedido parecido detectado: {duplicate_candidate.get('request_code')}.",
                }
            )
        if request_row and request_row.get("approval_required") and str(request_row.get("approval_status") or "").upper() != "APPROVED":
            notifications.append({"tone": "warning", "message": "Pedido aguardando aprovação administrativa."})
        if metadata.get("draft_saved_at"):
            notifications.append({"tone": "muted", "message": f"Rascunho salvo em {metadata.get('draft_saved_at')}"})
        return notifications

    def _load_or_create_thread(self, actor: dict[str, Any], thread_id: str | None, first_message: str) -> dict[str, Any]:
        if thread_id:
            thread = self.supabase.get_chat_thread(thread_id, actor["user"]["id"])
            if not thread:
                raise RuntimeError("Thread não encontrada.")
            return thread

        title = first_message[:72].strip() or "Nova cotação"
        return self.supabase.create_chat_thread(
            user_id=actor["user"]["id"],
            company_id=actor["profile"]["company_id"],
            title=title,
            status="DRAFT",
            metadata={"timeline": [{"at": datetime.now(UTC).isoformat(), "label": "Rascunho iniciado."}]},
        )

    def _merge_items(self, existing: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in [*existing, *incoming]:
            key = str(item.get("normalized_name") or item.get("name") or item.get("raw") or "").strip().casefold()
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(item)
        return merged

    def _resolve_items(self, override_items: list[str | dict[str, Any]] | None, fallback_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not override_items:
            return fallback_items
        normalized = [self.parser._normalize_item(item) for item in override_items]  # noqa: SLF001
        return [item for item in normalized if item]

    def _append_timeline(self, metadata: dict[str, Any], label: str) -> list[dict[str, str]]:
        timeline = list(metadata.get("timeline") or [])
        timeline.append({"at": datetime.now(UTC).isoformat(), "label": label})
        return timeline[-8:]
