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

    def _chat_completion_groq(self, system_prompt: str, user_payload: Any, temperature: float = 0) -> str:
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

    def _chat_completion_gemini(self, system_prompt: str, user_payload: Any, temperature: float = 0) -> str:
        if not self.settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")

        payload = {
            "system_instruction": {
                "parts": [{"text": system_prompt}],
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": json.dumps(user_payload, ensure_ascii=False)}],
                }
            ],
            "generationConfig": {
                "temperature": temperature,
                "responseMimeType": "application/json",
            },
        }
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.settings.gemini_api_key,
        }

        def do_request() -> str:
            response = self.session.post(
                f"{self.settings.gemini_base_url}/models/{self.settings.gemini_model}:generateContent",
                headers=headers,
                json=payload,
                timeout=self.settings.request_timeout_seconds,
            )
            response.raise_for_status()
            body = response.json()
            candidates = body.get("candidates") or []
            if not candidates:
                raise RuntimeError("Gemini returned no candidates")
            parts = candidates[0].get("content", {}).get("parts") or []
            text_parts = [str(part.get("text") or "").strip() for part in parts if isinstance(part, dict) and part.get("text")]
            content = "\n".join(part for part in text_parts if part).strip()
            if not content:
                raise RuntimeError("Gemini returned empty content")
            return content

        return retry_call(
            do_request,
            attempts=self.settings.retry_attempts,
            backoff_seconds=self.settings.retry_backoff_seconds,
            max_backoff_seconds=max(self.settings.retry_backoff_seconds, self.settings.request_timeout_seconds),
        )

    def _chat_completion(self, system_prompt: str, user_payload: Any, temperature: float = 0) -> tuple[str, str]:
        errors: list[str] = []
        providers: list[tuple[str, Any]] = []
        if self.settings.gemini_api_key:
            providers.append(("gemini", self._chat_completion_gemini))
        if self.settings.groq_api_key:
            providers.append(("groq", self._chat_completion_groq))
        if not providers:
            raise RuntimeError("No AI provider configured")

        for provider_name, handler in providers:
            try:
                return handler(system_prompt, user_payload, temperature), provider_name
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{provider_name}:{exc}")

        raise RuntimeError("; ".join(errors) or "All AI providers failed")

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

    def _coach_opening(self) -> str:
        return "Aqui e a Cota, atuando como mestre de obra da compra."

    def extract_items(self, text: str) -> tuple[list[dict[str, Any]], str]:
        fallback = self._fallback_extract_items(text)
        if not self.settings.groq_api_key and not self.settings.gemini_api_key:
            return fallback, "local"

        prompt = (
            "Voce extrai itens de cotacao de materiais de construcao. "
            "Retorne JSON puro com a chave items. Cada item precisa ter: "
            "name, normalized_name, quantity, unit e raw. "
            "Nao invente itens. Se nao houver item, retorne {\"items\": []}."
        )
        try:
            content, provider = self._chat_completion(prompt, {"message": text})
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
            return items or fallback, provider
        except Exception as exc:  # noqa: BLE001
            return fallback, f"local_fallback:{exc}"

    def build_confirmation_message(self, items: list[dict[str, Any]]) -> tuple[str, str]:
        fallback_lines = [f"{self._coach_opening()} Revise comigo estes itens antes de eu mandar para cotacao:"]
        fallback_lines.extend([f"- {format_item_label(item)}" for item in items])
        fallback_lines.append("Se estiver tudo certo, confirme o pedido. Se faltar medida, bitola, marca ou padrao, me avise para eu ajustar.")
        fallback = "\n".join(fallback_lines)

        if not self.settings.groq_api_key and not self.settings.gemini_api_key:
            return fallback, "local"

        prompt = (
            "Voce e a Cota, uma IA que fala como mestre de obra experiente e orientado por dados. "
            "Escreva uma mensagem curta de confirmacao em portugues do Brasil. "
            "Seja objetivo, pratico, confiavel e focado em revisar itens antes da compra. "
            "Nao use girias excessivas. Soe experiente em obra, mas profissional."
        )
        try:
            content, provider = self._chat_completion(prompt, {"items": items})
            cleaned_content = str(content or "").strip()
            match = re.search(r"\{.*\}", cleaned_content, flags=re.DOTALL)
            if match:
                try:
                    payload = json.loads(match.group(0))
                except json.JSONDecodeError:
                    payload = None
                if isinstance(payload, dict):
                    cleaned_message = str(payload.get("message") or "").strip()
                    if cleaned_message:
                        return cleaned_message, provider
            return cleaned_content or fallback, provider
        except Exception as exc:  # noqa: BLE001
            return fallback, f"local_fallback:{exc}"

    def extract_material_entities(self, text: str) -> tuple[dict[str, Any], str]:
        prompt = (
            "Voce extrai entidades de um pedido de material para engenharia civil. "
            "Retorne JSON puro com as chaves: item, marca, especificacao, quantidade, unidade e search_terms. "
            "Se alguma informacao nao existir, use null. "
            "Nao invente dados tecnicos. "
            "Exemplo: {\"item\":\"Cimento\",\"marca\":\"Votoran\",\"especificacao\":\"CP II\",\"quantidade\":30,\"unidade\":\"saco\",\"search_terms\":[\"cimento votoran cp ii 50kg\"]}"
        )
        content, provider = self._chat_completion(prompt, {"message": text})
        match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        payload = json.loads(match.group(0) if match else content)
        if not isinstance(payload, dict):
            raise RuntimeError("Invalid AI payload for material extraction")
        return payload, provider

    def _fallback_summary(self, request_code: str, results: list[dict[str, Any]]) -> str:
        summary = build_user_quote_response(request_code, results)
        return f"{self._coach_opening()}\n{summary}"

    def summarize_quote(self, request_code: str, results: list[dict[str, Any]]) -> tuple[str, str]:
        return self._fallback_summary(request_code, results), "template"
