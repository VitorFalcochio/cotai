from __future__ import annotations

import unittest
from dataclasses import replace

from backend.shared.request_parser import extract_inline_items
from backend.worker.config import load_settings
from backend.worker.main import WorkerApp, parse_request_message
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
                    "quantity": 20.0,
                    "unit": "saco",
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
        self.assertEqual(provider, "local")
        self.assertIn("Melhor oferta", summary)
        self.assertIn("Total estimado", summary)

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
