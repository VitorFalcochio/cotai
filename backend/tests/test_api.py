from __future__ import annotations

import unittest
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from backend.api import deps
from backend.api.main import app
from backend.api.services.chat_service import ChatService
from backend.api.services.construction_mode_service import ConstructionModeService
from backend.api.services.dynamic_quote_service import DynamicQuoteService
from backend.api.services.parametric_budget_service import ParametricBudgetService
from backend.api.services.project_service import ProjectService
from backend.api.services.quote_service import QuoteService
from backend.api.services.request_parser import RequestParserService
from backend.worker.config import load_settings
from backend.worker.testing import InMemoryAIService, InMemorySupabase
from backend.worker.utils.telemetry import telemetry


class FakeConstructionSearchService:
    def search_supplier_snapshots(self, item_name: str, limit: int = 5):
        rows = {
            "Concreto usinado fck 25": [{"price": 490.0, "source": "snapshot", "captured_at": "2026-03-20T10:00:00+00:00"}],
            "Aco CA-50": [{"price": 8.0, "source": "snapshot", "captured_at": "2026-03-20T10:00:00+00:00"}],
            "Bloco estrutural 14x19x39": [{"price": 6.1, "source": "snapshot", "captured_at": "2026-03-20T10:00:00+00:00"}],
        }
        return rows.get(item_name, [])[:limit]

    def search_catalog(self, item_name: str, limit: int = 5):
        rows = {
            "Argamassa de assentamento": [{"price": 420.0, "source": "catalog"}],
            "Cimento CP II 50kg": [{"price": 41.0, "source": "catalog"}],
            "Brita 1": [{"price": 180.0, "source": "catalog"}],
            "Areia media": [{"price": 165.0, "source": "catalog"}],
        }
        return rows.get(item_name, [])[:limit]


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.supabase = InMemorySupabase()
        self.ai = InMemoryAIService()
        telemetry.reset()

        def override_actor():
            return {
                "user": {"id": "user-1", "email": "user@example.com"},
                "profile": self.supabase.get_profile("user-1"),
                "access_token": "test-token",
            }

        def override_chat_service():
            parser = RequestParserService(self.ai)
            return ChatService(
                self.supabase,
                parser,
                ConstructionModeService(load_settings(), FakeConstructionSearchService()),
                project_service=ProjectService(self.supabase),
            )

        def override_quote_service():
            return QuoteService(self.supabase)

        class FakeDynamicQuoteService:
            def __init__(self) -> None:
                self.budget_service = ParametricBudgetService()

            async def quote_materials(self, free_text: str) -> dict[str, object]:
                return {
                    "query": {
                        "item": "Cimento",
                        "marca": "Votoran",
                        "especificacao": "CP II",
                        "quantidade": 30,
                        "unidade": "saco",
                        "raw": free_text,
                    },
                    "search_term": "cimento votoran cp ii 50kg",
                    "providers": {
                        "extraction": "fake",
                        "validation": "fuzzy_matching",
                        "search": "playwright_parallel",
                    },
                    "cache_hit": False,
                    "offers": [
                        {
                            "supplier": "Obramax",
                            "product_name": "Cimento Votoran CP II 50kg",
                            "price": 37.5,
                            "display_price": "R$ 37,50",
                            "offer_url": "https://example.com/oferta",
                            "source": "Obramax",
                        }
                    ],
                    "meta": {
                        "total_scraped": 4,
                        "total_validated": 1,
                        "future_budgeting_ready": True,
                    },
                }

        def override_supabase():
            return self.supabase

        app.dependency_overrides[deps.get_current_actor] = override_actor
        app.dependency_overrides[deps.get_chat_service] = override_chat_service
        app.dependency_overrides[deps.get_quote_service] = override_quote_service
        app.dependency_overrides[deps.get_dynamic_quote_service] = lambda: FakeDynamicQuoteService()
        app.dependency_overrides[deps.get_construction_mode_service] = lambda: ConstructionModeService(load_settings(), FakeConstructionSearchService())
        app.dependency_overrides[deps.get_supabase] = override_supabase
        self.client = TestClient(app)

    def tearDown(self) -> None:
        telemetry.reset()
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
        self.assertFalse(payload["plan_usage"]["billing_enabled"])
        self.assertFalse(payload["plan_usage"]["plan_limits_enforced"])
        self.assertEqual(payload["plan_usage"]["request_limit"], 80)
        self.assertEqual(payload["plan_usage"]["user_limit"], 2)
        self.assertEqual(payload["plan_usage"]["monthly_price"], 89)

    def test_chat_confirm_blocks_when_company_reaches_request_limit(self) -> None:
        self.supabase.enforce_plan_limits = True
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
        self.supabase.enforce_plan_limits = True
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
            self.supabase,
            RequestParserService(EmptyAIService()),
            ConstructionModeService(load_settings(), FakeConstructionSearchService()),
        )
        response = self.client.post(
            "/chat/message",
            json={"message": "Oi, consegue me ajudar?"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["thread"]["status"], "DRAFT")
        self.assertEqual(payload["detected_items"], [])
        self.assertIn("Posso te ajudar a planejar a obra", payload["messages"][-1]["content"])

    def test_chat_message_for_construction_scope_returns_guided_construction_answer(self) -> None:
        class EmptyAIService:
            def extract_items(self, text: str):
                return [], "empty"

            def build_confirmation_message(self, items):
                return "Sem itens", "empty"

        app.dependency_overrides[deps.get_chat_service] = lambda: ChatService(
            self.supabase,
            RequestParserService(EmptyAIService()),
            ConstructionModeService(load_settings(), FakeConstructionSearchService()),
        )
        response = self.client.post(
            "/chat/message",
            json={"message": "Como devo comecar uma casa de 120 m2?"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["thread"]["status"], "DRAFT")
        self.assertEqual(payload["detected_items"], [])
        self.assertIn("IA de construcao civil", payload["messages"][-1]["content"])
        self.assertIn("Montei a leitura inicial para casa de 120.0 m2.", payload["messages"][-1]["content"])
        self.assertIn("construction_preview", payload["messages"][-1]["metadata"])
        self.assertIn("brain", payload["messages"][-1]["metadata"]["construction_preview"])

    def test_chat_message_keeps_construction_context_for_refinement_follow_up(self) -> None:
        class EmptyAIService:
            def extract_items(self, text: str):
                return [], "empty"

            def build_confirmation_message(self, items):
                return "Sem itens", "empty"

        app.dependency_overrides[deps.get_chat_service] = lambda: ChatService(
            self.supabase,
            RequestParserService(EmptyAIService()),
            ConstructionModeService(load_settings(), FakeConstructionSearchService()),
        )
        first = self.client.post(
            "/chat/message",
            json={"message": "Como devo comecar uma casa de 120 m2?"},
        ).json()

        follow_up = self.client.post(
            "/chat/message",
            json={"thread_id": first["thread"]["id"], "message": "Em Campinas com radier"},
        )

        self.assertEqual(follow_up.status_code, 200)
        payload = follow_up.json()
        self.assertIn("Campinas", payload["messages"][-1]["content"])
        self.assertIn("radier", payload["messages"][-1]["content"].lower())
        self.assertTrue(payload["conversation_memory"])
        self.assertTrue(payload["notifications"])

    def test_chat_message_can_transform_construction_context_into_procurement_draft(self) -> None:
        class EmptyAIService:
            def extract_items(self, text: str):
                return [], "empty"

            def build_confirmation_message(self, items):
                return "Sem itens", "empty"

        app.dependency_overrides[deps.get_chat_service] = lambda: ChatService(
            self.supabase,
            RequestParserService(EmptyAIService()),
            ConstructionModeService(load_settings(), FakeConstructionSearchService()),
        )
        first = self.client.post(
            "/chat/message",
            json={"message": "Como devo comecar uma casa de 120 m2 em Campinas com radier?"},
        ).json()

        second = self.client.post(
            "/chat/message",
            json={"thread_id": first["thread"]["id"], "message": "Monte a lista de compra da fundacao"},
        )

        self.assertEqual(second.status_code, 200)
        payload = second.json()
        self.assertEqual(payload["thread"]["status"], "AWAITING_CONFIRMATION")
        self.assertTrue(payload["detected_items"])
        self.assertIn("lista inicial de compra", payload["messages"][-1]["content"].lower())
        self.assertIn("fundacao", payload["messages"][-1]["content"].lower())
        self.assertIn("construction_preview", payload["messages"][-1]["metadata"])
        self.assertIn("brain", payload["messages"][-1]["metadata"]["construction_preview"])

    def test_chat_message_surfaces_conflict_when_core_context_changes(self) -> None:
        class EmptyAIService:
            def extract_items(self, text: str):
                return [], "empty"

            def build_confirmation_message(self, items):
                return "Sem itens", "empty"

        app.dependency_overrides[deps.get_chat_service] = lambda: ChatService(
            self.supabase,
            RequestParserService(EmptyAIService()),
            ConstructionModeService(load_settings(), FakeConstructionSearchService()),
        )
        first = self.client.post(
            "/chat/message",
            json={"message": "Como devo comecar uma casa de 120 m2 em Campinas?"},
        ).json()

        second = self.client.post(
            "/chat/message",
            json={"thread_id": first["thread"]["id"], "message": "Agora considere 90 m2 em Rio Preto"},
        )

        self.assertEqual(second.status_code, 200)
        payload = second.json()
        self.assertTrue(payload["conversation_memory"].get("conflicts"))
        self.assertTrue(any("antes" in item["message"] for item in payload["notifications"]))

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
        self.assertIn("project_materials", payload)

    def test_request_execution_event_endpoint_updates_project_state(self) -> None:
        thread = self.supabase.create_chat_thread(user_id="user-1", company_id="company-1", title="Teste")
        request_row = self.supabase.create_internal_request(
            company_id="company-1",
            user_id="user-1",
            thread_id=thread["id"],
            customer_name="Cotai Teste",
            notes="teste",
            items=[{"name": "cimento", "normalized_name": "cimento", "quantity": 20.0, "unit": "saco", "raw": "20 sacos cimento"}],
        )

        event = self.client.post(
            f"/requests/{request_row['id']}/execution-event",
            json={
                "event_type": "material_received",
                "material_name": "cimento",
                "quantity": 10,
                "note": "Primeira carga recebida na obra",
            },
        )

        self.assertEqual(event.status_code, 200)
        status_response = self.client.get(f"/requests/{request_row['id']}/status")
        self.assertEqual(status_response.status_code, 200)
        payload = status_response.json()
        self.assertTrue(payload["project_events"])
        self.assertEqual(payload["project_events"][0]["event_type"], "material_received")

    def test_ops_overview_endpoint(self) -> None:
        response = self.client.get("/ops/overview")
        self.assertEqual(response.status_code, 200)
        self.assertIn("X-Request-Id", response.headers)
        payload = response.json()
        self.assertEqual(payload["api"]["status"], "online")
        self.assertIn("queue", payload)

    def test_quote_search_endpoint_returns_structured_top_offers(self) -> None:
        response = self.client.post("/cotar", json={"query": "30 sacos de cimento votoran"})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["query"]["item"], "Cimento")
        self.assertEqual(payload["offers"][0]["supplier"], "Obramax")
        self.assertTrue(payload["meta"]["future_budgeting_ready"])

    def test_construction_estimate_endpoint_returns_initial_budget(self) -> None:
        response = self.client.post("/modo-construcao/estimar", json={"query": "Preciso estimar materiais para 120 m2 de piso padrao medio"})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["mode"], "construction")
        self.assertEqual(payload["input"]["system_type"], "floor")
        self.assertEqual(payload["input"]["building_standard"], "medio")
        self.assertEqual(payload["input"]["area_m2"], 120.0)
        self.assertTrue(payload["items"])
        self.assertTrue(payload["future_ready"]["sinapi_composition_ready"])

    def test_construction_analysis_and_procurement_endpoints_work_end_to_end(self) -> None:
        analysis = self.client.post(
            "/modo-construcao/analisar",
            json={"query": "Quero construir uma casa de 120 m2 em Campinas"},
        )
        self.assertEqual(analysis.status_code, 200)
        analysis_payload = analysis.json()
        self.assertEqual(analysis_payload["mode"], "construction_project")
        self.assertEqual(analysis_payload["status"], "ok")

        procurement = self.client.post(
            "/modo-construcao/compra",
            json={
                "query": "Quero construir uma casa de 120 m2 em Campinas",
                "context": analysis_payload.get("conversation", {}).get("context"),
                "selected_phase": "foundation",
                "include_live_quotes": True,
            },
        )
        self.assertEqual(procurement.status_code, 200)
        procurement_payload = procurement.json()
        self.assertEqual(procurement_payload["mode"], "construction_procurement")
        self.assertEqual(procurement_payload["status"], "ok")
        self.assertTrue(procurement_payload["purchase_list"])
        self.assertTrue(procurement_payload["phase_packages"])
        self.assertEqual(procurement_payload["selected_phase_key"], "foundation")
        self.assertTrue(procurement_payload["live_quotes"])

    def test_chat_keeps_project_statement_in_construction_mode_even_with_item_extraction_noise(self) -> None:
        response = self.client.post(
            "/chat/message",
            json={"message": "Quero construir uma casa com 600m2"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        assistant_messages = [row for row in payload["messages"] if row["role"] == "assistant"]
        self.assertTrue(assistant_messages)
        latest = assistant_messages[-1]
        self.assertEqual(latest["metadata"]["kind"], "construction_guidance")
        self.assertIn("IA de construcao civil", latest["content"])
        self.assertEqual(payload["thread"]["status"], "DRAFT")
        self.assertTrue(payload["conversation_memory"])

    def test_chat_treats_building_request_without_area_as_construction_guidance(self) -> None:
        response = self.client.post(
            "/chat/message",
            json={"message": "Quero fazer um predio com 4 andares"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        assistant_messages = [row for row in payload["messages"] if row["role"] == "assistant"]
        self.assertTrue(assistant_messages)
        latest = assistant_messages[-1]
        self.assertEqual(latest["metadata"]["kind"], "construction_guidance")
        self.assertIn("Para eu te orientar melhor agora", latest["content"])
        self.assertEqual(payload["construction_context"]["project_type"], "building")
        self.assertEqual(payload["construction_context"]["floors"], 4)

    def test_can_save_project_from_chat_and_list_it(self) -> None:
        first = self.client.post(
            "/chat/message",
            json={"message": "Quero construir uma casa de 120 m2 em Campinas"},
        )
        self.assertEqual(first.status_code, 200)
        thread_id = first.json()["thread"]["id"]

        saved = self.client.post(
            "/projects/from-thread",
            json={"thread_id": thread_id, "name": "Residencial Campinas"},
        )
        self.assertEqual(saved.status_code, 200)
        saved_payload = saved.json()
        self.assertEqual(saved_payload["project"]["name"], "Residencial Campinas")
        self.assertEqual(saved_payload["project"]["project_type"], "house")

        listed = self.client.get("/projects")
        self.assertEqual(listed.status_code, 200)
        projects = listed.json()["projects"]
        self.assertTrue(any(row["name"] == "Residencial Campinas" for row in projects))

        detail = self.client.get(f"/projects/{saved_payload['project']['id']}")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["project"]["name"], "Residencial Campinas")

    def test_chat_can_save_project_conversationally_after_user_confirms(self) -> None:
        first = self.client.post(
            "/chat/message",
            json={"message": "Quero construir uma casa de 120 m2 em Campinas"},
        )
        self.assertEqual(first.status_code, 200)
        payload = first.json()
        thread_id = payload["thread"]["id"]
        assistant_messages = [row for row in payload["messages"] if row["role"] == "assistant"]
        self.assertIn("Quer que eu salve esta obra como projeto?", assistant_messages[-1]["content"])

        confirm = self.client.post(
            "/chat/message",
            json={"thread_id": thread_id, "message": "sim"},
        )
        self.assertEqual(confirm.status_code, 200)
        confirm_payload = confirm.json()
        assistant_messages = [row for row in confirm_payload["messages"] if row["role"] == "assistant"]
        self.assertIn("Qual nome voce quer dar para este projeto?", assistant_messages[-1]["content"])

        named = self.client.post(
            "/chat/message",
            json={"thread_id": thread_id, "message": "Residencial Campinas"},
        )
        self.assertEqual(named.status_code, 200)
        named_payload = named.json()
        self.assertEqual(named_payload["project"]["name"], "Residencial Campinas")
        assistant_messages = [row for row in named_payload["messages"] if row["role"] == "assistant"]
        self.assertIn("Projeto Residencial Campinas salvo", assistant_messages[-1]["content"])

    def test_chat_accepts_more_natural_project_save_replies_and_suggested_name(self) -> None:
        first = self.client.post(
            "/chat/message",
            json={"message": "Quero construir uma casa de 120 m2 em Campinas"},
        )
        self.assertEqual(first.status_code, 200)
        thread_id = first.json()["thread"]["id"]

        confirm = self.client.post(
            "/chat/message",
            json={"thread_id": thread_id, "message": "pode salvar"},
        )
        self.assertEqual(confirm.status_code, 200)
        assistant_messages = [row for row in confirm.json()["messages"] if row["role"] == "assistant"]
        self.assertIn("Se quiser, pode usar", assistant_messages[-1]["content"])

        suggested = self.client.post(
            "/chat/message",
            json={"thread_id": thread_id, "message": "pode ser"},
        )
        self.assertEqual(suggested.status_code, 200)
        self.assertIsNotNone(suggested.json()["project"])

    def test_chat_accepts_decline_project_save_with_natural_reply(self) -> None:
        first = self.client.post(
            "/chat/message",
            json={"message": "Quero construir uma casa de 120 m2 em Campinas"},
        )
        self.assertEqual(first.status_code, 200)
        thread_id = first.json()["thread"]["id"]

        declined = self.client.post(
            "/chat/message",
            json={"thread_id": thread_id, "message": "deixa pra depois"},
        )
        self.assertEqual(declined.status_code, 200)
        payload = declined.json()
        self.assertIsNone(payload["project"])
        assistant_messages = [row for row in payload["messages"] if row["role"] == "assistant"]
        self.assertIn("Quando quiser salvar essa obra depois", assistant_messages[-1]["content"])

    def test_chat_can_save_project_when_user_sends_yes_and_name_together(self) -> None:
        first = self.client.post(
            "/chat/message",
            json={"message": "Quero construir uma casa de 120 m2 em Campinas"},
        )
        self.assertEqual(first.status_code, 200)
        thread_id = first.json()["thread"]["id"]

        combined = self.client.post(
            "/chat/message",
            json={"thread_id": thread_id, "message": "sim, pode salvar como Residencial Primavera"},
        )

        self.assertEqual(combined.status_code, 200)
        payload = combined.json()
        self.assertEqual(payload["project"]["name"], "Residencial Primavera")
        assistant_messages = [row for row in payload["messages"] if row["role"] == "assistant"]
        self.assertIn("Projeto Residencial Primavera salvo", assistant_messages[-1]["content"])

    def test_telemetry_endpoint_exposes_recent_cota_flow(self) -> None:
        self.client.post("/modo-construcao/analisar", json={"query": "Quero construir uma casa de 90 m2 em Campinas"})
        self.client.post("/cotar", json={"query": "30 sacos de cimento votoran"})

        response = self.client.get("/ops/telemetry")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("counters", payload)
        self.assertIn("recent_events", payload)
        counter_keys = " ".join(payload["counters"].keys())
        self.assertIn("construction_analysis_completed", counter_keys)
        self.assertIn("http_request_completed", counter_keys)

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
