from __future__ import annotations

import re

from .models import ProjectSpec, RoomSpec


PROJECT_DIMENSION_PATTERN = re.compile(r"(\d+(?:[.,]\d+)?)\s*x\s*(\d+(?:[.,]\d+)?)", re.IGNORECASE)
SECTION_MARKERS = {
    0: ("terreo", "pavimento terreo", "andar terreo"),
    1: ("pavimento superior", "andar superior", "segundo andar", "segundo pavimento", "piso superior"),
    2: ("terceiro andar", "terceiro pavimento"),
}

ROOM_LIBRARY: dict[str, dict[str, object]] = {
    "sala de estar": {"aliases": ("sala de estar",), "size": (6.0, 5.0), "category": "social"},
    "sala de jantar": {"aliases": ("sala de jantar", "jantar"), "size": (5.0, 4.0), "category": "social"},
    "sala intima": {"aliases": ("sala intima", "sala de tv"), "size": (4.5, 4.0), "category": "social"},
    "cozinha gourmet": {"aliases": ("cozinha gourmet",), "size": (6.0, 5.0), "category": "social"},
    "cozinha": {"aliases": ("cozinha",), "size": (4.0, 3.5), "category": "social"},
    "despensa": {"aliases": ("despensa",), "size": (2.0, 2.0), "category": "service"},
    "lavabo": {"aliases": ("lavabo",), "size": (2.0, 1.8), "category": "service"},
    "escritorio": {"aliases": ("escritorio",), "size": (4.0, 3.5), "category": "social"},
    "area de servico": {"aliases": ("area de servico",), "size": (3.5, 3.0), "category": "service"},
    "lavanderia": {"aliases": ("lavanderia",), "size": (3.5, 3.0), "category": "service"},
    "deposito": {"aliases": ("deposito",), "size": (2.5, 2.0), "category": "service"},
    "espaco gourmet": {"aliases": ("espaco gourmet", "varanda gourmet"), "size": (7.0, 4.0), "category": "leisure"},
    "varanda": {"aliases": ("varanda",), "size": (6.0, 2.5), "category": "leisure"},
    "garagem": {"aliases": ("garagem",), "size": (7.5, 6.0), "category": "garage"},
    "piscina": {"aliases": ("piscina",), "size": (8.0, 4.0), "category": "external"},
    "suite master": {"aliases": ("suite master",), "size": (7.0, 6.0), "category": "private"},
    "suite": {"aliases": ("suite",), "size": (4.5, 4.0), "category": "private"},
    "quarto": {"aliases": ("quarto",), "size": (3.5, 3.5), "category": "private"},
    "closet": {"aliases": ("closet",), "size": (3.0, 2.5), "category": "private"},
    "banheiro": {"aliases": ("banheiro",), "size": (2.4, 2.2), "category": "private"},
}

QUANTITY_ROOM_PATTERN = re.compile(r"(\d+)\s+(suites?|quartos?|banheiros?)", re.IGNORECASE)


def _to_float(value: str) -> float:
    return float(value.replace(",", "."))


