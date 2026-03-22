from __future__ import annotations

import unittest
from dataclasses import replace

from backend.shared.request_parser import extract_inline_items
from backend.worker.config import load_settings
from backend.worker.agent.catalog_normalizer import normalize_request_item
from backend.worker.agent.price_validator import validate_offers
from backend.worker.agent.ranker import rank_item_offers
from backend.worker.main import WorkerApp, parse_request_message
from backend.worker.services.supabase_service import generate_request_code, is_request_code_conflict_error
from backend.worker.services.ai_service import AIService
from backend.worker.testing import InMemoryAIService, InMemorySearchService, InMemorySupabase


class WorkerTests(unittest.TestCase):
    def make_app(
        self,
        *,
        supabase: InMemorySupabase | None = None,
    ) -> WorkerApp:
        settings = load_settings()
        return WorkerApp(
            settings,
            supabase=supabase or InMemorySupabase(),
            search=InMemorySearchService(),
            ai=InMemoryAIService(),
        )

    def test_parse_request_message_extracts_trigger_code_and_items(self) -> None:
        payload = parse_request_message(
            "#COTAI\nPedidoID: CT-1000\nEntrega: Centro\nItens:\n- 20 saco cimento cp2 50kg\n- 3 m3 areia fina"
        )
        self.assertTrue(payload["has_trigger"])
        self.assertEqual(payload["request_code"], "CT-1000")
        self.assertEqual(len(payload["items"]), 2)
        self.assertEqual(payload["items"][0]["name"], "cimento cp2 50kg")

    def test_generate_request_code_is_unique_and_keeps_ct_prefix(self) -> None:
        codes = {generate_request_code() for _ in range(200)}
        self.assertEqual(len(codes), 200)
        self.assertTrue(all(code.startswith("CT-") for code in codes))
        self.assertTrue(all(len(code.split("-")) == 3 for code in codes))

    def test_request_code_conflict_detection_matches_unique_errors(self) -> None:
        self.assertTrue(is_request_code_conflict_error(RuntimeError('duplicate key value violates unique constraint "requests_request_code_key"')))
        self.assertFalse(is_request_code_conflict_error(RuntimeError("network timeout")))

    def test_request_completion_persists_results(self) -> None:
        supabase = InMemorySupabase()
        app = self.make_app(supabase=supabase)
        thread = supabase.create_chat_thread(user_id="user-1", company_id="company-1", title="Nova cotacao")
        request_row = supabase.create_internal_request(
            company_id="company-1",
            user_id="user-1",
            thread_id=thread["id"],
            customer_name="Cotai Teste",
            notes="teste",
            items=[{"name": "cimento", "normalized_name": "cimento", "quantity": 1.0, "unit": "un", "raw": "cimento"}],
        )

        app.process_pending_requests()

        latest_execution = supabase.get_latest_quote_execution(request_row["id"])
        assert latest_execution is not None
        self.assertEqual(latest_execution["status"], "DONE")
        self.assertEqual(supabase.get_request_by_id(request_row["id"])["status"], "DONE")
        self.assertGreaterEqual(len(supabase.quote_results[latest_execution["id"]]), 1)
        self.assertTrue(supabase.suppliers)
        self.assertTrue(supabase.price_history)
        self.assertTrue(supabase.projects)
        self.assertTrue(supabase.project_materials)

    def test_extract_inline_items_from_natural_language_without_groq(self) -> None:
        items = extract_inline_items(
            "Preciso de 50 sacos de cimento CP-II, 20 barras de ferro 10 mm e 5 m3 de areia media para entrega em Rio Preto."
        )
        self.assertEqual(len(items), 3)
        self.assertEqual(items[0]["quantity"], 50.0)
        self.assertIn("cimento", items[0]["name"].lower())

    def test_local_ai_summary_includes_best_offer_and_totals(self) -> None:
        settings = replace(load_settings(), groq_api_key="")
        ai = AIService(settings)
        summary, provider = ai.summarize_quote(
            "CT-1001",
            [
                {
                    "item_name": "cimento cp2 50kg",
                    "canonical_name": "cimento 50kg",
                    "quantity": 20.0,
                    "unit": "saco",
                    "analysis_confidence": 0.84,
                    "market_context": {
                        "lowest_unit_price": 34.9,
                        "highest_unit_price": 37.5,
                        "price_spread_pct": 7.45,
                    },
                    "best_overall_offer": {
                        "price": 34.9,
                        "unit_price": 34.9,
                        "supplier": "Deposito Nova Obra",
                        "source": "catalog",
                        "delivery_label": "2 dia(s)",
                    },
                    "best_price_offer": {
                        "price": 34.9,
                        "unit_price": 34.9,
                        "supplier": "Deposito Nova Obra",
                    },
                    "best_delivery_offer": {
                        "price": 34.9,
                        "unit_price": 34.9,
                        "supplier": "Deposito Nova Obra",
                        "delivery_label": "2 dia(s)",
                    },
                    "analysis_alerts": ["Alta dispersao de preco para cimento 50kg: 7.45%."],
                    "offers": [
                        {
                            "price": 34.9,
                            "supplier": "Deposito Nova Obra",
                            "source": "catalog",
                            "delivery_label": "2 dia(s)",
                            "best_hint": True,
                        },
                        {
                            "price": 37.5,
                            "supplier": "Fornecedor B",
                            "source": "mercado_livre",
                            "delivery_label": "5 dia(s)",
                        },
                    ],
                }
            ],
        )
        self.assertEqual(provider, "template")
        self.assertIn("Cotacao encontrada", summary)
        self.assertIn("Quantidade: 20 saco", summary)
        self.assertIn("Melhores opcoes", summary)
        self.assertIn("Total estimado: R$ 698,00", summary)
        self.assertIn("Media: R$ 36,20 por saco", summary)
        self.assertNotIn("confianca", summary)
        self.assertNotIn("Alta dispersao", summary)

    def test_local_ai_summary_stays_clean_when_only_one_offer_exists(self) -> None:
        settings = replace(load_settings(), groq_api_key="")
        ai = AIService(settings)
        summary, provider = ai.summarize_quote(
            "CT-1002",
            [
                {
                    "item_name": "areia media",
                    "canonical_name": "areia media",
                    "quantity": 3.0,
                    "unit": "m3",
                    "analysis_confidence": 0.54,
                    "market_context": {
                        "median_unit_price": 145.0,
                    },
                    "best_overall_offer": {
                        "price": 145.0,
                        "unit_price": 145.0,
                        "supplier": "Areia Brasil",
                        "estimated_total": 435.0,
                    },
                    "offers": [
                        {
                            "price": 145.0,
                            "unit_price": 145.0,
                            "supplier": "Areia Brasil",
                            "estimated_total": 435.0,
                        }
                    ],
                }
            ],
        )
        self.assertEqual(provider, "template")
        self.assertIn("Areia media", summary)
        self.assertIn("Areia Brasil", summary)
        self.assertIn("Observacao", summary)
        self.assertNotIn("Melhores opcoes", summary)
        self.assertNotIn("analysis_confidence", summary)

    def test_catalog_normalizer_builds_canonical_item_and_terms(self) -> None:
        item = normalize_request_item("cimento cp ii 50kg", "saco")
        self.assertEqual(item["category"], "cimento")
        self.assertEqual(item["canonical_name"], "cimento 50kg")
        self.assertTrue(item["search_terms"])
        self.assertGreaterEqual(item["normalization_confidence"], 0.8)

    def test_price_validator_and_ranker_identify_best_overall_offer(self) -> None:
        item_analysis = normalize_request_item("cimento cp ii 50kg", "saco")
        offers = [
            {
                "title": "Cimento CP2 50kg",
                "supplier": "Fornecedor Seguro",
                "price": 35.0,
                "source": "snapshot",
                "delivery_days": 2,
                "delivery_label": "2 dia(s)",
                "captured_at": "2026-03-16T12:00:00+00:00",
            },
            {
                "title": "Cimento CP2 50kg promocao",
                "supplier": "Marketplace X",
                "price": 31.5,
                "source": "mercado_livre",
                "delivery_days": 7,
                "delivery_label": "7 dia(s)",
                "captured_at": "2026-02-01T12:00:00+00:00",
            },
        ]
        validated = validate_offers(item_analysis=item_analysis, offers=offers, quantity=20.0)
        ranked = rank_item_offers(item_analysis, validated)

        self.assertEqual(ranked["best_price_offer"]["supplier"], "Marketplace X")
        self.assertEqual(ranked["best_overall_offer"]["supplier"], "Fornecedor Seguro")
        self.assertGreater(ranked["confidence"], 0.0)
        self.assertTrue(ranked["alerts"])

    def test_internal_chat_request_writes_assistant_message_on_completion(self) -> None:
        supabase = InMemorySupabase()
        thread = supabase.create_chat_thread(user_id="user-1", company_id="company-1", title="Nova cotacao")
        request_row = supabase.create_internal_request(
            company_id="company-1",
            user_id="user-1",
            thread_id=thread["id"],
            customer_name="Cotai Teste",
            notes="Preciso de cimento",
            items=[{"name": "cimento", "normalized_name": "cimento", "quantity": 20.0, "unit": "saco", "raw": "20 saco cimento"}],
        )
        app = self.make_app(supabase=supabase)

        app.process_pending_requests()

        self.assertEqual(supabase.get_request_by_id(request_row["id"])["status"], "DONE")
        assistant_messages = [msg for msg in supabase.list_chat_messages(thread["id"]) if msg["role"] == "assistant"]
        self.assertTrue(assistant_messages)

    def test_request_without_items_moves_to_error_and_notifies_chat(self) -> None:
        supabase = InMemorySupabase()
        thread = supabase.create_chat_thread(user_id="user-1", company_id="company-1", title="Sem itens")
        request_row = supabase.create_internal_request(
            company_id="company-1",
            user_id="user-1",
            thread_id=thread["id"],
            customer_name="Cotai Teste",
            notes="Pedido sem itens para validar erro",
            items=[],
        )
        supabase.request_items[str(request_row["id"])] = []
        app = self.make_app(supabase=supabase)

        app.process_pending_requests()

        self.assertEqual(supabase.get_request_by_id(request_row["id"])["status"], "ERROR")
        assistant_messages = [msg for msg in supabase.list_chat_messages(thread["id"]) if msg["role"] == "assistant"]
        self.assertTrue(any("Nao foi possivel concluir a cotacao" in msg["content"] for msg in assistant_messages))

    def test_request_awaiting_approval_is_not_processed(self) -> None:
        supabase = InMemorySupabase()
        app = self.make_app(supabase=supabase)
        thread = supabase.create_chat_thread(user_id="user-1", company_id="company-1", title="Aprovacao")
        request_row = supabase.create_internal_request(
            company_id="company-1",
            user_id="user-1",
            thread_id=thread["id"],
            customer_name="Cotai Teste",
            notes="Urgente",
            items=[{"name": "cimento", "normalized_name": "cimento", "quantity": 1.0, "unit": "un", "raw": "cimento"}],
            status="AWAITING_APPROVAL",
            approval_required=True,
            approval_status="PENDING",
        )

        app.process_pending_requests()

        self.assertEqual(supabase.get_request_by_id(request_row["id"])["status"], "AWAITING_APPROVAL")
        self.assertIsNone(supabase.get_latest_quote_execution(request_row["id"]))


if __name__ == "__main__":
    unittest.main()
