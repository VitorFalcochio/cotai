from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ...worker.config import Settings
from ...worker.services.search_service import SearchService
from .dynamic_search_engine import SearchEngine, normalize_text
from .material_extraction_service import MaterialExtractionService
from .parametric_budget_service import ParametricBudgetService
from .search_cache_service import SearchCacheService


@dataclass
class QuoteValidationDecision:
    accepted: bool
    score: float
    reason: str


class QuoteOfferPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    supplier: str
    product_name: str
    price: float
    price_cents: int = Field(ge=1)
    display_price: str
    offer_url: str | None = None
    source: str
    currency: str = "BRL"
    captured_at: str | None = None
    delivery_days: int | None = None
    delivery_label: str | None = None
    match_score: float | None = None
    match_reason: str | None = None


class QuoteMetaPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_scraped: int = Field(ge=0)
    total_validated: int = Field(ge=0)
    used_historical_fallback: bool
    item_found: bool
    warnings: list[str]
    future_budgeting_ready: bool


class QuoteResponsePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    query: dict[str, Any]
    search_term: str | None = None
    providers: dict[str, str]
    cache_hit: bool
    offers: list[QuoteOfferPayload]
    message: str
    meta: QuoteMetaPayload


class DynamicQuoteService:
    """Orchestrates extraction, scraping, normalization and fallback."""

    NOT_FOUND_MESSAGE = "Item não localizado na base de dados atual"

    def __init__(
        self,
        settings: Settings,
        extractor: MaterialExtractionService,
        search_engine: SearchEngine,
        cache: SearchCacheService,
        budget_service: ParametricBudgetService | None = None,
        fallback_search: SearchService | None = None,
    ) -> None:
        self.settings = settings
        self.extractor = extractor
        self.search_engine = search_engine
        self.cache = cache
        self.budget_service = budget_service or ParametricBudgetService()
        self.fallback_search = fallback_search or SearchService(settings)

    async def quote_materials(self, free_text: str) -> dict[str, Any]:
        structured, extraction_provider = self.extractor.extract(free_text)
        clarification = self._clarification_response_if_needed(structured, extraction_provider)
        if clarification is not None:
            return clarification

        cache_payload = {
            "item": structured.get("item"),
            "marca": structured.get("marca"),
            "especificacao": structured.get("especificacao"),
            "quantidade": structured.get("quantidade"),
            "unidade": structured.get("unidade"),
        }
        cache_key = self.cache.build_daily_key("quote_search", cache_payload)
        cached = self.cache.get(cache_key)
        if cached is not None:
            return {**cached, "cache_hit": True}

        search_term = str((structured.get("search_terms") or [structured.get("raw") or structured.get("item")])[0]).strip()
        live_result = await self._search_live_offers(search_term)
        validated_offers = self._validate_offers(structured, live_result["offers"])

        fallback_used = False
        warning_messages: list[str] = []
        final_offers = validated_offers

        if live_result["error"]:
            warning_messages.append("Busca em tempo real indisponivel. Usando referencias historicas quando possivel.")

        if not final_offers:
            fallback_used = True
            fallback_offers, fallback_source = self._load_historical_reference_offers(structured)
            final_offers = self._validate_offers(structured, fallback_offers)
            if final_offers:
                warning_messages.append("Resultado baseado em referencia historica ou catalogo local.")
                search_provider_label = f"historical_fallback:{fallback_source}"
            else:
                search_provider_label = "playwright_parallel+historical_fallback"
        else:
            search_provider_label = "playwright_parallel"

        response = self._build_response(
            structured=structured,
            extraction_provider=extraction_provider,
            search_term=search_term,
            raw_offers=live_result["offers"],
            validated_offers=final_offers,
            warning_messages=warning_messages,
            fallback_used=fallback_used,
            search_provider_label=search_provider_label,
        )
        self.cache.set(cache_key, response, ttl_seconds=self.settings.search_cache_ttl_seconds)
        return response

    async def _search_live_offers(self, search_term: str) -> dict[str, Any]:
        try:
            offers = await self.search_engine.search(search_term)
            return {"offers": self._normalize_offer_rows(offers), "error": None}
        except Exception as exc:  # noqa: BLE001
            return {"offers": [], "error": str(exc)}

    def _load_historical_reference_offers(self, structured: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
        try:
            item_name = str(structured.get("item") or structured.get("raw") or "").strip()
            offers = self.fallback_search.search_supplier_snapshots(item_name, limit=5)
            source_parts = ["snapshot"] if offers else []
            catalog_offers = self.fallback_search.search_catalog(item_name, limit=5)
            if catalog_offers:
                offers.extend(catalog_offers)
                source_parts.append("catalog")
            return self._normalize_offer_rows(offers), "+".join(source_parts) or "historical_reference"
        except Exception:
            return [], "unavailable"

    def _clarification_response_if_needed(self, structured: dict[str, Any], extraction_provider: str) -> dict[str, Any] | None:
        if structured.get("status") != "needs_clarification":
            return None
        return self._finalize_response(
            {
                "status": "needs_clarification",
                "query": structured,
                "search_term": None,
                "providers": {
                    "extraction": extraction_provider,
                    "validation": "input_guard",
                    "search": "not_started",
                    "pricing_mode": "not_available",
                },
                "cache_hit": False,
                "offers": [],
                "message": "Preciso confirmar alguns dados antes de iniciar a busca.",
                "meta": {
                    "total_scraped": 0,
                    "total_validated": 0,
                    "used_historical_fallback": False,
                    "item_found": False,
                    "warnings": [issue["message"] for issue in structured.get("validation_issues", [])],
                    "future_budgeting_ready": True,
                },
            }
        )

    def _build_response(
        self,
        *,
        structured: dict[str, Any],
        extraction_provider: str,
        search_term: str,
        raw_offers: list[dict[str, Any]],
        validated_offers: list[dict[str, Any]],
        warning_messages: list[str],
        fallback_used: bool,
        search_provider_label: str,
    ) -> dict[str, Any]:
        sorted_offers = sorted(
            [offer for offer in validated_offers if isinstance(offer.get("price_cents"), int) and offer["price_cents"] > 0],
            key=lambda item: item["price_cents"],
        )[:3]

        if not sorted_offers:
            return self._finalize_response(
                {
                    "status": "not_found",
                    "query": structured,
                    "search_term": search_term,
                    "providers": {
                        "extraction": extraction_provider,
                        "validation": "fuzzy_matching",
                        "search": search_provider_label,
                        "pricing_mode": "not_available",
                    },
                    "cache_hit": False,
                    "offers": [],
                    "message": self.NOT_FOUND_MESSAGE,
                    "meta": {
                        "total_scraped": len(raw_offers),
                        "total_validated": 0,
                        "used_historical_fallback": fallback_used,
                        "item_found": False,
                        "warnings": warning_messages,
                        "future_budgeting_ready": True,
                    },
                }
            )

        return self._finalize_response(
            {
                "status": "ok",
                "query": structured,
                "search_term": search_term,
                "providers": {
                    "extraction": extraction_provider,
                    "validation": "fuzzy_matching",
                    "search": search_provider_label,
                    "pricing_mode": "historical_reference" if fallback_used else "live_market",
                },
                "cache_hit": False,
                "offers": sorted_offers,
                "message": "Cotacao encontrada." if not fallback_used else "Cotacao encontrada com referencia historica.",
                "meta": {
                    "total_scraped": len(raw_offers),
                    "total_validated": len(validated_offers),
                    "used_historical_fallback": fallback_used,
                    "item_found": True,
                    "warnings": warning_messages,
                    "future_budgeting_ready": True,
                },
            }
        )

    def _finalize_response(self, payload: dict[str, Any]) -> dict[str, Any]:
        offers = []
        for offer in payload.get("offers", []):
            normalized = self._normalize_offer_payload(offer)
            if normalized is not None:
                offers.append(normalized)
        payload["offers"] = offers
        return QuoteResponsePayload.model_validate(payload).model_dump()

    def _normalize_offer_rows(self, offers: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized_rows = []
        for offer in offers:
            normalized = self._normalize_offer_payload(offer)
            if normalized is None:
                continue
            normalized_rows.append(normalized)
        return normalized_rows

    def _normalize_offer_payload(self, offer: dict[str, Any]) -> dict[str, Any] | None:
        title = str(offer.get("product_name") or offer.get("title") or "").strip()
        supplier = str(offer.get("supplier") or "Fornecedor").strip()
        price_cents = self._to_cents(offer.get("price"))
        if not title or not supplier or price_cents is None or price_cents <= 0:
            return None
        return {
            "supplier": supplier,
            "product_name": title,
            "price": price_cents / 100,
            "price_cents": price_cents,
            "display_price": self._format_brl_from_cents(price_cents),
            "offer_url": str(offer.get("offer_url") or offer.get("link") or "").strip() or None,
            "source": str(offer.get("source") or supplier).strip(),
            "currency": str(offer.get("currency") or "BRL"),
            "captured_at": offer.get("captured_at"),
            "delivery_days": offer.get("delivery_days"),
            "delivery_label": offer.get("delivery_label"),
            "match_score": round(float(offer.get("match_score") or 0), 4) if offer.get("match_score") is not None else None,
            "match_reason": offer.get("match_reason"),
        }

    def _validate_offers(self, structured: dict[str, Any], offers: list[dict[str, Any]]) -> list[dict[str, Any]]:
        accepted: list[dict[str, Any]] = []
        for offer in offers:
            decision = self._score_offer(structured, offer)
            if not decision.accepted:
                continue
            accepted.append({**offer, "match_score": round(decision.score, 4), "match_reason": decision.reason})
        return accepted

    def _score_offer(self, structured: dict[str, Any], offer: dict[str, Any]) -> QuoteValidationDecision:
        target_tokens = self._tokens_from_structured(structured)
        title = normalize_text(str(offer.get("product_name") or offer.get("title") or ""))
        title_tokens = {token for token in title.split() if len(token) > 1}
        if not title_tokens:
            return QuoteValidationDecision(False, 0.0, "titulo_vazio")

        overlap = target_tokens.intersection(title_tokens)
        ratio = SequenceMatcher(None, " ".join(sorted(target_tokens)), title).ratio()
        score = ratio + (len(overlap) * 0.12)
        brand = normalize_text(str(structured.get("marca") or ""))
        if brand:
            score += 0.2 if brand in title else -0.1
        specification = normalize_text(str(structured.get("especificacao") or ""))
        if specification:
            score += 0.12 if specification in title else 0

        accepted = bool(overlap) and score >= 0.58
        return QuoteValidationDecision(accepted=accepted, score=score, reason=f"overlap={len(overlap)} ratio={ratio:.2f}")

    def _tokens_from_structured(self, structured: dict[str, Any]) -> set[str]:
        parts = [
            structured.get("item"),
            structured.get("marca"),
            structured.get("especificacao"),
            structured.get("raw"),
        ]
        tokens: set[str] = set()
        for part in parts:
            normalized = normalize_text(str(part or ""))
            tokens.update(token for token in normalized.split() if len(token) > 1)
        return tokens

    def _to_cents(self, value: Any) -> int | None:
        if value is None:
            return None
        if isinstance(value, int):
            return value * 100 if value < 10_000 else value
        if isinstance(value, float):
            if value <= 0:
                return None
            return int(round(value * 100))
        text = str(value).strip()
        if not text:
            return None
        cleaned = text.replace("R$", "").replace(" ", "").replace(".", "").replace(",", ".")
        try:
            parsed = float(cleaned)
        except ValueError:
            return None
        if parsed <= 0:
            return None
        return int(round(parsed * 100))

    def _format_brl_from_cents(self, value_cents: int) -> str:
        raw = f"{value_cents / 100:,.2f}"
        return "R$ " + raw.replace(",", "X").replace(".", ",").replace("X", ".")
