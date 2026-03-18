from __future__ import annotations

import re
from typing import Any


def _format_brl(value: float | None) -> str:
    if value is None:
        return "Preco indisponivel"
    raw = f"{value:,.2f}"
    return "R$ " + raw.replace(",", "X").replace(".", ",").replace("X", ".")


def _format_quantity(quantity: Any, unit: str | None) -> str:
    if quantity is None:
        return f"- {unit or 'un'}".strip()
    numeric = float(quantity)
    amount = int(numeric) if numeric.is_integer() else round(numeric, 2)
    return f"{amount} {unit or 'un'}"


def _humanize_item_name(value: str) -> str:
    cleaned = str(value or "").strip()
    if not cleaned:
        return "Item"
    cleaned = re.sub(r"\bcp2\b", "CP-II", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bcp3\b", "CP-III", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:1].upper() + cleaned[1:]


def _offer_line(offer: dict[str, Any], unit: str, quantity: Any = None, include_index: int | None = None) -> list[str]:
    supplier = str(offer.get("supplier") or "Fornecedor").strip()
    unit_price = offer.get("unit_price") if offer.get("unit_price") is not None else offer.get("price")
    estimated_total = offer.get("estimated_total")
    if estimated_total is None and isinstance(unit_price, (int, float)) and quantity is not None:
        estimated_total = float(unit_price) * float(quantity)

    title = f"{include_index}. {supplier}" if include_index is not None else supplier
    lines = [title, f"{_format_brl(unit_price)} por {unit}"]
    if estimated_total is not None:
        lines.append(f"Total estimado: {_format_brl(float(estimated_total))}")
    return lines


def _build_observation(entry: dict[str, Any], offers: list[dict[str, Any]]) -> str | None:
    if not offers:
        return "Nao encontrei referencias suficientes para fechar este item agora."

    if len(offers) == 1:
        return "Use esta referencia como ponto de partida para negociar."

    market = entry.get("market_context") or {}
    spread_pct = market.get("price_spread_pct")
    if isinstance(spread_pct, (int, float)) and spread_pct >= 18:
        return "Os valores variaram bastante. Vale confirmar disponibilidade antes de fechar."

    low_confidence = float(entry.get("analysis_confidence") or 0) < 0.68
    if low_confidence:
        return "Encontrei poucas referencias consistentes. Vale validar antes de comprar."

    return None


def _format_market_block(entry: dict[str, Any], unit: str) -> list[str]:
    market = entry.get("market_context") or {}
    median_price = market.get("median_unit_price")
    lowest_price = market.get("lowest_unit_price")
    highest_price = market.get("highest_unit_price")
    if median_price is None:
        unit_prices = [
            float(offer.get("unit_price") if offer.get("unit_price") is not None else offer.get("price"))
            for offer in (entry.get("offers") or [])[:3]
            if isinstance(offer.get("unit_price") if offer.get("unit_price") is not None else offer.get("price"), (int, float))
        ]
        if unit_prices:
            median_price = round(sum(unit_prices) / len(unit_prices), 2)

    if median_price is None and lowest_price is None and highest_price is None:
        return []

    lines = ["Mercado"]
    if median_price is not None:
        lines.append(f"Media: {_format_brl(float(median_price))} por {unit}")
    if (
        lowest_price is not None
        and highest_price is not None
        and float(lowest_price) != float(highest_price)
    ):
        lines.append(f"Faixa: {_format_brl(float(lowest_price))} a {_format_brl(float(highest_price))}")
    return lines


def build_user_quote_response(request_code: str, results: list[dict[str, Any]]) -> str:
    lines: list[str] = ["Cotacao encontrada", ""]
    total_order_value = 0.0
    has_total = False

    for index, entry in enumerate(results):
        item_name = _humanize_item_name(entry.get("canonical_name") or entry.get("item_name") or "Item")
        quantity = _format_quantity(entry.get("quantity"), entry.get("unit") or "un")
        offers = list(entry.get("offers") or [])
        best_offer = entry.get("best_overall_offer")
        unit = str(entry.get("unit") or "un").strip()

        lines.append(item_name)
        lines.append(f"Quantidade: {quantity}")
        lines.append("")

        if not offers or not best_offer:
            lines.append("Nenhuma oferta encontrada no momento.")
        elif len(offers) == 1:
            lines.extend(_offer_line(best_offer, unit, entry.get("quantity")))
            estimated_total = best_offer.get("estimated_total")
            if estimated_total is None and isinstance(best_offer.get("unit_price") if best_offer.get("unit_price") is not None else best_offer.get("price"), (int, float)) and entry.get("quantity") is not None:
                estimated_total = float(best_offer.get("unit_price") if best_offer.get("unit_price") is not None else best_offer.get("price")) * float(entry.get("quantity"))
            if isinstance(estimated_total, (int, float)):
                total_order_value += float(estimated_total)
                has_total = True
        else:
            lines.append("Melhores opcoes")
            for offer_index, offer in enumerate(offers[:2], start=1):
                lines.extend(_offer_line(offer, unit, entry.get("quantity"), include_index=offer_index))
                estimated_total = offer.get("estimated_total")
                if estimated_total is None and isinstance(offer.get("unit_price") if offer.get("unit_price") is not None else offer.get("price"), (int, float)) and entry.get("quantity") is not None:
                    estimated_total = float(offer.get("unit_price") if offer.get("unit_price") is not None else offer.get("price")) * float(entry.get("quantity"))
                if offer_index == 1 and isinstance(estimated_total, (int, float)):
                    total_order_value += float(estimated_total)
                    has_total = True
                if offer_index < min(len(offers), 2):
                    lines.append("")

        market_lines = _format_market_block(entry, unit)
        if market_lines:
            lines.append("")
            lines.extend(market_lines)

        observation = _build_observation(entry, offers)
        if observation:
            lines.append("")
            lines.append("Observacao")
            lines.append(observation)

        if index < len(results) - 1:
            lines.extend(["", "---", ""])

    if len(results) > 1 and has_total:
        lines.extend(["", f"Total estimado do pedido: {_format_brl(total_order_value)}"])

    return "\n".join(lines).strip()
