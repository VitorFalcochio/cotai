from __future__ import annotations

import json
import time
from typing import Any

import requests

from ..config import Settings
from ..utils.retry import retry_call


def _format_brl(value: float | None) -> str:
    if value is None:
        return "Preco indisponivel"
    raw = f"{value:,.2f}"
    return "R$ " + raw.replace(",", "X").replace(".", ",").replace("X", ".")


class AIService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.session = requests.Session()

    def close(self) -> None:
        self.session.close()

    def _fallback_summary(self, request_code: str, results: list[dict[str, Any]]) -> str:
        lines = [f"#COTAI", f"Pedido: {request_code}", "Cotacao preliminar:", ""]
        for index, entry in enumerate(results, start=1):
            lines.append(f"{index}. {entry['item_name']}")
            if entry["offers"]:
                for offer in entry["offers"][:3]:
                    lines.append(f"- {_format_brl(offer.get('price'))} | {offer.get('supplier')} | {offer.get('source')}")
            else:
                lines.append("- Nenhuma oferta encontrada no momento.")
            lines.append("")
        lines.append("Resposta gerada de forma deterministica pelo worker.")
        return "\n".join(lines).strip()

    def summarize_quote(self, request_code: str, results: list[dict[str, Any]]) -> tuple[str, str]:
        fallback = self._fallback_summary(request_code, results)
        if not self.settings.groq_api_key:
            return fallback, "local"

        payload = {
            "model": self.settings.groq_model,
            "temperature": 0,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Formate uma resposta profissional e deterministica em portugues do Brasil. "
                        "Nao invente dados, nao mude valores, nao adicione opinioes."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps({"request_code": request_code, "results": results}, ensure_ascii=False),
                },
            ],
        }
        headers = {
            "Authorization": f"Bearer {self.settings.groq_api_key}",
            "Content-Type": "application/json",
        }

        try:
            def do_request() -> tuple[str, str]:
                response = self.session.post(
                    f"{self.settings.groq_base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=self.settings.request_timeout_seconds,
                )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"].strip()
                return content or fallback, "groq"

            return retry_call(
                do_request,
                attempts=self.settings.retry_attempts,
                backoff_seconds=self.settings.retry_backoff_seconds,
                max_backoff_seconds=max(self.settings.retry_backoff_seconds, self.settings.request_timeout_seconds),
            )
        except Exception as exc:  # noqa: BLE001
            return fallback, f"local_fallback:{exc}"
