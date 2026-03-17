from __future__ import annotations

import re
import unicodedata
from typing import Any


ALIASES = {
    "cimento": ["cimento", "cp2", "cp ii", "cp-ii", "cp iii", "cimento portland"],
    "areia": ["areia", "areia media", "areia fina", "areia grossa"],
    "brita": ["brita", "brita 0", "brita 1", "brita 2"],
    "argamassa": ["argamassa", "argamassa colante", "massa pronta"],
    "vergalhao": ["vergalhao", "ferro", "aco", "barra de ferro", "ca50", "ca-50"],
    "bloco": ["bloco", "bloco estrutural", "bloco de concreto", "tijolo"],
    "tubo": ["tubo", "cano", "pvc", "conexao"],
}


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or "").strip().lower())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", normalized).strip()


def _detect_category(normalized_name: str) -> str:
    for category, aliases in ALIASES.items():
        if any(alias in normalized_name for alias in aliases):
            return category
    return "geral"


def _compact_measurements(normalized_name: str) -> str:
    value = re.sub(r"(\d)\s+(kg|g|mm|cm|m2|m3|m|l)\b", r"\1\2", normalized_name)
    value = re.sub(r"\bcp\s*[- ]?\s*ii\b", "cp2", value)
    value = re.sub(r"\bcp\s*[- ]?\s*iii\b", "cp3", value)
    return re.sub(r"\s+", " ", value).strip()


def _extract_measurements(normalized_name: str) -> list[str]:
    return re.findall(r"\b\d+(?:[.,]\d+)?(?:kg|g|mm|cm|m2|m3|m|l)\b", normalized_name)


def normalize_request_item(item_name: str, unit: str | None = None) -> dict[str, Any]:
    original = str(item_name or "").strip()
    normalized = normalize_text(original)
    compacted = _compact_measurements(normalized)
    category = _detect_category(compacted)
    aliases = [alias for alias in ALIASES.get(category, []) if alias in compacted or alias == category]
    measurements = _extract_measurements(compacted)

    canonical_parts = [category]
    canonical_parts.extend(measurements[:2])
    canonical_name = " ".join(part for part in canonical_parts if part).strip() or compacted or normalized

    search_terms = [original, compacted, canonical_name]
    for alias in aliases[:3]:
        term = " ".join(part for part in [alias, *measurements[:2]] if part).strip()
        if term:
            search_terms.append(term)

    seen: set[str] = set()
    unique_terms: list[str] = []
    for term in search_terms:
        normalized_term = normalize_text(term)
        if not normalized_term or normalized_term in seen:
            continue
        seen.add(normalized_term)
        unique_terms.append(term.strip())

    confidence = 0.55
    if category != "geral":
        confidence += 0.2
    if measurements:
        confidence += 0.15
    if unit:
        confidence += 0.05

    return {
        "original_name": original,
        "normalized_name": compacted or normalized,
        "canonical_name": canonical_name,
        "category": category,
        "aliases": aliases or [category],
        "measurements": measurements,
        "requested_unit": str(unit or "").strip() or None,
        "search_terms": unique_terms[:5],
        "normalization_confidence": round(min(confidence, 0.98), 2),
    }
