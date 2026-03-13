from __future__ import annotations

import re
import unicodedata
from typing import Any


def clean_text(text: str) -> str:
    text = re.sub(r"[\u200e\u200f\u202a-\u202e]", "", text or "")
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", clean_text(text).lower())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def extract_request_code(text: str) -> str | None:
    match = re.search(r"pedido\s*(?:id)?\s*:\s*([A-Za-z0-9][A-Za-z0-9\-_/]*)", text, flags=re.IGNORECASE)
    return match.group(1).strip() if match else None


def canonical_delivery_mode(label: str | None) -> str | None:
    normalized = normalize_text(label or "")
    if not normalized:
        return None
    if "retirada" in normalized:
        return "RETIRADA"
    if "entrega" in normalized:
        return "ENTREGA"
    return None


def parse_item_line(line: str) -> dict[str, Any] | None:
    raw = re.sub(r"^[\-*\u2022\s]+", "", line or "").strip()
    raw = re.sub(r"^\d+[\)\.]\s*", "", raw).strip()
    raw = re.sub(r"^(?:preciso(?:ria)?|quero|cotar|comprar|precisamos|necessito)\s+(?:de\s+)?", "", raw, flags=re.IGNORECASE).strip()
    if not raw:
        return None

    units_pattern = r"(?:sacos?|un|unid(?:ades)?|m2|m3|m|latas?|caixas?|kg|g|l|barras?|ton|toneladas?)"
    patterns = (
        rf"^(?P<name>.+?)\s*-\s*(?P<qty>\d+(?:[\.,]\d+)?)\s*(?P<unit>{units_pattern})\b",
        rf"^(?P<qty>\d+(?:[\.,]\d+)?)\s*(?P<unit>{units_pattern})\b\s*(?:de\s+)?(?P<name>.+)$",
        rf"^(?P<name>.+?)\s*\((?P<qty>\d+(?:[\.,]\d+)?)\s*(?P<unit>{units_pattern})\)\s*$",
    )

    for pattern in patterns:
        match = re.match(pattern, raw, flags=re.IGNORECASE)
        if not match:
            continue
        quantity = float(match.group("qty").replace(",", "."))
        unit = match.group("unit").lower()
        name = match.group("name").strip(" -")
        return {"raw": raw, "name": name, "quantity": quantity, "unit": unit}

    return {"raw": raw, "name": raw, "quantity": None, "unit": None}


def extract_inline_items(text: str) -> list[dict[str, Any]]:
    cleaned = clean_text(text)
    if not cleaned:
        return []

    units_pattern = r"(?:sacos?|un|unid(?:ades)?|m2|m3|m|latas?|caixas?|kg|g|l|barras?|ton|toneladas?)"
    stop_pattern = r"(?=,\s*\d|\s+e\s+\d|\s+para\b|\s+com\b|\s+ate\b|\s+at[eé]\b|\s+no\b|\s+na\b|\s+em\b|$)"
    pattern = re.compile(
        rf"(?P<qty>\d+(?:[\.,]\d+)?)\s*(?P<unit>{units_pattern})\b\s*(?:de\s+)?(?P<name>.*?){stop_pattern}",
        flags=re.IGNORECASE,
    )

    items: list[dict[str, Any]] = []
    for match in pattern.finditer(cleaned):
        name = str(match.group("name") or "").strip(" ,.-")
        if not name:
            continue
        items.append(
            {
                "raw": match.group(0).strip(" ,.-"),
                "name": name,
                "quantity": float(match.group("qty").replace(",", ".")),
                "unit": match.group("unit").lower(),
            }
        )
    return items


def parse_request_message(text: str) -> dict[str, Any]:
    cleaned = clean_text(text)
    normalized = normalize_text(cleaned)
    parsed: dict[str, Any] = {
        "has_trigger": "#cotai" in normalized,
        "request_code": extract_request_code(cleaned),
        "delivery_mode": None,
        "delivery_location": None,
        "items": [],
    }
    if not parsed["has_trigger"]:
        return parsed

    lines = [line.strip() for line in cleaned.split("\n") if line.strip()]
    item_lines: list[str] = []
    in_items = False

    for line in lines:
        normalized_line = normalize_text(line)
        if normalized_line.startswith("#cotai") or "pedidoid" in normalized_line or "pedido id" in normalized_line:
            continue
        if normalized_line.startswith("entrega"):
            parsed["delivery_mode"] = "ENTREGA"
            delivery_context = line.split(":", 1)[-1].strip()
            if delivery_context and not parsed["delivery_location"]:
                parsed["delivery_location"] = delivery_context
            continue
        if normalized_line.startswith("retirada"):
            parsed["delivery_mode"] = "RETIRADA"
            pickup_context = line.split(":", 1)[-1].strip()
            if pickup_context and not parsed["delivery_location"]:
                parsed["delivery_location"] = pickup_context
            continue
        if normalized_line.startswith(("local", "cep", "endereco", "cidade", "bairro")):
            parsed["delivery_location"] = line.split(":", 1)[-1].strip()
            continue
        if any(normalized_line.startswith(prefix) for prefix in ("itens", "materiais", "lista", "produtos")):
            in_items = True
            inline = line.split(":", 1)[1].strip() if ":" in line else ""
            if inline:
                item_lines.extend([part.strip() for part in re.split(r"[;|]", inline) if part.strip()])
            continue
        if in_items or line.startswith("-") or line.startswith("\u2022") or re.match(r"^\d+[\)\.]\s+", line):
            item_lines.append(line)

    parsed["items"] = [item for item in (parse_item_line(line) for line in item_lines) if item]
    return parsed


def format_quantity(value: float | None) -> str:
    if value is None:
        return "-"
    if float(value).is_integer():
        return str(int(value))
    return str(round(value, 2)).replace(".", ",")


def format_item_label(item: dict[str, Any]) -> str:
    name = str(item.get("normalized_name") or item.get("name") or item.get("item_name") or item.get("raw") or "Item").strip()
    quantity = format_quantity(item.get("quantity"))
    unit = str(item.get("unit") or "un").strip()
    if quantity == "-":
        return name
    return f"{name} - {quantity} {unit}".strip()
