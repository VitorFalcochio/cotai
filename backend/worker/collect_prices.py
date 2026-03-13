from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .config import load_settings, validate_settings
from .services.search_service import SearchService, normalize_text
from .services.supabase_service import SupabaseService


@dataclass
class WatchItem:
    item_name: str
    query: str
    provider: str
    source_name: str
    company_id: str | None = None
    max_results: int = 5


def load_watchlist(settings, supabase: SupabaseService) -> list[WatchItem]:
    watch_items: list[WatchItem] = []
    seen: set[tuple[str, str, str | None]] = set()

    if settings.price_sources_json.exists():
        with settings.price_sources_json.open("r", encoding="utf-8-sig") as handle:
            payload = json.load(handle)
        if isinstance(payload, list):
            for row in payload:
                if not isinstance(row, dict) or not row.get("enabled", True):
                    continue
                item_name = str(row.get("item_name") or row.get("query") or "").strip()
                query = str(row.get("query") or item_name).strip()
                provider = str(row.get("provider") or "mercado_livre").strip()
                source_name = str(row.get("source_name") or provider).strip()
                company_id = row.get("company_id")
                key = (normalize_text(item_name), provider, company_id)
                if not item_name or key in seen:
                    continue
                seen.add(key)
                watch_items.append(
                    WatchItem(
                        item_name=item_name,
                        query=query,
                        provider=provider,
                        source_name=source_name,
                        company_id=company_id,
                        max_results=int(row.get("max_results") or 5),
                    )
                )

    try:
        recent_items = supabase.list_recent_request_item_names(company_id=settings.worker_company_id or None, limit=50)
    except Exception:
        recent_items = []

    for item_name in recent_items:
        key = (normalize_text(item_name), "mercado_livre", settings.worker_company_id or None)
        if key in seen:
            continue
        seen.add(key)
        watch_items.append(
            WatchItem(
                item_name=item_name,
                query=item_name,
                provider="mercado_livre",
                source_name="mercado_livre",
                company_id=settings.worker_company_id or None,
                max_results=5,
            )
        )

    return watch_items


def collect_offers_for_watch_item(search: SearchService, item: WatchItem) -> list[dict[str, Any]]:
    if item.provider != "mercado_livre":
        return []

    offers = search.search_mercado_livre(item.query, limit=item.max_results)
    snapshots: list[dict[str, Any]] = []
    for offer in offers:
        snapshots.append(
            {
                "company_id": item.company_id,
                "item_name": item.item_name,
                "normalized_item_name": normalize_text(item.item_name),
                "query": item.query,
                "provider": item.provider,
                "source_name": item.source_name,
                "supplier_name": str(offer.get("supplier") or item.source_name or "Fornecedor").strip(),
                "title": str(offer.get("title") or item.item_name).strip(),
                "price": offer.get("price"),
                "unit_price": offer.get("price"),
                "currency": "BRL",
                "delivery_days": offer.get("delivery_days"),
                "delivery_label": offer.get("delivery_label") or None,
                "result_url": offer.get("link"),
                "metadata": {
                    "source": offer.get("source"),
                    "raw_title": offer.get("title"),
                    "captured_via": "collector",
                },
            }
        )
    return snapshots


def main() -> int:
    settings = load_settings()
    validate_settings(settings)
    supabase = SupabaseService(settings)
    search = SearchService(settings)
    try:
        watchlist = load_watchlist(settings, supabase)
        all_rows: list[dict[str, Any]] = []
        for item in watchlist:
            try:
                all_rows.extend(collect_offers_for_watch_item(search, item))
            except Exception:
                continue
        supabase.insert_supplier_price_snapshots(all_rows)
        print(
            json.dumps(
                {
                    "watch_items": len(watchlist),
                    "snapshots_inserted": len(all_rows),
                    "table": "supplier_price_snapshots",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    finally:
        search.close()
        supabase.close()


if __name__ == "__main__":
    raise SystemExit(main())
