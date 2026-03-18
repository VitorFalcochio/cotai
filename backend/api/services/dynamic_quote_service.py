from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

from ...worker.config import Settings
from .dynamic_search_engine import SearchEngine, normalize_text
from .material_extraction_service import MaterialExtractionService
from .parametric_budget_service import ParametricBudgetService
from .search_cache_service import SearchCacheService


@dataclass
class QuoteValidationDecision:
    accepted: bool
    score: float
    reason: str


class DynamicQuoteService:
    """Orchestrates extraction, scraping, normalization and caching."""

    def __init__(
        self,
        settings: Settings,
        extractor: MaterialExtractionService,
        search_engine: SearchEngine,
        cache: SearchCacheService,
        budget_service: ParametricBudgetService | None = None,
    ) -> None:
        self.settings = settings
        self.extractor = extractor
        self.search_engine = search_engine
        self.cache = cache
        self.budget_service = budget_service or ParametricBudgetService()

    async def quote_materials(self, free_text: str) -> dict[str, Any]:
        structured, extraction_provider = self.extractor.extract(free_text)
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

        search_terms = structured.get("search_terms") or [structured.get("raw") or structured.get("item")]
        raw_offers = await self.search_engine.search(search_terms[0])
        validated_offers = self._validate_offers(structured, raw_offers)
        top_offers = sorted(validated_offers, key=lambda item: item["price"])[:3]

        response = {
            "query": structured,
            "search_term": search_terms[0],
            "providers": {
                "extraction": extraction_provider,
                "validation": "fuzzy_matching",
                "search": "playwright_parallel",
            },
            "cache_hit": False,
            "offers": [
                {
                    **offer,
                    "display_price": self._format_brl(float(offer["price"])),
                }
                for offer in top_offers
            ],
            "meta": {
                "total_scraped": len(raw_offers),
                "total_validated": len(validated_offers),
                "future_budgeting_ready": True,
            },
        }
        self.cache.set(cache_key, response, ttl_seconds=self.settings.search_cache_ttl_seconds)
        return response

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

    def _format_brl(self, value: float) -> str:
        raw = f"{value:,.2f}"
        return "R$ " + raw.replace(",", "X").replace(".", ",").replace("X", ".")

