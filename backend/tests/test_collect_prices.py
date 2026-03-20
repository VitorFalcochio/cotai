from __future__ import annotations

import unittest

from backend.worker.collect_prices import (
    DEFAULT_RECENT_ITEM_PROVIDERS,
    WatchItem,
    collect_offers_for_watch_item,
    load_watchlist,
)
from backend.worker.config import load_settings


class FakeSupabase:
    def list_recent_request_item_names(self, *, company_id: str | None = None, limit: int = 50) -> list[str]:
        return ["cimento cp-ii 50kg"]


class FakeSearchService:
    def search_mercado_livre(self, query: str, limit: int = 3) -> list[dict[str, object]]:
        return [
            {
                "title": f"{query} promocao",
                "price": 39.9,
                "supplier": "Mercado Livre",
                "link": "https://example.com/ml",
                "source": "mercado_livre",
            }
        ]


class FakeLiveSearchEngine:
    async def search(self, term: str, providers: tuple[str, ...] | None = None) -> list[dict[str, object]]:
        provider = providers[0] if providers else "desconhecido"
        return [
            {
                "supplier": provider.replace("_", " ").title(),
                "product_name": f"{term} loja",
                "price": 42.5,
                "currency": "BRL",
                "offer_url": f"https://example.com/{provider}",
                "source": provider,
            }
        ]


class CollectPricesTests(unittest.TestCase):
    def test_load_watchlist_adds_recent_items_for_all_default_providers(self) -> None:
        settings = load_settings()
        watchlist = load_watchlist(settings, FakeSupabase())

        providers = {item.provider for item in watchlist if item.item_name == "cimento cp-ii 50kg"}
        expected = {provider for provider, _, _ in DEFAULT_RECENT_ITEM_PROVIDERS}
        self.assertTrue(expected.issubset(providers))

    def test_collect_offers_for_marketplace_watch_item(self) -> None:
        rows = collect_offers_for_watch_item(
            FakeSearchService(),
            FakeLiveSearchEngine(),
            WatchItem(
                item_name="cimento cp-ii 50kg",
                query="cimento cp-ii 50kg",
                provider="mercado_livre",
                source_name="mercado_livre",
                max_results=3,
            ),
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["provider"], "mercado_livre")
        self.assertEqual(rows[0]["supplier_name"], "Mercado Livre")

    def test_collect_offers_for_live_provider_watch_item(self) -> None:
        rows = collect_offers_for_watch_item(
            FakeSearchService(),
            FakeLiveSearchEngine(),
            WatchItem(
                item_name="cimento cp-ii 50kg",
                query="cimento cp-ii 50kg",
                provider="telhanorte",
                source_name="Telhanorte",
                max_results=3,
            ),
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["provider"], "telhanorte")
        self.assertEqual(rows[0]["source_name"], "Telhanorte")
        self.assertEqual(rows[0]["metadata"]["source"], "telhanorte")


if __name__ == "__main__":
    unittest.main()
