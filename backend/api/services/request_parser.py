from __future__ import annotations

import re
from typing import Any

from ...shared.request_parser import format_item_label, parse_item_line
from ...worker.services.ai_service import AIService


class RequestParserService:
    def __init__(self, ai_service: AIService) -> None:
        self.ai_service = ai_service

    def parse_user_message(self, message: str) -> dict[str, Any]:
        items, provider = self.ai_service.extract_items(message)
        normalized_items: list[dict[str, Any]] = []
        for item in items:
            normalized = self._normalize_item(item)
            if normalized:
                normalized_items.append(normalized)
        return {
            "items": normalized_items,
            "provider": provider,
            "needs_confirmation": len(normalized_items) > 0,
        }

    def build_confirmation(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        message, provider = self.ai_service.build_confirmation_message(items)
        cautions = self._build_item_cautions(items)
        return {
            "message": "\n".join([message, *cautions]).strip(),
            "provider": provider,
            "preview": [format_item_label(item) for item in items],
        }

    def _normalize_item(self, item: dict[str, Any] | str) -> dict[str, Any] | None:
        if isinstance(item, str):
            parsed = parse_item_line(item)
            if not parsed:
                return None
            item = parsed
        name = str(item.get("normalized_name") or item.get("name") or item.get("raw") or "").strip()
        if not name:
            return None
        quantity = item.get("quantity")
        try:
            quantity = float(quantity) if quantity is not None else None
        except (TypeError, ValueError):
            quantity = None
        return {
            "name": str(item.get("name") or name).strip(),
            "normalized_name": name,
            "quantity": quantity,
            "unit": str(item.get("unit") or "un").strip(),
            "raw": str(item.get("raw") or name).strip(),
        }

    def _build_item_cautions(self, items: list[dict[str, Any]]) -> list[str]:
        cautions: list[str] = []
        raw_text = " ".join(str(item.get("raw") or item.get("name") or "") for item in items).lower()
        has_token = lambda *tokens: any(re.search(rf"\b{re.escape(token)}\b", raw_text) for token in tokens)

        if has_token("cimento", "argamassa", "rejunte") and "kg" not in raw_text:
            cautions.append("Antes de confirmar: se tiver o peso da embalagem, me passe para eu evitar compra errada.")
        if has_token("ferro", "aco", "vergalhao", "barra") and "mm" not in raw_text:
            cautions.append("Atencao na ferragem: confirme a bitola em mm para eu nao misturar material estrutural.")
        if has_token("piso", "porcelanato", "revestimento") and "m2" not in raw_text:
            cautions.append("Se for revestimento, confirme a area em m2 ou a medida da peca para eu montar melhor a compra.")

        return cautions[:2]
