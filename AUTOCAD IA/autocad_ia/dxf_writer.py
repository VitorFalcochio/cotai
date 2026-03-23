from __future__ import annotations

from pathlib import Path

from .models import ProjectSpec, RoomSpec


def _line(start: tuple[float, float], end: tuple[float, float], layer: str = "0", color: int | None = None) -> str:
    color_section = f"62\n{color}\n" if color is not None else ""
    return (
        "0\nLINE\n8\n"
        f"{layer}\n"
        f"{color_section}"
        f"10\n{start[0]:.3f}\n20\n{start[1]:.3f}\n30\n0.0\n"
        f"11\n{end[0]:.3f}\n21\n{end[1]:.3f}\n31\n0.0\n"
    )


def _text(
    value: str,
    insert: tuple[float, float],
    height: float = 0.22,
    layer: str = "TEXT",
    color: int | None = None,
) -> str:
    safe_value = str(value or "").replace("\n", " ").strip() or "Sem titulo"
    color_section = f"62\n{color}\n" if color is not None else ""
    return (
        "0\nTEXT\n8\n"
        f"{layer}\n"
        f"{color_section}"
        f"10\n{insert[0]:.3f}\n20\n{insert[1]:.3f}\n30\n0.0\n"
        f"40\n{height:.3f}\n1\n{safe_value}\n"
    )


def _arc(
    center: tuple[float, float],
    radius: float,
    start_angle: float,
    end_angle: float,
    layer: str = "DOORS",
    color: int | None = None,
) -> str:
    color_section = f"62\n{color}\n" if color is not None else ""
    return (
        "0\nARC\n8\n"
        f"{layer}\n"
        f"{color_section}"
        f"10\n{center[0]:.3f}\n20\n{center[1]:.3f}\n30\n0.0\n"
        f"40\n{radius:.3f}\n50\n{start_angle:.3f}\n51\n{end_angle:.3f}\n"
    )


def _circle(center: tuple[float, float], radius: float, layer: str = "FURNITURE", color: int | None = None) -> str:
    color_section = f"62\n{color}\n" if color is not None else ""
    return (
        "0\nCIRCLE\n8\n"
        f"{layer}\n"
        f"{color_section}"
        f"10\n{center[0]:.3f}\n20\n{center[1]:.3f}\n30\n0.0\n"
        f"40\n{radius:.3f}\n"
    )


def _room_bounds(room: RoomSpec, level_y_offset: float) -> tuple[float, float, float, float]:
    x = room.x
    y = room.y + level_y_offset
    return x, y, x + room.width, y + room.depth


def _wall_entities(room: RoomSpec, project: ProjectSpec, level_y_offset: float) -> list[str]:
    x1, y1, x2, y2 = _room_bounds(room, level_y_offset)
    t = max(project.wall_thickness, 0.12)
    inset = max(t * 0.45, 0.06)

    return [
        _line((x1, y1), (x2, y1), "WALLS", 7),
        _line((x2, y1), (x2, y2), "WALLS", 7),
        _line((x2, y2), (x1, y2), "WALLS", 7),
        _line((x1, y2), (x1, y1), "WALLS", 7),
        _line((x1 + inset, y1 + inset), (x2 - inset, y1 + inset), "WALLS_INNER", 8),
        _line((x2 - inset, y1 + inset), (x2 - inset, y2 - inset), "WALLS_INNER", 8),
        _line((x2 - inset, y2 - inset), (x1 + inset, y2 - inset), "WALLS_INNER", 8),
        _line((x1 + inset, y2 - inset), (x1 + inset, y1 + inset), "WALLS_INNER", 8),
    ]


def _door_entities(room: RoomSpec, level_y_offset: float) -> list[str]:
    x1, _, x2, y2 = _room_bounds(room, level_y_offset)
    door_width = min(0.9, max(0.75, room.width * 0.24))
    hinge_x = x1 + ((x2 - x1) / 2) - (door_width / 2)
    hinge_y = y2
    return [
        _line((hinge_x, hinge_y), (hinge_x + door_width, hinge_y), "DOORS", 1),
        _arc((hinge_x, hinge_y), door_width, 0, 90, "DOORS", 6),
    ]


def _window_entities(room: RoomSpec, project: ProjectSpec, level_y_offset: float) -> list[str]:
    x1, y1, x2, y2 = _room_bounds(room, level_y_offset)
    span = min(1.4, max(0.9, room.width * 0.28))
    wall_mid_x = x1 + ((x2 - x1) / 2)
    wall_mid_y = y1 + ((y2 - y1) / 2)
    offset = max(project.wall_thickness * 0.22, 0.05)

    entities: list[str] = []
    if room.category in {"external", "leisure", "garage"} or y1 <= level_y_offset + 0.01:
        entities.append(_line((wall_mid_x - span / 2, y1 + offset), (wall_mid_x + span / 2, y1 + offset), "WINDOWS", 5))
    if room.category in {"private", "social"} and x2 >= project.width - 0.01:
        entities.append(_line((x2 - offset, wall_mid_y - span / 2), (x2 - offset, wall_mid_y + span / 2), "WINDOWS", 5))
    if room.category in {"social", "leisure"} and y2 >= level_y_offset + project.depth - 0.75:
        entities.append(_line((wall_mid_x - span / 2, y2 - offset), (wall_mid_x + span / 2, y2 - offset), "WINDOWS", 5))
    return entities


