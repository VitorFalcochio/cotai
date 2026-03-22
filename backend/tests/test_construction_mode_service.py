from __future__ import annotations

import unittest

from backend.api.services.construction_mode_service import ConstructionModeService
from backend.worker.config import load_settings


class FakeSearchService:
    def search_supplier_snapshots(self, item_name: str, limit: int = 5):
        snapshot_prices = {
            "Concreto usinado fck 25": [
                {"price": 480.0, "source": "snapshot_leroy", "captured_at": "2026-03-19T10:00:00+00:00"},
                {"price": 510.0, "source": "snapshot_telhanorte", "captured_at": "2026-03-17T10:00:00+00:00"},
            ],
            "Aco CA-50": [{"price": 7.8, "source": "snapshot_obramax", "captured_at": "2026-03-18T10:00:00+00:00"}],
            "Bloco estrutural 14x19x39": [{"price": 5.9, "source": "snapshot_telhanorte", "captured_at": "2026-03-20T09:00:00+00:00"}],
            "Cimento CP II 50kg": [{"price": 41.5, "source": "snapshot_leroy", "captured_at": "2026-03-18T08:00:00+00:00"}],
            "Telha ceramica": [{"price": 58.0, "source": "snapshot_leroy", "captured_at": "2026-03-16T10:00:00+00:00"}],
            "Madeiramento para telhado": [{"price": 72.0, "source": "snapshot_catalog", "captured_at": "2026-03-15T10:00:00+00:00"}],
            "Manta termica": [{"price": 15.0, "source": "snapshot_catalog", "captured_at": "2026-03-14T10:00:00+00:00"}],
            "Piso ceramico": [{"price": 34.9, "source": "snapshot_telhanorte", "captured_at": "2026-03-20T07:00:00+00:00"}],
            "Argamassa colante AC-II 20kg": [{"price": 23.9, "source": "snapshot_leroy", "captured_at": "2026-03-18T11:00:00+00:00"}],
            "Tinta acrilica fosca 18L": [{"price": 269.0, "source": "snapshot_obramax", "captured_at": "2026-03-13T10:00:00+00:00"}],
            "Caixa de entulho 4m3": [{"price": 420.0, "source": "snapshot_local", "captured_at": "2026-03-19T11:00:00+00:00"}],
            "Disco de corte diamantado": [{"price": 55.0, "source": "snapshot_local", "captured_at": "2026-03-18T11:00:00+00:00"}],
            "Chapisco rolado 18L": [{"price": 189.0, "source": "snapshot_local", "captured_at": "2026-03-18T11:00:00+00:00"}],
            "Bica corrida": [{"price": 155.0, "source": "snapshot_local", "captured_at": "2026-03-20T11:00:00+00:00"}],
            "Tela soldada Q138": [{"price": 36.0, "source": "snapshot_local", "captured_at": "2026-03-19T11:00:00+00:00"}],
            "Junta de dilatacao": [{"price": 7.5, "source": "snapshot_local", "captured_at": "2026-03-19T11:00:00+00:00"}],
            "Aditivo plastificante": [{"price": 12.9, "source": "snapshot_local", "captured_at": "2026-03-17T11:00:00+00:00"}],
            "Tela de reforco leve": [{"price": 14.5, "source": "snapshot_local", "captured_at": "2026-03-17T11:00:00+00:00"}],
        }
        return snapshot_prices.get(item_name, [])[:limit]

    def search_catalog(self, item_name: str, limit: int = 5):
        catalog_prices = {
            "Concreto usinado fck 25": [{"price": 500.0, "source": "catalog"}],
            "Aco CA-50": [{"price": 8.2, "source": "catalog"}],
            "Brita 1": [{"price": 180.0, "source": "catalog"}],
            "Areia media": [{"price": 165.0, "source": "catalog"}],
            "Argamassa de assentamento": [{"price": 420.0, "source": "catalog"}],
            "Tubo PVC soldavel 25mm": [{"price": 8.9, "source": "catalog"}],
            "Tubo PVC esgoto 100mm": [{"price": 29.9, "source": "catalog"}],
            "Conexoes hidraulicas": [{"price": 6.5, "source": "catalog"}],
            "Fio 2.5mm": [{"price": 2.9, "source": "catalog"}],
            "Fio 1.5mm": [{"price": 2.1, "source": "catalog"}],
            "Caixa 4x2": [{"price": 3.8, "source": "catalog"}],
            "Rejunte 1kg": [{"price": 8.5, "source": "catalog"}],
            "Argamassa de regularizacao": [{"price": 28.9, "source": "catalog"}],
            "Massa para reboco": [{"price": 24.9, "source": "catalog"}],
            "Lona preta 200 micras": [{"price": 3.8, "source": "catalog"}],
            "Selador acrilico": [{"price": 11.9, "source": "catalog"}],
        }
        return catalog_prices.get(item_name, [])[:limit]


