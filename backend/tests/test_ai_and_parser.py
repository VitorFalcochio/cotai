from __future__ import annotations

import unittest

from backend.api.services.request_parser import RequestParserService
from backend.worker.config import load_settings
from backend.worker.services.ai_service import AIService


class _DummyAIService:
    def extract_items(self, text: str):
        return [], "dummy"

    def build_confirmation_message(self, items):
        return "ok", "dummy"


class RequestParserServiceTests(unittest.TestCase):
    def test_caution_does_not_flag_ferragem_for_sacos(self) -> None:
        service = RequestParserService(_DummyAIService())

        payload = service.build_confirmation(
            [
                {
                    "name": "cimento cp ii 50kg",
                    "normalized_name": "cimento cp ii 50kg",
                    "quantity": 12.0,
                    "unit": "sacos",
                    "raw": "12 sacos de cimento cp ii 50kg",
                }
            ]
        )

        self.assertNotIn("ferragem", payload["message"].lower())


class AIServiceTests(unittest.TestCase):
    def test_build_confirmation_message_extracts_message_from_json_payload(self) -> None:
        service = AIService(load_settings())
        service._chat_completion = lambda prompt, payload, temperature=0: ('{"message":"Confere os 12 sacos de cimento antes de seguir."}', "gemini")  # type: ignore[method-assign]

        message, provider = service.build_confirmation_message(
            [
                {
                    "name": "cimento cp ii 50kg",
                    "normalized_name": "cimento cp ii 50kg",
                    "quantity": 12.0,
                    "unit": "sacos",
                    "raw": "12 sacos de cimento cp ii 50kg",
                }
            ]
        )

        self.assertEqual(provider, "gemini")
        self.assertEqual(message, "Confere os 12 sacos de cimento antes de seguir.")


if __name__ == "__main__":
    unittest.main()
