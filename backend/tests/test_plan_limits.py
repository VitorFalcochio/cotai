from __future__ import annotations

import unittest

from backend.api.services.plan_limits import get_plan_definition, normalize_plan_key
from backend.worker.testing import InMemorySupabase


class PlanLimitTests(unittest.TestCase):
    def test_normalize_plan_key_supports_starter_aliases(self) -> None:
        self.assertEqual(normalize_plan_key("starter"), "starter")
        self.assertEqual(normalize_plan_key("trial"), "starter")

    def test_get_plan_definition_exposes_starter_limits(self) -> None:
        plan = get_plan_definition("starter")
        self.assertEqual(plan["label"], "Starter")
        self.assertEqual(plan["request_limit"], 20)
        self.assertEqual(plan["user_limit"], 1)

    def test_plan_limits_can_remain_configured_while_enforcement_is_disabled(self) -> None:
        supabase = InMemorySupabase()
        context = supabase.assert_company_can_create_request("company-1", profile=supabase.get_profile("user-1"))
        self.assertFalse(context["billing_enabled"])
        self.assertFalse(context["plan_limits_enforced"])
        self.assertEqual(context["monthly_price"], 89)


if __name__ == "__main__":
    unittest.main()
