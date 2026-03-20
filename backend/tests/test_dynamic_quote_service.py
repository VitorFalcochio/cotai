from __future__ import annotations

import asyncio
import unittest

from backend.api.services.dynamic_quote_service import DynamicQuoteService
from backend.api.services.search_cache_service import SearchCacheService
from backend.worker.config import load_settings


class FakeExtractor:
    def extract(self, text: str):
        return (
            {
                "item": "Cimento",
                "marca": "Votoran",
                "especificacao": "CP II",
                "quantidade": 30,
                "unidade": "saco",
                "search_terms": ["cimento votoran cp ii 50kg"],
                "raw": text,
            },
            "fake",
        )


class FakeSearchEngine:
    def __init__(self) -> None:
        self.calls = 0

    async def search(self, term: str):
        self.calls += 1
        return [
            {
                "supplier": "Leroy Merlin",
                "product_name": "Cimento Votoran CP II 50kg",
                "price": 39.9,
                "offer_url": "https://example.com/a",
                "source": "Leroy Merlin",
            },
            {
                "supplier": "Obramax",
                "product_name": "Cimento Votoran CP II 50kg",
                "price": 37.5,
                "offer_url": "https://example.com/b",
                "source": "Obramax",
            },
            {
                "supplier": "Leroy Merlin",
                "product_name": "Tinta acrilica branca 18L",
                "price": 199.0,
                "offer_url": "https://example.com/c",
                "source": "Leroy Merlin",
            },
        ]


class FailingSearchEngine:
    async def search(self, term: str):
        raise RuntimeError("scraping offline")


class FakeFallbackSearchService:
    def __init__(self, offers: list[dict[str, object]] | None = None) -> None:
        self.offers = offers or []

    def search_supplier_snapshots(self, item_name: str, limit: int = 5):
        return self.offers[:limit]

    def search_catalog(self, item_name: str, limit: int = 5):
        return self.offers[:limit]


class AmbiguousExtractor:
    def extract(self, text: str):
        return (
            {
                "item": "",
                "marca": None,
                "especificacao": None,
                "quantidade": None,
                "unidade": None,
                "search_terms": [],
                "raw": text,
                "status": "needs_clarification",
                "validation_issues": [{"field": "item", "code": "missing", "message": "Nao consegui identificar qual material deve ser buscado."}],
                "missing_fields": ["item"],
            },
            "fake",
        )


class DynamicQuoteServiceTests(unittest.TestCase):
    def test_quote_service_filters_invalid_offer_and_uses_daily_cache(self) -> None:
        settings = load_settings()
        cache = SearchCacheService()
        search_engine = FakeSearchEngine()
        service = DynamicQuoteService(
            settings=settings,
            extractor=FakeExtractor(),
            search_engine=search_engine,
            cache=cache,
        )

        first = asyncio.run(service.quote_materials("30 sacos de cimento Votoran"))
        second = asyncio.run(service.quote_materials("30 sacos de cimento Votoran"))

        self.assertFalse(first["cache_hit"])
        self.assertTrue(second["cache_hit"])
        self.assertEqual(search_engine.calls, 1)
        self.assertEqual(len(first["offers"]), 2)
        self.assertEqual(first["offers"][0]["supplier"], "Obramax")
        self.assertTrue(all("cimento" in offer["product_name"].lower() for offer in first["offers"]))
        self.assertEqual(first["offers"][0]["price_cents"], 3750)

    def test_quote_service_uses_historical_fallback_when_live_search_fails(self) -> None:
        settings = load_settings()
        cache = SearchCacheService()
        service = DynamicQuoteService(
            settings=settings,
            extractor=FakeExtractor(),
            search_engine=FailingSearchEngine(),
            cache=cache,
            fallback_search=FakeFallbackSearchService(
                offers=[
                    {
                        "title": "Cimento Votoran CP II 50kg",
                        "price": 36.4,
                        "supplier": "Deposito Historico",
                        "link": "https://example.com/historico",
                        "source": "catalog",
                        "captured_at": "2026-03-20T10:00:00+00:00",
                    }
                ]
            ),
        )

        result = asyncio.run(service.quote_materials("30 sacos de cimento Votoran"))

        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["meta"]["used_historical_fallback"])
        self.assertEqual(result["providers"]["pricing_mode"], "historical_reference")
        self.assertEqual(result["offers"][0]["price_cents"], 3640)
        self.assertTrue(result["meta"]["warnings"])

    def test_quote_service_returns_not_found_without_inventing_price(self) -> None:
        settings = load_settings()
        cache = SearchCacheService()
        service = DynamicQuoteService(
            settings=settings,
            extractor=FakeExtractor(),
            search_engine=FailingSearchEngine(),
            cache=cache,
            fallback_search=FakeFallbackSearchService(),
        )

        result = asyncio.run(service.quote_materials("30 sacos de cimento Votoran"))

        self.assertEqual(result["status"], "not_found")
        self.assertEqual(result["message"], "Item não localizado na base de dados atual")
        self.assertEqual(result["offers"], [])

    def test_quote_service_requests_clarification_for_ambiguous_input(self) -> None:
        settings = load_settings()
        cache = SearchCacheService()
        service = DynamicQuoteService(
            settings=settings,
            extractor=AmbiguousExtractor(),
            search_engine=FakeSearchEngine(),
            cache=cache,
        )

        result = asyncio.run(service.quote_materials("material"))

        self.assertEqual(result["status"], "needs_clarification")
        self.assertEqual(result["offers"], [])
        self.assertIn("item", result["query"]["missing_fields"])
