from __future__ import annotations

from typing import Any

from ..services.supabase_service import SupabaseService
from ..utils.hashing import sha256_payload


class DedupeService:
    def __init__(self, supabase: SupabaseService) -> None:
        self.supabase = supabase

    def already_processed(self, message_id: str) -> bool:
        return self.supabase.is_message_processed(message_id)

    def mark_processed(
        self,
        message_id: str,
        chat_id: str,
        request_id: Any | None,
        request_quote_id: Any | None,
        status: str,
        payload: dict[str, Any],
        notes: str = "",
    ) -> None:
        self.supabase.record_processed_message(
            message_id=message_id,
            chat_id=chat_id,
            request_id=request_id,
            request_quote_id=request_quote_id,
            payload_hash=sha256_payload(payload),
            processing_status=status,
            notes=notes,
        )
