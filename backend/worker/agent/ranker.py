from __future__ import annotations

from statistics import median
from typing import Any


def _price_score(offer: dict[str, Any], best_price: float | None, worst_price: float | None) -> float:
    unit_price = offer.get("unit_price")
    if not isinstance(unit_price, (int, float)):
        return 0.0
    if best_price is None or worst_price is None or best_price == worst_price:
        return 0.85
    span = max(worst_price - best_price, 0.01)
    return max(0.0, min(1.0, 1.0 - ((float(unit_price) - best_price) / span)))


def _delivery_score(offer: dict[str, Any], fastest_days: float | None) -> float:
    delivery_days = offer.get("delivery_days")
    if not isinstance(delivery_days, (int, float)):
        return 0.5
    if fastest_days is None or fastest_days <= 0:
        return 0.8
    return max(0.0, min(1.0, fastest_days / max(float(delivery_days), 1.0)))


def rank_item_offers(item_analysis: dict[str, Any], offers: list[dict[str, Any]]) -> dict[str, Any]:
    if not offers:
        return {
            "ranked_offers": [],
            "best_overall_offer": None,
            "best_price_offer": None,
            "best_delivery_offer": None,
            "market_context": {"median_unit_price": None, "lowest_unit_price": None, "highest_unit_price": None, "price_spread_pct": None},
            "alerts": ["Nenhuma oferta valida encontrada para este item."],
            "confidence": 0.0,
        }

    priced = [float(offer["unit_price"]) for offer in offers if isinstance(offer.get("unit_price"), (int, float))]
    best_price = min(priced) if priced else None
    worst_price = max(priced) if priced else None
    fastest_days = min((float(offer["delivery_days"]) for offer in offers if isinstance(offer.get("delivery_days"), (int, float))), default=None)

    ranked_offers: list[dict[str, Any]] = []
    for offer in offers:
        flag_penalty = min(0.24, len(offer.get("flags") or []) * 0.08)
        overall_score = (
            _price_score(offer, best_price, worst_price) * 0.3
            + _delivery_score(offer, fastest_days) * 0.18
            + float(offer.get("confidence_score") or 0) * 0.46
            + float(item_analysis.get("normalization_confidence") or 0) * 0.06
            - flag_penalty
        )
        ranked_offers.append({**offer, "overall_score": round(overall_score, 3)})

    ranked_offers.sort(key=lambda offer: (-float(offer.get("overall_score") or 0), float(offer.get("unit_price") or 999999), float(offer.get("delivery_days") or 999)))
    best_overall_offer = ranked_offers[0]
    best_price_offer = min(ranked_offers, key=lambda offer: float(offer.get("unit_price") or 999999))
    best_delivery_offer = min(ranked_offers, key=lambda offer: float(offer.get("delivery_days") or 999))

    median_price = median(priced) if priced else None
    spread_pct = None
    if best_price is not None and worst_price is not None and best_price > 0:
        spread_pct = round(((worst_price - best_price) / best_price) * 100, 2)

    alerts: list[str] = []
    if spread_pct is not None and spread_pct >= 18:
        alerts.append(f"Alta dispersao de preco para {item_analysis.get('canonical_name')}: {spread_pct}%.")
    flagged = [offer for offer in ranked_offers if offer.get("flags")]
    if flagged:
        alerts.append(f"{len(flagged)} oferta(s) exigem revisao por confianca ou equivalencia.")
    if float(best_overall_offer.get("confidence_score") or 0) < 0.68:
        alerts.append("Melhor oferta com confianca moderada; validar antes de fechar pedido.")

    return {
        "ranked_offers": ranked_offers,
        "best_overall_offer": best_overall_offer,
        "best_price_offer": best_price_offer,
        "best_delivery_offer": best_delivery_offer,
        "market_context": {
            "median_unit_price": round(median_price, 2) if isinstance(median_price, float) else median_price,
            "lowest_unit_price": round(best_price, 2) if isinstance(best_price, float) else best_price,
            "highest_unit_price": round(worst_price, 2) if isinstance(worst_price, float) else worst_price,
            "price_spread_pct": spread_pct,
        },
        "alerts": alerts,
        "confidence": round(sum(float(offer.get("confidence_score") or 0) for offer in ranked_offers[:3]) / max(min(len(ranked_offers), 3), 1), 2),
    }