def _stair_entities(room: RoomSpec, level_y_offset: float) -> list[str]:
    if "escada" not in room.name.lower():
        return []

    x1, y1, x2, y2 = _room_bounds(room, level_y_offset)
    width = x2 - x1
    steps = max(int(room.depth / 0.28), 8)
    tread = (y2 - y1) / steps
    entities = [
        _line((x1 + 0.16, y1 + 0.18), (x2 - 0.16, y1 + 0.18), "STAIRS", 4),
        _line((x1 + 0.16, y2 - 0.18), (x2 - 0.16, y2 - 0.18), "STAIRS", 4),
    ]
    for index in range(1, steps):
        y = y1 + (index * tread)
        entities.append(_line((x1 + 0.16, y), (x2 - 0.16, y), "STAIRS", 4))
    entities.append(_text("UP", (x1 + (width * 0.34), y1 + ((y2 - y1) * 0.5)), 0.18, "STAIRS", 1))
    return entities


def _fixture_entities(room: RoomSpec, level_y_offset: float) -> list[str]:
    lowered = room.name.lower()
    x1, y1, x2, y2 = _room_bounds(room, level_y_offset)
    cx = x1 + ((x2 - x1) / 2)
    cy = y1 + ((y2 - y1) / 2)
    entities: list[str] = []

    if "banheiro" in lowered or "wc" in lowered or "lavabo" in lowered:
        entities.append(_circle((x1 + 0.45, y1 + 0.45), 0.18, "FIXTURES", 2))
        entities.append(_line((x2 - 0.75, y1 + 0.35), (x2 - 0.25, y1 + 0.35), "FIXTURES", 4))
        entities.append(_line((x2 - 0.25, y1 + 0.35), (x2 - 0.25, y1 + 0.85), "FIXTURES", 4))
        entities.append(_line((x2 - 0.25, y1 + 0.85), (x2 - 0.75, y1 + 0.85), "FIXTURES", 4))
        entities.append(_line((x2 - 0.75, y1 + 0.85), (x2 - 0.75, y1 + 0.35), "FIXTURES", 4))
    elif "cozinha" in lowered:
        entities.append(_line((x1 + 0.3, y1 + 0.35), (x2 - 0.3, y1 + 0.35), "FIXTURES", 3))
        entities.append(_line((x1 + 0.3, y1 + 0.85), (x2 - 0.3, y1 + 0.85), "FIXTURES", 3))
        entities.append(_circle((cx, y1 + 0.58), 0.12, "FIXTURES", 1))
    elif "hall" in lowered or "circulacao" in lowered or "corredor" in lowered:
        entities.append(_text("CIRC", (cx - 0.45, cy), 0.16, "TEXT", 5))

    return entities


def _room_text_entities(room: RoomSpec, level_y_offset: float) -> list[str]:
    center_x = room.x + (room.width / 2)
    center_y = room.y + level_y_offset + (room.depth / 2)
    return [
        _text(room.name, (center_x - (room.width * 0.18), center_y + 0.1), 0.22, "TEXT", 2),
        _text(f"{room.width:.2f} x {room.depth:.2f} m", (center_x - (room.width * 0.2), center_y - 0.2), 0.14, "TEXT", 8),
    ]


def _level_header(level: int, y_offset: float, title: str) -> list[str]:
    label = "TERREO" if level == 0 else f"PAVIMENTO {level + 1}"
    return [
        _text(f"{title} - {label}", (0.0, y_offset - 0.9), 0.32, "TEXT", 3),
        _line((-0.4, y_offset - 0.55), (16.0, y_offset - 0.55), "GUIDES", 9),
    ]


def write_project_dxf(project: ProjectSpec, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    entities: list[str] = []
    entities.append(_text(project.title, (0.0, -1.6), 0.38, "TEXT", 2))
    entities.append(_text(f"Tipo: {project.project_type} | Pavimentos: {project.floors}", (0.0, -1.1), 0.2, "TEXT", 8))

    max_level = max((room.level for room in project.rooms), default=0)
    level_height = project.depth + 4.5

    for level in range(max_level + 1):
        level_rooms = [room for room in project.rooms if room.level == level]
        if not level_rooms:
            continue

        y_offset = level * level_height
        entities.extend(_level_header(level, y_offset, project.title))
        entities.append(_line((0.0, y_offset), (project.width, y_offset), "PLOT", 8))
        entities.append(_line((project.width, y_offset), (project.width, y_offset + project.depth), "PLOT", 8))
        entities.append(_line((project.width, y_offset + project.depth), (0.0, y_offset + project.depth), "PLOT", 8))
        entities.append(_line((0.0, y_offset + project.depth), (0.0, y_offset), "PLOT", 8))

        for room in level_rooms:
            entities.extend(_wall_entities(room, project, y_offset))
            entities.extend(_door_entities(room, y_offset))
            entities.extend(_window_entities(room, project, y_offset))
            entities.extend(_stair_entities(room, y_offset))
            entities.extend(_fixture_entities(room, y_offset))
            entities.extend(_room_text_entities(room, y_offset))

    dxf = "".join(
        [
            "0\nSECTION\n2\nHEADER\n0\nENDSEC\n",
            "0\nSECTION\n2\nTABLES\n0\nENDSEC\n",
            "0\nSECTION\n2\nENTITIES\n",
            *entities,
            "0\nENDSEC\n0\nEOF\n",
        ]
    )
    output_path.write_text(dxf, encoding="utf-8")
    return output_path
