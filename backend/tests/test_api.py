from __future__ import annotations

import unittest
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from backend.api import deps
from backend.api.main import app
from backend.api.services.chat_service import ChatService
from backend.api.services.quote_service import QuoteService
from backend.api.services.request_parser import RequestParserService
from backend.worker.testing import InMemoryAIService, InMemorySupabase


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.supabase = InMemorySupabase()
        self.ai = InMemoryAIService()

        def override_actor():
            return {
                "user": {"id": "user-1", "email": "user@example.com"},
                "profile": self.supabase.get_profile("user-1"),
                "access_token": "test-token",
            }

        def override_chat_service():
            parser = RequestParserService(self.ai)
            return ChatService(self.supabase, parser)

        def override_quote_service():
            return QuoteService(self.supabase)

        def override_supabase():
            return self.supabase

        app.dependency_overrides[deps.get_current_actor] = override_actor
        app.dependency_overrides[deps.get_chat_service] = override_chat_service
        app.dependency_overrides[deps.get_quote_service] = override_quote_service
        app.dependency_overrides[deps.get_supabase] = override_supabase
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_chat_message_creates_thread_and_awaits_confirmation(self) -> None:
        response = self.client.post(
            "/chat/message",
            json={"message": "Preciso de 50 sacos de cimento e 5 m3 de areia media"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["thread"]["status"], "AWAITING_CONFIRMATION")
        self.assertGreaterEqual(len(payload["messages"]), 2)
        self.assertTrue(payload["detected_items"])

    def test_chat_confirm_creates_request(self) -> None:
        first = self.client.post(
            "/chat/message",
            json={"message": "Preciso de 50 sacos de cimento e 5 m3 de areia media"},
        ).json()
        thread_id = first["thread"]["id"]

        response = self.client.post("/chat/confirm", json={"thread_id": thread_id})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["thread"]["status"], "PROCESSING")
        self.assertIsNotNone(payload["request"])
        self.assertEqual(payload["request"]["status"], "PENDING_QUOTE")

    def test_chat_thread_payload_includes_plan_usage(self) -> None:
        first = self.client.post(
            "/chat/message",
            json={"message": "Preciso de 10 sacos de cimento"},
        ).json()

        response = self.client.get(f"/chat/thread/{first['thread']['id']}")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("plan_usage", payload)
        self.assertEqual(payload["plan_usage"]["plan_key"], "silver")
        self.assertEqual(payload["plan_usage"]["request_limit"], 80)
        self.assertEqual(payload["plan_usage"]["user_limit"], 2)
        self.assertEqual(payload["plan_usage"]["monthly_price"], 89)

    def test_chat_confirm_blocks_when_company_reaches_request_limit(self) -> None:
        company = self.supabase.companies["company-1"]
        company["plan"] = "silver"
        month_start = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        for index in range(80):
            request_id = f"limit-req-{index}"
            request_code = f"CT-LIMIT-{index}"
            self.supabase.requests_by_id[request_id] = {
                "id": request_id,
                "request_code": request_code,
                "company_id": "company-1",
                "requested_by_user_id": "user-1",
                "status": "DONE",
                "created_at": month_start.isoformat(),
            }
            self.supabase.requests[request_code] = self.supabase.requests_by_id[request_id]

        first = self.client.post(
            "/chat/message",
            json={"message": "Preciso de 10 sacos de cimento"},
        ).json()
        response = self.client.post("/chat/confirm", json={"thread_id": first["thread"]["id"]})

        self.assertEqual(response.status_code, 400)
        self.assertIn("atingiu o limite", response.json()["detail"])

    def test_chat_confirm_blocks_when_company_exceeds_user_limit(self) -> None:
        self.supabase.companies["company-1"]["plan"] = "silver"
        self.supabase.profiles["user-2"] = {
            "id": "user-2",
            "email": "second@example.com",
            "full_name": "Second User",
            "company_name": "Cotai Teste",
            "company_id": "company-1",
            "plan": "silver",
            "role": "buyer",
            "status": "active",
        }
        self.supabase.profiles["user-3"] = {
            "id": "user-3",
            "email": "third@example.com",
            "full_name": "Third User",
            "company_name": "Cotai Teste",
            "company_id": "company-1",
            "plan": "silver",
            "role": "buyer",
            "status": "active",
        }

        first = self.client.post(
            "/chat/message",
            json={"message": "Preciso de 10 sacos de cimento"},
        ).json()
        response = self.client.post("/chat/confirm", json={"thread_id": first["thread"]["id"]})

        self.assertEqual(response.status_code, 400)
        self.assertIn("permite ate 2 usuario", response.json()["detail"])

    def test_chat_draft_can_be_updated_before_confirmation(self) -> None:
        first = self.client.post(
            "/chat/message",
            json={"message": "Preciso de 10 sacos de cimento"},
        ).json()
        thread_id = first["thread"]["id"]

        response = self.client.put(
            f"/chat/thread/{thread_id}/draft",
            json={
                "title": "Obra alfa",
                "items": [{"name": "cimento cp2 50kg", "quantity": 12, "unit": "saco"}],
                "delivery_location": "Sao Jose do Rio Preto",
                "notes": "Entregar amanha",
                "priority": "HIGH",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["thread"]["title"], "Obra alfa")
        self.assertEqual(payload["draft"]["priority"], "HIGH")
        self.assertEqual(payload["detected_items"][0]["quantity"], 12.0)

    def test_chat_message_without_detectable_items_returns_draft_feedback(self) -> None:
        class EmptyAIService:
            def extract_items(self, text: str):
                return [], "empty"

            def build_confirmation_message(self, items):
                return "Sem itens", "empty"

        app.dependency_overrides[deps.get_chat_service] = lambda: ChatService(
            self.supabase, RequestParserService(EmptyAIService())
        )
        response = self.client.post(
            "/chat/message",
            json={"message": "Oi, consegue me ajudar?"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["thread"]["status"], "DRAFT")
        self.assertEqual(payload["detected_items"], [])
        self.assertIn("Nao consegui identificar", payload["messages"][-1]["content"])

    def test_confirm_thread_is_idempotent_after_request_creation(self) -> None:
        first = self.client.post(
            "/chat/message",
            json={"message": "Preciso de 10 sacos de cimento"},
        ).json()
        thread_id = first["thread"]["id"]

        confirmed = self.client.post("/chat/confirm", json={"thread_id": thread_id})
        repeated = self.client.post("/chat/confirm", json={"thread_id": thread_id})

        self.assertEqual(confirmed.status_code, 200)
        self.assertEqual(repeated.status_code, 200)
        self.assertEqual(confirmed.json()["request"]["id"], repeated.json()["request"]["id"])

    def test_chat_message_after_done_request_starts_new_confirmation_cycle(self) -> None:
        first = self.client.post(
            "/chat/message",
            json={"message": "Preciso de 10 sacos de cimento"},
        ).json()
        thread_id = first["thread"]["id"]

        confirmed = self.client.post("/chat/confirm", json={"thread_id": thread_id}).json()
        request_id = confirmed["request"]["id"]
        self.supabase.mark_request_done(request_id)

        follow_up = self.client.post(
            "/chat/message",
            json={"thread_id": thread_id, "message": "Agora quero 5 m3 de areia media"},
        )

        self.assertEqual(follow_up.status_code, 200)
        payload = follow_up.json()
        self.assertEqual(payload["thread"]["status"], "AWAITING_CONFIRMATION")
        self.assertIsNone(payload["thread"]["request_id"])
        self.assertIsNone(payload["request"])
        self.assertTrue(payload["detected_items"])

        second_confirm = self.client.post("/chat/confirm", json={"thread_id": thread_id})
        self.assertEqual(second_confirm.status_code, 200)
        self.assertNotEqual(second_confirm.json()["request"]["id"], request_id)

    def test_request_status_endpoint(self) -> None:
        thread = self.supabase.create_chat_thread(user_id="user-1", company_id="company-1", title="Teste")
        request_row = self.supabase.create_internal_request(
            company_id="company-1",
            user_id="user-1",
            thread_id=thread["id"],
            customer_name="Cotai Teste",
            notes="teste",
            items=[{"name": "cimento", "normalized_name": "cimento", "quantity": 2.0, "unit": "saco", "raw": "2 sacos cimento"}],
        )
        response = self.client.get(f"/requests/{request_row['id']}/status")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["request_id"], request_row["id"])
        self.assertEqual(payload["status"], "PENDING_QUOTE")

    def test_ops_overview_endpoint(self) -> None:
        response = self.client.get("/ops/overview")
        self.assertEqual(response.status_code, 200)
        self.assertIn("X-Request-Id", response.headers)
        payload = response.json()
        self.assertEqual(payload["api"]["status"], "online")
        self.assertIn("queue", payload)

    def test_admin_can_reprocess_request_with_reason_and_audit_log(self) -> None:
        thread = self.supabase.create_chat_thread(user_id="user-1", company_id="company-1", title="Teste")
        request_row = self.supabase.create_internal_request(
            company_id="company-1",
            user_id="user-1",
            thread_id=thread["id"],
            customer_name="Cotai Teste",
            notes="teste",
            items=[{"name": "cimento", "normalized_name": "cimento", "quantity": 2.0, "unit": "saco", "raw": "2 sacos cimento"}],
        )
        self.supabase.mark_request_error(request_row["id"], "Falha de integracao")

        response = self.client.post(
            f"/ops/requests/{request_row['id']}/reprocess",
            json={"reason": "Corrigir falha temporaria e reenfileirar"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "NEW")
        self.assertTrue(any(item["event_type"] == "request_reprocess_requested" for item in self.supabase.admin_audit_logs))

    def test_request_can_require_approval_and_be_approved(self) -> None:
        first = self.client.post(
            "/chat/message",
            json={"message": "Preciso urgente de cimento para hoje"},
        ).json()
        thread_id = first["thread"]["id"]

        confirmed = self.client.post(
            "/chat/confirm",
            json={
                "thread_id": thread_id,
                "priority": "URGENT",
                "notes": "Entrega urgente hoje",
            },
        )
        self.assertEqual(confirmed.status_code, 200)
        request_id = confirmed.json()["request"]["id"]
        self.assertEqual(confirmed.json()["request"]["approval_status"], "PENDING")

        approved = self.client.post(
            f"/ops/requests/{request_id}/approve",
            json={"comment": "Liberado pelo admin"},
        )
        self.assertEqual(approved.status_code, 200)
        self.assertEqual(approved.json()["approval_status"], "APPROVED")

    def test_supplier_review_endpoint_creates_review_and_audit_log(self) -> None:
        thread = self.supabase.create_chat_thread(user_id="user-1", company_id="company-1", title="Teste")
        request_row = self.supabase.create_internal_request(
            company_id="company-1",
            user_id="user-1",
            thread_id=thread["id"],
            customer_name="Cotai Teste",
            notes="teste",
            items=[{"name": "cimento", "normalized_name": "cimento", "quantity": 2.0, "unit": "saco", "raw": "2 sacos cimento"}],
        )
        supplier = self.supabase.find_or_create_supplier(company_id="company-1", supplier_name="Fornecedor A", source_name="catalog")

        response = self.client.post(
            f"/requests/{request_row['id']}/supplier-review",
            json={
                "supplier_id": supplier["id"],
                "price_rating": 5,
                "delivery_rating": 4,
                "service_rating": 5,
                "reliability_rating": 4,
                "comment": "Bom fornecedor",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertEqual(len(self.supabase.supplier_reviews), 1)
        self.assertTrue(any(item["event_type"] == "supplier_review_created" for item in self.supabase.admin_audit_logs))


if __name__ == "__main__":
    unittest.main()
