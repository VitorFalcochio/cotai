from __future__ import annotations

import unittest

from backend.worker.config import load_settings
from backend.worker.main import WorkerApp, parse_request_message
from backend.worker.testing import InMemoryAIService, InMemorySearchService, InMemorySupabase, InMemoryWhatsAppService


class WorkerTests(unittest.TestCase):
    def make_app(
        self,
        *,
        supabase: InMemorySupabase | None = None,
        whatsapp: InMemoryWhatsAppService | None = None,
    ) -> WorkerApp:
        settings = load_settings()
        return WorkerApp(
            settings,
            supabase=supabase or InMemorySupabase(),
            whatsapp=whatsapp or InMemoryWhatsAppService(),
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

    def test_replayed_request_code_does_not_duplicate_items(self) -> None:
        supabase = InMemorySupabase()
        app = self.make_app(supabase=supabase)
        message_a = {"id": "msg-1", "timestamp": 1, "body": "#COTAI\nPedidoID: CT-2000\nItens:\n- cimento\n- areia", "fromMe": False}
        message_b = {"id": "msg-2", "timestamp": 2, "body": "#COTAI\nPedidoID: CT-2000\nItens:\n- cimento\n- areia", "fromMe": False}

        app.handle_incoming_message("5511999999999@c.us", message_a)
        app.handle_incoming_message("5511999999999@c.us", message_b)

        request_row = supabase.get_request_by_code("CT-2000")
        assert request_row is not None
        items = supabase.get_request_items(request_row["id"])
        self.assertEqual([item["item_name"] for item in items], ["cimento", "areia"])

    def test_request_completion_survives_send_failure(self) -> None:
        supabase = InMemorySupabase()
        whatsapp = InMemoryWhatsAppService(fail_sends=True)
        app = self.make_app(supabase=supabase, whatsapp=whatsapp)
        request_row = supabase.create_request_from_message(
            request_code="CT-3000",
            company_id=supabase.resolve_worker_company_id(),
            customer_name="5511999999999@c.us",
            delivery_mode=None,
            delivery_location=None,
            notes="teste",
            origin_chat_id="5511999999999@c.us",
        )
        supabase.insert_request_items(request_row["id"], ["cimento"])

        app.process_pending_requests()

        latest_execution = supabase.get_latest_quote_execution(request_row["id"])
        assert latest_execution is not None
        self.assertEqual(latest_execution["status"], "DONE")
        self.assertEqual(supabase.get_request_by_code("CT-3000")["status"], "DONE")
        self.assertEqual(len(supabase.quote_results[latest_execution["id"]]), 1)


if __name__ == "__main__":
    unittest.main()
