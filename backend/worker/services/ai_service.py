from __future__ import annotations

import json
import re
from typing import Any

import requests

from ..config import Settings
from ..utils.retry import retry_call
from ...shared.request_parser import extract_inline_items, format_item_label, parse_item_line
from .quote_response_formatter import build_user_quote_response


class AIService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.session = requests.Session()

    def close(self) -> None:
        self.session.close()

    def _chat_completion(self, system_prompt: str, user_payload: Any, temperature: float = 0) -> str:
        if not self.settings.groq_api_key:
            raise RuntimeError("GROQ_API_KEY is not configured")

        payload = {
            "model": self.settings.groq_model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
        }
        headers = {
            "Authorization": f"Bearer {self.settings.groq_api_key}",
            "Content-Type": "application/json",
        }

        def do_request() -> str:
            response = self.session.post(
                f"{self.settings.groq_base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=self.settings.request_timeout_seconds,
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"].strip()

        return retry_call(
            do_request,
            attempts=self.settings.retry_attempts,
            backoff_seconds=self.settings.retry_backoff_seconds,
            max_backoff_seconds=max(self.settings.retry_backoff_seconds, self.settings.request_timeout_seconds),
        )

    def _fallback_extract_items(self, text: str) -> list[dict[str, Any]]:
        inline_items = extract_inline_items(text)
        if inline_items:
            return inline_items

        lines = [line.strip() for line in re.split(r"[\n;]", text or "") if line.strip()]
        items: list[dict[str, Any]] = []
        for line in lines:
            item = parse_item_line(line)
            if item:
                item["normalized_name"] = item["name"]
                items.append(item)
        return items

    def extract_items(self, text: str) -> tuple[list[dict[str, Any]], str]:
        fallback = self._fallback_extract_items(text)
        if not self.settings.groq_api_key:
            return fallback, "local"

        prompt = (
            "Voce extrai itens de cotacao de materiais de construcao. "
            "Retorne JSON puro com a chave items. Cada item precisa ter: "
            "name, normalized_name, quantity, unit e raw. "
            "Nao invente itens. Se nao houver item, retorne {\"items\": []}."
        )
        try:
            content = self._chat_completion(prompt, {"message": text})
            match = re.search(r"\{.*\}", content, flags=re.DOTALL)
            payload = json.loads(match.group(0) if match else content)
            rows = payload.get("items", []) if isinstance(payload, dict) else []
            items: list[dict[str, Any]] = []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                name = str(row.get("name") or row.get("normalized_name") or row.get("raw") or "").strip()
                if not name:
                    continue
                quantity = row.get("quantity")
                try:
                    quantity = float(quantity) if quantity is not None else None
                except (TypeError, ValueError):
                    quantity = None
                items.append(
                    {
                        "name": name,
                        "normalized_name": str(row.get("normalized_name") or name).strip(),
                        "quantity": quantity,
                        "unit": str(row.get("unit") or "un").strip(),
                        "raw": str(row.get("raw") or name).strip(),
                    }
                )
            return items or fallback, "groq"
        except Exception as exc:  # noqa: BLE001
            return fallback, f"local_fallback:{exc}"

    def build_confirmation_message(self, items: list[dict[str, Any]]) -> tuple[str, str]:
        fallback_lines = ["Entendi seu pedido. Confirma estes itens?"]
        fallback_lines.extend([f"- {format_item_label(item)}" for item in items])
        fallback_lines.append("Se estiver correto, clique em Confirmar pedido.")
        fallback = "\n".join(fallback_lines)

        if not self.settings.groq_api_key:
            return fallback, "local"

        prompt = (
            "Voce escreve uma mensagem curta de confirmacao para um assistente de cotacao. "
            "Use portugues do Brasil. Seja objetivo, profissional e focado em confirmar os itens."
        )
        try:
            content = self._chat_completion(prompt, {"items": items})
            return content or fallback, "groq"
        except Exception as exc:  # noqa: BLE001
            return fallback, f"local_fallback:{exc}"

    def _fallback_summary(self, request_code: str, results: list[dict[str, Any]]) -> str:
        return build_user_quote_response(request_code, results)

    def summarize_quote(self, request_code: str, results: list[dict[str, Any]]) -> tuple[str, str]:
        return self._fallback_summary(request_code, results), "template"
