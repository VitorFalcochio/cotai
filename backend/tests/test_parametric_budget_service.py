from __future__ import annotations

import unittest

from backend.api.services.parametric_budget_service import ParametricBudgetService


class ParametricBudgetServiceTests(unittest.TestCase):
    def test_estimate_from_text_for_floor_medium_standard(self) -> None:
        service = ParametricBudgetService()
        payload = service.estimate_from_text("Preciso estimar materiais para 120 m2 de piso padrao medio")

        self.assertEqual(payload["mode"], "construction")
        self.assertEqual(payload["input"]["system_type"], "floor")
        self.assertEqual(payload["input"]["building_standard"], "medio")
        self.assertEqual(payload["input"]["area_m2"], 120.0)
        self.assertTrue(any(item["material"] == "Piso ceramico" for item in payload["items"]))

    def test_estimate_from_area_for_wall_high_standard(self) -> None:
        service = ParametricBudgetService()
        payload = service.estimate_from_area(area_m2=80, building_standard="alto", system_type="wall")

        self.assertEqual(payload["input"]["system_type"], "wall")
        self.assertEqual(payload["input"]["building_standard"], "alto")
        self.assertTrue(payload["items"])
        self.assertTrue(all(item["quantity"] for item in payload["items"]))