def _normalize_text(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _normalize_room_name(name: str) -> str:
    cleaned = " ".join(str(name or "").strip().split())
    return cleaned[:1].upper() + cleaned[1:] if cleaned else "Ambiente"


def _detect_project_type(lowered: str) -> str:
    if "mansao" in lowered:
        return "mansao"
    if "galpao" in lowered:
        return "galpao"
    if "predio" in lowered or "edificio" in lowered:
        return "predio"
    if "apartamento" in lowered:
        return "apartamento"
    if "sobrado" in lowered:
        return "sobrado"
    if "casa" in lowered:
        return "casa"
    return "residencial"


def _detect_floors(lowered: str) -> int:
    if any(token in lowered for token in ("3 andares", "tres andares", "3 pavimentos", "tres pavimentos")):
        return 3
    if any(token in lowered for token in ("2 andares", "dois andares", "2 pavimentos", "dois pavimentos", "sobrado")):
        return 2
    return 1


def _canonical_room_key(fragment: str) -> str | None:
    lowered = _normalize_text(fragment)
    for canonical_name, config in ROOM_LIBRARY.items():
        for alias in config["aliases"]:
            if alias in lowered:
                return canonical_name
    return None


def _section_level_for_match(index: int, text: str, floors: int) -> int:
    if floors <= 1:
        return 0
    lower_text = text.lower()
    nearest_level = 0
    best_distance = None
    for level, markers in SECTION_MARKERS.items():
        for marker in markers:
            marker_index = lower_text.rfind(marker, 0, index + 1)
            if marker_index < 0:
                continue
            distance = index - marker_index
            if best_distance is None or distance < best_distance:
                best_distance = distance
                nearest_level = level
    return nearest_level


def _room_level(category: str, detected_level: int, floors: int) -> int:
    if floors <= 1:
        return 0
    if detected_level > 0:
        return min(detected_level, floors - 1)
    if category == "private":
        return 1
    return 0


def _build_room(canonical_name: str, width: float, depth: float, floors: int, detected_level: int) -> RoomSpec:
    config = ROOM_LIBRARY[canonical_name]
    category = str(config["category"])
    return RoomSpec(
        name=_normalize_room_name(canonical_name),
        width=width,
        depth=depth,
        level=_room_level(category, detected_level, floors),
        category=category,
    )


def _extract_explicit_rooms(text: str, floors: int) -> list[RoomSpec]:
    aliases = sorted(
        {alias for config in ROOM_LIBRARY.values() for alias in config["aliases"]},
        key=len,
        reverse=True,
    )
    alias_pattern = "|".join(re.escape(alias) for alias in aliases)
    explicit_pattern = re.compile(
        rf"({alias_pattern})(?:\s+de)?\s+(\d+(?:[.,]\d+)?)\s*x\s*(\d+(?:[.,]\d+)?)",
        re.IGNORECASE,
    )

    rooms: list[RoomSpec] = []
    for match in explicit_pattern.finditer(text):
        canonical_name = _canonical_room_key(match.group(1))
        if not canonical_name:
            continue
        detected_level = _section_level_for_match(match.start(), text, floors)
        rooms.append(
            _build_room(
                canonical_name,
                _to_float(match.group(2)),
                _to_float(match.group(3)),
                floors,
                detected_level,
            )
        )
    return rooms


def _extract_quantity_rooms(text: str, floors: int, existing_names: list[str]) -> list[RoomSpec]:
    existing_lower = {name.lower() for name in existing_names}
    quantity_rooms: list[RoomSpec] = []

    for match in QUANTITY_ROOM_PATTERN.finditer(text):
        quantity = int(match.group(1))
        raw_name = _normalize_text(match.group(2))
        if "suite" in raw_name:
            canonical_name = "suite"
        elif "quarto" in raw_name:
            canonical_name = "quarto"
        else:
            canonical_name = "banheiro"

        base_name = _normalize_room_name(canonical_name)
        config = ROOM_LIBRARY[canonical_name]
        width, depth = config["size"]
        detected_level = _section_level_for_match(match.start(), text, floors)

        for index in range(quantity):
            next_name = f"{base_name} {index + 1}" if quantity > 1 else base_name
            if next_name.lower() in existing_lower:
                continue
            room = _build_room(canonical_name, float(width), float(depth), floors, detected_level)
            room.name = next_name
            quantity_rooms.append(room)
            existing_lower.add(next_name.lower())

    return quantity_rooms


def _extract_implicit_rooms(text: str, floors: int, existing_names: list[str]) -> list[RoomSpec]:
    lowered = text.lower()
    existing_lower = {name.lower() for name in existing_names}
    rooms: list[RoomSpec] = []

    for canonical_name, config in ROOM_LIBRARY.items():
        if canonical_name in {"suite", "quarto", "banheiro"}:
            continue
        if any(alias in lowered for alias in config["aliases"]):
            pretty_name = _normalize_room_name(canonical_name)
            if pretty_name.lower() in existing_lower:
                continue
            width, depth = config["size"]
            room = _build_room(canonical_name, float(width), float(depth), floors, 0)
            rooms.append(room)
            existing_lower.add(pretty_name.lower())

    return rooms


def parse_project_from_text(description: str) -> ProjectSpec:
    text = " ".join(str(description or "").strip().split())
    lowered = text.lower()
    project_type = _detect_project_type(lowered)
    floors = _detect_floors(lowered)
    title = f"Projeto beta - {project_type}"

    project_width = 12.0
    project_depth = 8.0
    dimension_match = PROJECT_DIMENSION_PATTERN.search(text)
    if dimension_match:
        project_width = _to_float(dimension_match.group(1))
        project_depth = _to_float(dimension_match.group(2))

    rooms = _extract_explicit_rooms(text, floors)
    existing_names = [room.name for room in rooms]
    rooms.extend(_extract_quantity_rooms(text, floors, existing_names))
    existing_names = [room.name for room in rooms]
    rooms.extend(_extract_implicit_rooms(text, floors, existing_names))

    if not rooms:
        rooms = [
            RoomSpec(name="Sala", width=4.0, depth=5.0, category="social"),
            RoomSpec(name="Cozinha", width=3.0, depth=3.0, category="social"),
            RoomSpec(name="Quarto", width=3.0, depth=3.5, category="private", level=1 if floors > 1 else 0),
            RoomSpec(name="Banheiro", width=2.0, depth=2.0, category="private", level=1 if floors > 1 else 0),
        ]

    return ProjectSpec(
        title=title,
        project_type=project_type,
        floors=floors,
        width=project_width,
        depth=project_depth,
        rooms=rooms,
        notes=text,
    )
