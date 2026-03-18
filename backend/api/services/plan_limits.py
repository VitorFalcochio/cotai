from __future__ import annotations

from typing import Any


PLAN_LIMITS: dict[str, dict[str, Any]] = {
    "silver": {
        "label": "Prata",
        "tagline": "Entrada enxuta para operacoes pequenas",
        "monthly_price": 89,
        "request_limit": 80,
        "user_limit": 2,
        "supplier_limit": 20,
        "history_days": 90,
        "csv_imports_per_month": 1,
        "support_level": "Padrao",
        "recommended": False,
    },
    "gold": {
        "label": "Ouro",
        "tagline": "Plano principal para equipes de compras em crescimento",
        "monthly_price": 189,
        "request_limit": 300,
        "user_limit": 5,
        "supplier_limit": 80,
        "history_days": 365,
        "csv_imports_per_month": 12,
        "support_level": "Prioritario",
        "recommended": True,
    },
    "diamond": {
        "label": "Diamante",
        "tagline": "Operacao intensiva com governanca e escala",
        "monthly_price": 499,
        "request_limit": 2000,
        "user_limit": 15,
        "supplier_limit": 400,
        "history_days": None,
        "csv_imports_per_month": None,
        "support_level": "Premium",
        "recommended": False,
    },
}

PLAN_ALIASES = {
    "silver": "silver",
    "prata": "silver",
    "gold": "gold",
    "ouro": "gold",
    "diamond": "diamond",
    "diamante": "diamond",
}


def normalize_plan_key(value: str | None, fallback: str = "silver") -> str:
    normalized = str(value or "").strip().casefold()
    return PLAN_ALIASES.get(normalized, fallback)


def get_plan_definition(value: str | None) -> dict[str, Any]:
    return PLAN_LIMITS[normalize_plan_key(value)]
