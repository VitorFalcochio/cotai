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
        if not self.settings.groq_api_key and not self.settings.gemini_api_key:
            return self._finalize_payload(fallback, raw=text), "local"
        try:
            payload, provider = self.ai_service.extract_material_entities(text)
            return self._finalize_payload(self._normalize_payload(payload, raw=text), raw=text), provider
        except Exception as exc:  # noqa: BLE001
            return self._finalize_payload(fallback, raw=text), f"local_fallback:{exc}"

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

    def _finalize_payload(self, payload: dict[str, Any], *, raw: str) -> dict[str, Any]:
        issues = self._validation_issues(payload, raw=raw)
        missing_fields = [issue["field"] for issue in issues if issue["code"] == "missing"]
        return {
            **payload,
            "status": "needs_clarification" if issues else "ready",
            "validation_issues": issues,
            "missing_fields": missing_fields,
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

    def _validation_issues(self, payload: dict[str, Any], *, raw: str) -> list[dict[str, str]]:
        issues: list[dict[str, str]] = []
        item = str(payload.get("item") or "").strip()
        quantity = payload.get("quantidade")
        search_terms = payload.get("search_terms") or []
        cleaned_raw = str(raw or "").strip()

        if len(cleaned_raw) < 3:
            issues.append({"field": "query", "code": "missing", "message": "Descreva melhor o item para cotacao."})
        if not item or item.lower() == "material" or len(item.split()) < 1:
            issues.append({"field": "item", "code": "missing", "message": "Nao consegui identificar qual material deve ser buscado."})
        if isinstance(quantity, (int, float)) and quantity <= 0:
            issues.append({"field": "quantidade", "code": "invalid", "message": "A quantidade informada precisa ser maior que zero."})
        if not search_terms or not any(str(term).strip() for term in search_terms):
            issues.append({"field": "search_terms", "code": "missing", "message": "Nao consegui montar um termo de busca confiavel."})
        return issues
