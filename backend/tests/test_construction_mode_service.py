from __future__ import annotations

import unittest

from backend.api.services.construction_mode_service import ConstructionModeService
from backend.worker.config import load_settings


class FakeSearchService:
    def search_supplier_snapshots(self, item_name: str, limit: int = 5):
        snapshot_prices = {
            "Concreto usinado fck 25": [{"price": 480.0, "source": "snapshot_leroy"}],
            "Aco CA-50": [{"price": 7.8, "source": "snapshot_obramax"}],
            "Bloco estrutural 14x19x39": [{"price": 5.9, "source": "snapshot_telhanorte"}],
            "Cimento CP II 50kg": [{"price": 41.5, "source": "snapshot_leroy"}],
            "Telha ceramica": [{"price": 58.0, "source": "snapshot_leroy"}],
            "Madeiramento para telhado": [{"price": 72.0, "source": "snapshot_catalog"}],
            "Manta termica": [{"price": 15.0, "source": "snapshot_catalog"}],
            "Piso ceramico": [{"price": 34.9, "source": "snapshot_telhanorte"}],
            "Argamassa colante AC-II 20kg": [{"price": 23.9, "source": "snapshot_leroy"}],
            "Tinta acrilica fosca 18L": [{"price": 269.0, "source": "snapshot_obramax"}],
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
        foundation = next(phase for phase in payload["phases"] if phase["key"] == "foundation")
        self.assertIsInstance(foundation["estimated_cost_cents"], int)
        self.assertGreaterEqual(foundation["priced_materials"], 1)
        priced_item = next(item for item in payload["procurement_items"] if item["pricing_status"] == "estimated")
        self.assertIsInstance(priced_item["unit_price_cents"], int)
        self.assertIsInstance(priced_item["estimated_total_cents"], int)

    def test_analyze_project_keeps_plan_when_some_items_have_no_price_reference(self) -> None:
        service = ConstructionModeService(load_settings(), EmptySearchService())

        payload = service.analyze_project("Quero construir uma casa de 80 m2")

        self.assertEqual(payload["status"], "ok")
        self.assertIsNone(payload["summary"]["estimated_total_cost_cents"])
        self.assertEqual(payload["summary"]["pricing_coverage_pct"], 0.0)
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

    def test_analyze_project_requests_clarification_when_core_scope_is_missing(self) -> None:
        service = ConstructionModeService(load_settings(), FakeSearchService())

        payload = service.analyze_project("Quero construir uma obra")

        self.assertEqual(payload["status"], "needs_clarification")
        self.assertIn("area_m2", payload["missing_fields"])
        self.assertIn("project_type", payload["missing_fields"])
        self.assertEqual(payload["phases"], [])


if __name__ == "__main__":
    unittest.main()