class EmptySearchService:
    def search_supplier_snapshots(self, item_name: str, limit: int = 5):
        return []

    def search_catalog(self, item_name: str, limit: int = 5):
        return []


class ConstructionModeServiceTests(unittest.TestCase):
    def test_analyze_project_returns_phase_based_plan_and_average_cost_for_house(self) -> None:
        service = ConstructionModeService(load_settings(), FakeSearchService())

        payload = service.analyze_project("Quero construir uma casa de 120 m2 em Rio Preto com 3 quartos e 2 banheiros")

        self.assertEqual(payload["mode"], "construction_project")
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["project"]["project_type"], "house")
        self.assertEqual(payload["project"]["area_m2"], 120.0)
        self.assertTrue(payload["phases"])
        self.assertTrue(payload["procurement_items"])
        self.assertTrue(any(phase["key"] == "foundation" for phase in payload["phases"]))
        self.assertIsInstance(payload["summary"]["estimated_total_cost_cents"], int)
        self.assertGreater(payload["summary"]["estimated_total_cost_cents"], 0)
        self.assertTrue(str(payload["summary"]["estimated_total_cost_display"]).startswith("R$ "))
        self.assertGreater(payload["summary"]["pricing_coverage_pct"], 0)
        self.assertIsInstance(payload["summary"]["estimated_total_cost_range_min_cents"], int)
        self.assertIsInstance(payload["summary"]["estimated_total_cost_range_max_cents"], int)
        self.assertLessEqual(payload["summary"]["estimated_total_cost_range_min_cents"], payload["summary"]["estimated_total_cost_cents"])
        self.assertGreaterEqual(payload["summary"]["estimated_total_cost_range_max_cents"], payload["summary"]["estimated_total_cost_cents"])
        self.assertIn(payload["summary"]["pricing_strength"], {"strong", "moderate", "weak"})
        self.assertTrue(payload["summary"]["freshest_reference_label"])
        foundation = next(phase for phase in payload["phases"] if phase["key"] == "foundation")
        self.assertIsInstance(foundation["estimated_cost_cents"], int)
        self.assertGreaterEqual(foundation["priced_materials"], 1)
        self.assertIsInstance(foundation["estimated_cost_range_min_cents"], int)
        self.assertIsInstance(foundation["estimated_cost_range_max_cents"], int)
        self.assertTrue(foundation["reference_age_label"])
        priced_item = next(item for item in payload["procurement_items"] if item["pricing_status"] == "estimated")
        self.assertIsInstance(priced_item["unit_price_cents"], int)
        self.assertIsInstance(priced_item["estimated_total_cents"], int)
        self.assertIsInstance(priced_item["unit_price_range_min_cents"], int)
        self.assertIsInstance(priced_item["unit_price_range_max_cents"], int)
        self.assertGreaterEqual(priced_item["reference_count"], 1)
        self.assertTrue(priced_item["reference_age_label"])

    def test_analyze_project_keeps_plan_when_some_items_have_no_price_reference(self) -> None:
        service = ConstructionModeService(load_settings(), EmptySearchService())

        payload = service.analyze_project("Quero construir uma casa de 80 m2")

        self.assertEqual(payload["status"], "ok")
        self.assertIsNone(payload["summary"]["estimated_total_cost_cents"])
        self.assertEqual(payload["summary"]["pricing_coverage_pct"], 0.0)
        self.assertEqual(payload["summary"]["pricing_strength"], "unavailable")
        self.assertTrue(all(item["pricing_status"] == "unavailable" for item in payload["procurement_items"]))

    def test_analyze_project_uses_conversation_context_to_refine_follow_up_message(self) -> None:
        service = ConstructionModeService(load_settings(), FakeSearchService())

        payload = service.analyze_project(
            "Padrao alto em Campinas com radier",
            context={"area_m2": 120.0, "project_type": "house"},
        )

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["project"]["area_m2"], 120.0)
        self.assertEqual(payload["project"]["project_type"], "house")
        self.assertEqual(payload["project"]["building_standard"], "alto")
        self.assertEqual(payload["project"]["location"], "Campinas")
        self.assertEqual(payload["project"]["foundation_type"], "radier")
        self.assertEqual(payload["conversation"]["stage"], "ready")
        self.assertFalse(payload["conversation"]["pending_fields"])

    def test_build_procurement_plan_groups_items_by_phase(self) -> None:
        service = ConstructionModeService(load_settings(), FakeSearchService())
        analysis = service.analyze_project("Quero construir uma casa de 120 m2 em Rio Preto")

        procurement = service.build_procurement_plan(analysis, selected_phase="foundation")

        self.assertEqual(procurement["mode"], "construction_procurement")
        self.assertEqual(procurement["status"], "ok")
        self.assertTrue(procurement["purchase_list"])
        self.assertTrue(procurement["phase_packages"])
        self.assertEqual(procurement["selected_phase_key"], "foundation")
        self.assertTrue(any(phase["key"] == "foundation" for phase in procurement["phase_packages"]))

    def test_analyze_project_supports_renovation_typology(self) -> None:
        service = ConstructionModeService(load_settings(), FakeSearchService())

        payload = service.analyze_project("Quero reformar 80 m2 de um apartamento em Campinas")

        self.assertEqual(payload["project"]["project_type"], "renovation")
        self.assertTrue(any(phase["key"] == "demolition" for phase in payload["phases"]))
        self.assertFalse(any(phase["key"] == "roof" for phase in payload["phases"]))

    def test_analyze_project_supports_wall_typology(self) -> None:
        service = ConstructionModeService(load_settings(), FakeSearchService())

        payload = service.analyze_project("Preciso fazer um muro de 45 m2 em Rio Preto")

        self.assertEqual(payload["project"]["project_type"], "wall")
        self.assertTrue(any(phase["key"] == "wall_foundation" for phase in payload["phases"]))
        self.assertTrue(any(phase["key"] == "wall_masonry" for phase in payload["phases"]))

    def test_analyze_project_supports_sidewalk_and_screed_typologies(self) -> None:
        service = ConstructionModeService(load_settings(), FakeSearchService())

        sidewalk_payload = service.analyze_project("Quero executar uma calcada de 60 m2 na frente da loja em Campinas")
        screed_payload = service.analyze_project("Preciso fazer um contrapiso de 90 m2 em Rio Preto")

        self.assertEqual(sidewalk_payload["project"]["project_type"], "sidewalk")
        self.assertTrue(any(phase["key"] == "pavement_base" for phase in sidewalk_payload["phases"]))
        self.assertEqual(screed_payload["project"]["project_type"], "screed")
        self.assertTrue(any(phase["key"] == "screed_finish" for phase in screed_payload["phases"]))

    def test_analyze_project_requests_clarification_when_core_scope_is_missing(self) -> None:
        service = ConstructionModeService(load_settings(), FakeSearchService())

        payload = service.analyze_project("Quero construir uma obra")

        self.assertEqual(payload["status"], "needs_clarification")
        self.assertIn("area_m2", payload["missing_fields"])
        self.assertIn("project_type", payload["missing_fields"])
        self.assertEqual(payload["phases"], [])

    def test_analyze_project_understands_building_with_multiple_floors_and_keeps_guided_conversation(self) -> None:
        service = ConstructionModeService(load_settings(), FakeSearchService())

        payload = service.analyze_project("Quero fazer um predio com 4 andares")

        self.assertEqual(payload["status"], "needs_clarification")
        self.assertEqual(payload["project"]["project_type"], "building")
        self.assertEqual(payload["project"]["floors"], 4)
        self.assertIn("area_m2", payload["missing_fields"])
        self.assertTrue(any("predio" in question.lower() or "pavimento" in question.lower() for question in payload["next_questions"]))


if __name__ == "__main__":
    unittest.main()
