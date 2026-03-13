from __future__ import annotations

import json
import re
from typing import Any

import requests

from ..config import Settings
from ..utils.retry import retry_call
from ...shared.request_parser import extract_inline_items, format_item_label, parse_item_line


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
            "Você extrai itens de cotação de materiais de construção. "
            "Retorne JSON puro com a chave items. Cada item precisa ter: "
            "name, normalized_name, quantity, unit e raw. "
            "Não invente itens. Se não houver item, retorne {\"items\": []}."
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
                item = {
                    "name": name,
                    "normalized_name": str(row.get("normalized_name") or name).strip(),
                    "quantity": quantity,
                    "unit": str(row.get("unit") or "un").strip(),
                    "raw": str(row.get("raw") or name).strip(),
                }
                items.append(item)
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
            "Você escreve uma mensagem curta de confirmação para um assistente de cotação. "
            "Use portugues do Brasil. Seja objetivo, profissional e focado em confirmar os itens."
        )
        try:
            content = self._chat_completion(prompt, {"items": items})
            return content or fallback, "groq"
        except Exception as exc:  # noqa: BLE001
            return fallback, f"local_fallback:{exc}"

    def _fallback_summary(self, request_code: str, results: list[dict[str, Any]]) -> str:
        lines = [f"Pedido {request_code}", "Cotacao preliminar consolidada:", ""]
        estimated_total = 0.0
        estimated_savings = 0.0
        for index, entry in enumerate(results, start=1):
            quantity = entry.get("quantity")
            unit = entry.get("unit") or "un"
            item_label = entry["item_name"]
            if quantity is not None:
                qty_text = int(quantity) if float(quantity).is_integer() else round(float(quantity), 2)
                item_label = f"{item_label} - {qty_text} {unit}"
            lines.append(f"{index}. {item_label}")
            offers = entry["offers"]
            if offers:
                priced_offers = [offer for offer in offers if offer.get("price") is not None]
                if priced_offers:
                    best_price = min(float(offer["price"]) for offer in priced_offers)
                    worst_price = max(float(offer["price"]) for offer in priced_offers)
                    multiplier = float(quantity) if quantity is not None else 1.0
                    estimated_total += best_price * multiplier
                    estimated_savings += max(0.0, (worst_price - best_price) * multiplier)
                best_offer = next((offer for offer in offers if offer.get("best_hint")), offers[0])
                best_unit_price = best_offer.get("price")
                if best_unit_price is not None:
                    total_text = _format_brl(float(best_unit_price) * (float(quantity) if quantity is not None else 1.0))
                else:
                    total_text = "Total indisponivel"
                lines.append(
                    f"- Melhor oferta: {_format_brl(best_unit_price)} | {best_offer.get('supplier')} | {best_offer.get('delivery_label') or 'Prazo não informado'} | {total_text}"
                )
                for offer in offers[:3]:
                    lines.append(
                        f"  * {_format_brl(offer.get('price'))} | {offer.get('supplier')} | {offer.get('delivery_label') or 'Prazo não informado'} | {offer.get('source')}"
                    )
            else:
                lines.append("- Nenhuma oferta encontrada no momento.")
            lines.append("")
        lines.append(f"Total estimado da melhor composicao: {_format_brl(estimated_total)}")
        if estimated_savings > 0:
            lines.append(f"Economia potencial visivel: {_format_brl(estimated_savings)}")
        lines.append("Resumo gerado automaticamente pela Cotai.")
        return "\n".join(lines).strip()

    def summarize_quote(self, request_code: str, results: list[dict[str, Any]]) -> tuple[str, str]:
        fallback = self._fallback_summary(request_code, results)
        if not self.settings.groq_api_key:
            return fallback, "local"

        prompt = (
            "Formate uma resposta profissional e deterministica em portugues do Brasil. "
            "Não invente dados, não altere valores e não adicione opiniões. "
            "Organize por item e destaque a melhor oferta visivel."
        )
        try:
            content = self._chat_completion(prompt, {"request_code": request_code, "results": results})
            return content or fallback, "groq"
        except Exception as exc:  # noqa: BLE001
            return fallback, f"local_fallback:{exc}"
