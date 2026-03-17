from __future__ import annotations

from typing import Any

from .catalog_normalizer import normalize_request_item
from .price_validator import validate_offers
from .ranker import rank_item_offers


def _dedupe_offers(offers: list[dict[str, Any]], limit: int = 6) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, Any]] = set()
    for offer in offers:
        key = (
            str(offer.get("title") or "").strip().casefold(),
            str(offer.get("supplier") or "").strip().casefold(),
            offer.get("price"),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(offer)
    deduped.sort(key=lambda item: item["price"] if isinstance(item.get("price"), (int, float)) else float("inf"))
    return deduped[:limit]


class AgentQuoteEngine:
    def __init__(self, search_service: Any) -> None:
        self.search = search_service

    def _search_with_strategy(self, item_analysis: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
        offers: list[dict[str, Any]] = []
        sources: set[str] = set()
        search_terms = item_analysis.get("search_terms") or [item_analysis.get("original_name")]

        if all(hasattr(self.search, name) for name in ("search_supplier_snapshots", "search_catalog", "search_mercado_livre")):
            for term in search_terms[:3]:
                snapshot_rows = self.search.search_supplier_snapshots(term, limit=4)
                if snapshot_rows:
                    offers.extend(snapshot_rows)
                    sources.add("snapshot")

                catalog_rows = self.search.search_catalog(term, limit=4)
                if catalog_rows:
                    offers.extend(catalog_rows)
                    sources.add("catalog")

                try:
                    mercado_rows = self.search.search_mercado_livre(term, limit=4)
                except Exception:
                    mercado_rows = []
                if mercado_rows:
                    offers.extend(mercado_rows)
                    sources.add("mercado_livre")
        else:
            fallback_offers, source = self.search.quote_item(item_analysis.get("original_name") or item_analysis.get("canonical_name") or "")
            offers.extend(fallback_offers)
            if source:
                sources.update(str(source).split("+"))

        return _dedupe_offers(offers), "+".join(sorted(source for source in sources if source)) or "unavailable"

    def build_item_quote(self, item_row: dict[str, Any]) -> dict[str, Any]:
        item_name = str(item_row.get("item_name") or item_row.get("description") or item_row.get("item") or "").strip()
        quantity_raw = item_row.get("qty") or item_row.get("quantity")
        try:
            quantity_value = float(quantity_raw) if quantity_raw is not None else None
        except (TypeError, ValueError):
            quantity_value = None
        unit = str(item_row.get("unit") or "un").strip()

        item_analysis = normalize_request_item(item_name, unit)
        offers, source = self._search_with_strategy(item_analysis)
        validated_offers = validate_offers(item_analysis=item_analysis, offers=offers, quantity=quantity_value)
        ranked = rank_item_offers(item_analysis, validated_offers)

        return {
            "item_name": item_name,
            "canonical_name": item_analysis["canonical_name"],
            "category": item_analysis["category"],
            "quantity": quantity_value,
            "unit": unit,
            "offers": ranked["ranked_offers"],
            "source": source,
            "not_found": len(ranked["ranked_offers"]) == 0,
            "suggestion": item_analysis["search_terms"][0] if item_analysis.get("search_terms") else item_name,
            "estimated_best_total": ranked["best_overall_offer"].get("estimated_total") if ranked["best_overall_offer"] else None,
            "best_overall_offer": ranked["best_overall_offer"],
            "best_price_offer": ranked["best_price_offer"],
            "best_delivery_offer": ranked["best_delivery_offer"],
            "market_context": ranked["market_context"],
            "analysis_alerts": ranked["alerts"],
            "analysis_confidence": ranked["confidence"],
            "item_analysis": item_analysis,
        }
