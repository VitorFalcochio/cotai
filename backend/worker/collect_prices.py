from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any

from ..api.services.dynamic_search_engine import SearchEngine
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


DEFAULT_RECENT_ITEM_PROVIDERS: tuple[tuple[str, str, int], ...] = (
    ("mercado_livre", "mercado_livre", 5),
    ("leroy_merlin", "Leroy Merlin", 3),
    ("telhanorte", "Telhanorte", 3),
    ("obramax", "Obramax", 3),
)


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
        for provider, source_name, max_results in DEFAULT_RECENT_ITEM_PROVIDERS:
            key = (normalize_text(item_name), provider, settings.worker_company_id or None)
            if key in seen:
                continue
            seen.add(key)
            watch_items.append(
                WatchItem(
                    item_name=item_name,
                    query=item_name,
                    provider=provider,
                    source_name=source_name,
                    company_id=settings.worker_company_id or None,
                    max_results=max_results,
                )
            )

    return watch_items


def _to_snapshot_row(item: WatchItem, offer: dict[str, Any]) -> dict[str, Any]:
    title = str(offer.get("title") or offer.get("product_name") or item.item_name).strip()
    supplier_name = str(offer.get("supplier") or item.source_name or "Fornecedor").strip()
    link = offer.get("link") or offer.get("offer_url")
    source = str(offer.get("source") or item.source_name or item.provider).strip()

    return {
        "company_id": item.company_id,
        "item_name": item.item_name,
        "normalized_item_name": normalize_text(item.item_name),
        "query": item.query,
        "provider": item.provider,
        "source_name": item.source_name,
        "supplier_name": supplier_name,
        "title": title,
        "price": offer.get("price"),
        "unit_price": offer.get("price"),
        "currency": str(offer.get("currency") or "BRL"),
        "delivery_days": offer.get("delivery_days"),
        "delivery_label": offer.get("delivery_label") or None,
        "result_url": link,
        "metadata": {
            "source": source,
            "raw_title": title,
            "captured_via": "collector",
        },
    }


async def _collect_live_provider_offers(live_search: SearchEngine, item: WatchItem) -> list[dict[str, Any]]:
    offers = await live_search.search(item.query, providers=(item.provider,))
    snapshots = [_to_snapshot_row(item, offer) for offer in offers[: item.max_results]]
    return [row for row in snapshots if row.get("price") is not None]


def collect_offers_for_watch_item(search: SearchService, live_search: SearchEngine, item: WatchItem) -> list[dict[str, Any]]:
    if item.provider == "mercado_livre":
        offers = search.search_mercado_livre(item.query, limit=item.max_results)
        return [_to_snapshot_row(item, offer) for offer in offers if offer.get("price") is not None]

    if item.provider in {"leroy_merlin", "telhanorte", "obramax"}:
        return asyncio.run(_collect_live_provider_offers(live_search, item))

    return []


def main() -> int:
    settings = load_settings()
    validate_settings(settings)
    supabase = SupabaseService(settings)
    search = SearchService(settings)
    live_search = SearchEngine(settings)
    try:
        watchlist = load_watchlist(settings, supabase)
        all_rows: list[dict[str, Any]] = []
        for item in watchlist:
            try:
                all_rows.extend(collect_offers_for_watch_item(search, live_search, item))
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
