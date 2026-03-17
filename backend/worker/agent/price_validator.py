from __future__ import annotations

from datetime import UTC, datetime
from statistics import median
from typing import Any

from .catalog_normalizer import normalize_text


SOURCE_RELIABILITY = {
    "snapshot": 0.96,
    "catalog": 0.82,
    "mercado_livre": 0.58,
    "mercado livre": 0.58,
    "unavailable": 0.25,
}


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _recency_score(captured_at: Any) -> float:
    timestamp = _parse_datetime(captured_at)
    if not timestamp:
        return 0.55
    age_days = max(0.0, (datetime.now(UTC) - timestamp.astimezone(UTC)).total_seconds() / 86400)
    if age_days <= 3:
        return 1.0
    if age_days <= 10:
        return 0.88
    if age_days <= 30:
        return 0.7
    return 0.45


def _match_score(canonical_name: str, offer_title: str) -> float:
    canonical_tokens = {token for token in normalize_text(canonical_name).split() if len(token) > 2}
    offer_tokens = {token for token in normalize_text(offer_title).split() if len(token) > 2}
    if not canonical_tokens or not offer_tokens:
        return 0.45
    overlap = canonical_tokens.intersection(offer_tokens)
    coverage = len(overlap) / max(len(canonical_tokens), 1)
    return round(0.35 + coverage * 0.65, 2)


def validate_offers(
    *,
    item_analysis: dict[str, Any],
    offers: list[dict[str, Any]],
    quantity: float | None,
) -> list[dict[str, Any]]:
    priced_offers = [float(offer["price"]) for offer in offers if isinstance(offer.get("price"), (int, float))]
    median_price = median(priced_offers) if priced_offers else None
    validated: list[dict[str, Any]] = []

    for offer in offers:
        source_name = str(offer.get("source") or "").strip().lower()
        unit_price = float(offer["price"]) if isinstance(offer.get("price"), (int, float)) else None
        source_reliability = SOURCE_RELIABILITY.get(source_name, 0.62)
        name_match = _match_score(item_analysis.get("canonical_name") or item_analysis.get("normalized_name") or "", offer.get("title") or item_analysis.get("original_name") or "")
        recency = _recency_score(offer.get("captured_at"))
        delivery_days = offer.get("delivery_days")
        delivery_score = 0.7 if delivery_days is None else max(0.35, min(1.0, 1.0 - (float(delivery_days) / 30)))

        outlier_penalty = 0.0
        if median_price is not None and unit_price is not None and median_price > 0:
            deviation = abs(unit_price - median_price) / median_price
            outlier_penalty = min(0.45, deviation * 0.5)

        confidence = (
            name_match * 0.38
            + source_reliability * 0.26
            + recency * 0.18
            + delivery_score * 0.08
            + float(item_analysis.get("normalization_confidence") or 0.5) * 0.1
            - outlier_penalty
        )
        confidence = round(max(0.05, min(0.99, confidence)), 2)

        flags: list[str] = []
        if unit_price is None:
            flags.append("preco_indisponivel")
        if outlier_penalty >= 0.2:
            flags.append("preco_fora_da_curva")
        if name_match < 0.62:
            flags.append("match_fraco")
        if source_reliability < 0.65:
            flags.append("fonte_menos_confiavel")
        if recency < 0.6:
            flags.append("dado_antigo")

        estimated_total = (unit_price * quantity) if unit_price is not None and quantity is not None else unit_price
        validated.append(
            {
                **offer,
                "unit_price": unit_price,
                "estimated_total": round(estimated_total, 2) if isinstance(estimated_total, float) else estimated_total,
                "confidence_score": confidence,
                "validation": {
                    "name_match": round(name_match, 2),
                    "source_reliability": round(source_reliability, 2),
                    "recency_score": round(recency, 2),
                    "delivery_score": round(delivery_score, 2),
                    "outlier_penalty": round(outlier_penalty, 2),
                },
                "flags": flags,
            }
        )

    return validated
