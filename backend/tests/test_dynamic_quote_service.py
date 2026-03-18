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

