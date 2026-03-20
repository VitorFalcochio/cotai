from __future__ import annotations

import unittest

from backend.api.services.dynamic_search_engine import SearchEngine, parse_price
from backend.worker.config import load_settings


class DynamicSearchEngineTests(unittest.TestCase):
    def test_parse_price_handles_brazilian_currency_formats(self) -> None:
        self.assertEqual(parse_price("R$ 1.234,56"), 1234.56)
        self.assertEqual(parse_price("37,90 cada"), 37.90)
        self.assertIsNone(parse_price("sem preco"))

    def test_search_engine_registers_telhanorte_and_leroy_fallback_url(self) -> None:
        engine = SearchEngine(load_settings())

        providers = {provider.name: provider for provider in engine.PROVIDERS}
        self.assertIn("Telhanorte", providers)
        self.assertIn("Leroy Merlin", providers)

        leroy_urls = engine._candidate_search_urls(providers["Leroy Merlin"], "cimento 50kg")
        self.assertEqual(len(leroy_urls), 2)
        self.assertTrue(any("/busca?q=cimento+50kg" in url for url in leroy_urls))
        self.assertTrue(any("/search?term=cimento+50kg" in url for url in leroy_urls))

        telhanorte_urls = engine._candidate_search_urls(providers["Telhanorte"], "argamassa ac3")
        self.assertEqual(telhanorte_urls, ["https://www.telhanorte.com.br/busca?q=argamassa+ac3"])

    def test_resolve_providers_accepts_key_and_display_name(self) -> None:
        engine = SearchEngine(load_settings())

        by_key = engine._resolve_providers(("leroy_merlin",))
        by_name = engine._resolve_providers(("Telhanorte",))

        self.assertEqual([provider.key for provider in by_key], ["leroy_merlin"])
        self.assertEqual([provider.key for provider in by_name], ["telhanorte"])


if __name__ == "__main__":
    unittest.main()
