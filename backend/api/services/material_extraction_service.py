from __future__ import annotations

import json
import re
from typing import Any

from ...worker.config import Settings
from ...worker.services.ai_service import AIService


class MaterialExtractionService:
    """Extracts structured material entities from free text.

    The output shape is stable and intentionally aligned with the future
    parametric budgeting module, which will need item, brand, specification,
    quantity and unit to estimate compositions.
    """

    def __init__(self, settings: Settings, ai_service: AIService) -> None:
        self.settings = settings
        self.ai_service = ai_service

    def extract(self, text: str) -> tuple[dict[str, Any], str]:
        fallback = self._fallback_extract(text)
        if not self.settings.groq_api_key:
            return fallback, "local"

        prompt = (
            "Voce extrai entidades de um pedido de material para engenharia civil. "
            "Retorne JSON puro com as chaves: item, marca, especificacao, quantidade, unidade e search_terms. "
            "Se alguma informacao nao existir, use null. "
            "Nao invente dados tecnicos. "
            "Exemplo: {\"item\":\"Cimento\",\"marca\":\"Votoran\",\"especificacao\":\"CP II\",\"quantidade\":30,\"unidade\":\"saco\",\"search_terms\":[\"cimento votoran cp ii 50kg\"]}"
        )
        try:
            content = self.ai_service._chat_completion(prompt, {"message": text})  # noqa: SLF001
            match = re.search(r"\{.*\}", content, flags=re.DOTALL)
            payload = json.loads(match.group(0) if match else content)
            return self._normalize_payload(payload, raw=text), "groq"
        except Exception as exc:  # noqa: BLE001
            return fallback, f"local_fallback:{exc}"

    def _normalize_payload(self, payload: dict[str, Any], *, raw: str) -> dict[str, Any]:
        search_terms = payload.get("search_terms") if isinstance(payload.get("search_terms"), list) else []
        quantity = payload.get("quantidade")
        try:
          quantity = float(quantity) if quantity is not None else None
        except (TypeError, ValueError):
          quantity = None
        return {
            "item": str(payload.get("item") or "").strip() or self._infer_item_name(raw),
            "marca": str(payload.get("marca") or "").strip() or None,
            "especificacao": str(payload.get("especificacao") or "").strip() or None,
            "quantidade": quantity,
            "unidade": str(payload.get("unidade") or "").strip() or self._infer_unit(raw),
            "search_terms": [str(term).strip() for term in search_terms if str(term).strip()] or [self._build_search_term(raw, payload)],
            "raw": raw.strip(),
        }

    def _fallback_extract(self, text: str) -> dict[str, Any]:
        quantity = None
        quantity_match = re.search(r"(?P<qty>\d+(?:[.,]\d+)?)", text or "")
        if quantity_match:
            try:
                quantity = float(quantity_match.group("qty").replace(",", "."))
            except ValueError:
                quantity = None
        item = self._infer_item_name(text)
        return {
            "item": item,
            "marca": self._infer_brand(text),
            "especificacao": self._infer_spec(text),
            "quantidade": quantity,
            "unidade": self._infer_unit(text),
            "search_terms": [self._build_search_term(text, {"item": item})],
            "raw": text.strip(),
        }

    def _infer_item_name(self, text: str) -> str:
        clean = re.sub(r"\b\d+(?:[.,]\d+)?\b", "", text or "", flags=re.IGNORECASE)
        clean = re.sub(r"\b(saco|sacos|barra|barras|un|unidade|unidades|m2|m3|m|kg|g|l)\b", "", clean, flags=re.IGNORECASE)
        clean = re.sub(r"\s+", " ", clean).strip(" ,.-")
        return clean or "Material"

    def _infer_unit(self, text: str) -> str | None:
        match = re.search(r"\b(saco|sacos|barra|barras|un|unidade|unidades|m2|m3|m|kg|g|l)\b", text or "", flags=re.IGNORECASE)
        if not match:
            return None
        unit = match.group(1).lower()
        return {"sacos": "saco", "barras": "barra", "unidades": "unidade"}.get(unit, unit)

    def _infer_brand(self, text: str) -> str | None:
        known_brands = ["votoran", "votorantim", "obramax", "amanco", "tigre", "quartzolit", "vedacit", "suvinil"]
        lowered = str(text or "").lower()
        for brand in known_brands:
            if brand in lowered:
                return brand.title()
        return None

    def _infer_spec(self, text: str) -> str | None:
        match = re.search(r"\b(cp\s*[ivx0-9]+)\b", text or "", flags=re.IGNORECASE)
        if match:
            return re.sub(r"\s+", " ", match.group(1).upper()).strip()
        return None

    def _build_search_term(self, raw: str, payload: dict[str, Any]) -> str:
        parts = [
            payload.get("item"),
            payload.get("marca"),
            payload.get("especificacao"),
            re.search(r"\b\d+\s*kg\b", raw or "", flags=re.IGNORECASE).group(0) if re.search(r"\b\d+\s*kg\b", raw or "", flags=re.IGNORECASE) else None,
        ]
        return " ".join(str(part).strip() for part in parts if part).strip() or raw.strip()

