from __future__ import annotations

from dataclasses import replace

from .models import ProjectSpec, RoomSpec


GUTTER = 0.3


def _default_room_level(room: RoomSpec, floors: int) -> int:
    if floors <= 1:
        return 0
    if room.level:
        return room.level
    if room.category == "private":
        return 1
    return 0


def _normalized_room(room: RoomSpec, floors: int) -> RoomSpec:
    return replace(room, level=_default_room_level(room, floors))


def _role(room: RoomSpec) -> str:
    return (room.role or room.category or "").lower()


def _is_named(room: RoomSpec, *tokens: str) -> bool:
    lowered = room.name.lower()
    return any(token in lowered for token in tokens)


def _make_room(name: str, width: float, depth: float, level: int, category: str, zone: str, role: str, cluster: str) -> RoomSpec:
    return RoomSpec(
        name=name,
        width=width,
        depth=depth,
        level=level,
        category=category,
        zone=zone,
        role=role,
        cluster=cluster,
    )


def _has_room(rooms: list[RoomSpec], token: str, level: int | None = None) -> bool:
    return any(token in room.name.lower() and (level is None or room.level == level) for room in rooms)


def _inject_vertical_core(project: ProjectSpec, rooms: list[RoomSpec]) -> list[RoomSpec]:
    injected = list(rooms)
    if project.floors > 1:
        for level in range(project.floors):
            if not _has_room(injected, "escada", level):
                injected.append(_make_room("Escada", 3.1, 4.0, level, "service", "core", "stairs", "access"))
        if not _has_room(injected, "hall", 1):
            injected.append(_make_room("Sala Intima", 4.4, 3.8, 1, "social", "upper_private", "family_lounge", "private"))

    for level in range(project.floors):
        if not _has_room(injected, "hall", level) and not _has_room(injected, "circul", level):
            hall_name = "Hall" if level == 0 else "Hall Intimo"
            injected.append(_make_room(hall_name, 2.2, 4.2, level, "service", "core", "circulation", "access"))

    return injected


def _clone_at(room: RoomSpec, x: float, y: float) -> RoomSpec:
    return replace(room, x=round(x, 3), y=round(y, 3))


def _split_rooms(rooms: list[RoomSpec], predicate) -> tuple[list[RoomSpec], list[RoomSpec]]:
    selected: list[RoomSpec] = []
    leftover: list[RoomSpec] = []
    for room in rooms:
        (selected if predicate(room) else leftover).append(room)
    return selected, leftover


def _sort_front_band(rooms: list[RoomSpec]) -> list[RoomSpec]:
    order = {"garage": 0, "office": 1, "circulation": 2, "stairs": 3}
    return sorted(rooms, key=lambda room: (order.get(_role(room), 8), room.name.lower()))


def _sort_social(rooms: list[RoomSpec]) -> list[RoomSpec]:
    order = {"living": 0, "dining": 1, "kitchen": 2, "gourmet": 3, "veranda": 4}
    return sorted(rooms, key=lambda room: (order.get(_role(room), 9), room.name.lower()))


def _sort_private(rooms: list[RoomSpec]) -> list[RoomSpec]:
    order = {"master_suite": 0, "suite": 1, "bedroom": 2, "closet": 3, "bathroom": 4}
    return sorted(rooms, key=lambda room: (order.get(_role(room), 9), room.name.lower()))


def _layout_row(rooms: list[RoomSpec], y: float, max_width: float, start_x: float = 0.0) -> tuple[list[RoomSpec], float]:
    cursor_x = start_x
    row_depth = 0.0
    laid_out: list[RoomSpec] = []
    for room in rooms:
        if cursor_x + room.width > max_width and cursor_x > start_x:
            break
        laid_out.append(_clone_at(room, cursor_x, y))
        cursor_x += room.width + GUTTER
        row_depth = max(row_depth, room.depth)
    return laid_out, y + row_depth + GUTTER


def _layout_grid(rooms: list[RoomSpec], y: float, max_width: float, start_x: float = 0.0) -> tuple[list[RoomSpec], float]:
    cursor_x = start_x
    cursor_y = y
    row_depth = 0.0
    laid_out: list[RoomSpec] = []
    for room in rooms:
        if cursor_x + room.width > max_width and cursor_x > start_x:
            cursor_x = start_x
            cursor_y += row_depth + GUTTER
            row_depth = 0.0
        laid_out.append(_clone_at(room, cursor_x, cursor_y))
        cursor_x += room.width + GUTTER
        row_depth = max(row_depth, room.depth)
    return laid_out, cursor_y + row_depth + GUTTER


def _layout_social_core(project: ProjectSpec, rooms: list[RoomSpec], start_y: float, level: int) -> tuple[list[RoomSpec], float]:
    social = _sort_social(rooms)
    if not social:
        return [], start_y

    living = next((room for room in social if _role(room) == "living"), None)
    dining = next((room for room in social if _role(room) == "dining"), None)
    kitchen = next((room for room in social if _role(room) == "kitchen"), None)
    anchors = [item for item in (living, dining, kitchen) if item is not None]
    others = [room for room in social if room not in anchors]
    placed: list[RoomSpec] = []

    if living and dining and kitchen:
        living_x = 0.0
        dining_x = living.width + GUTTER
        kitchen_x = dining_x + dining.width + GUTTER

        placed.append(_clone_at(living, living_x, start_y))
        placed.append(_clone_at(dining, dining_x, start_y))
        placed.append(_clone_at(kitchen, kitchen_x, start_y))
        next_y = start_y + max(living.depth, dining.depth, kitchen.depth) + GUTTER
    else:
        placed, next_y = _layout_grid(social, start_y, project.width)
        others = []

    if others:
        extra, next_y = _layout_grid(others, next_y, project.width)
        placed.extend(extra)

    return placed, next_y


def _pair_private_groups(rooms: list[RoomSpec]) -> list[list[RoomSpec]]:
    anchors = [room for room in rooms if _role(room) in {"master_suite", "suite", "bedroom"}]
    closets = [room for room in rooms if _role(room) == "closet"]
    baths = [room for room in rooms if _role(room) in {"bathroom", "powder_room"}]
    family_lounges = [room for room in rooms if _role(room) == "family_lounge"]
    circulation = [room for room in rooms if _role(room) == "circulation"]
    others = [room for room in rooms if room not in anchors + closets + baths + family_lounges + circulation]

    groups: list[list[RoomSpec]] = []
    if family_lounges:
        groups.append(family_lounges[:1])
    if circulation:
        groups.append(circulation[:1])

    for anchor in _sort_private(anchors):
        group = [anchor]
        if closets:
            group.append(closets.pop(0))
        if baths:
            group.append(baths.pop(0))
        groups.append(group)

    for bath in baths:
        groups.append([bath])
    for room in others:
        groups.append([room])

    return groups


def _layout_upper_private(project: ProjectSpec, rooms: list[RoomSpec], start_y: float, level: int) -> tuple[list[RoomSpec], float]:
    groups = _pair_private_groups(rooms)
    if not groups:
        return [], start_y

    laid_out: list[RoomSpec] = []
    center_x = max((project.width * 0.5) - 1.6, 0.0)
    top_y = start_y

    core_groups = [group for group in groups if any(_role(room) in {"family_lounge", "circulation", "stairs"} for room in group)]
    private_groups = [group for group in groups if group not in core_groups]

    for group in core_groups:
        cursor_y = top_y
        for room in group:
            width = min(room.width, max(project.width * 0.34, 2.2))
            laid_out.append(_clone_at(replace(room, width=width), center_x, cursor_y))
            cursor_y += room.depth + GUTTER
        top_y = max(top_y, cursor_y)

    left_x = 0.0
    right_x = min(project.width * 0.58, project.width - 4.8)
    left_y = top_y
    right_y = top_y

    for index, group in enumerate(private_groups):
        anchor = group[0]
        stack = group[1:]
        place_left = index % 2 == 0
        base_x = left_x if place_left else right_x
        base_y = left_y if place_left else right_y

        max_stack_width = max((room.width for room in stack), default=0.0)
        cluster_width = anchor.width + (GUTTER + max_stack_width if stack else 0.0)
        if not place_left:
            base_x = max(project.width - cluster_width, right_x)

        laid_out.append(_clone_at(anchor, base_x, base_y))
        stack_y = base_y
        for room in stack:
            laid_out.append(_clone_at(room, base_x + anchor.width + GUTTER, stack_y))
            stack_y += room.depth + GUTTER

        cluster_depth = max(anchor.depth, stack_y - base_y - (GUTTER if stack else 0.0))
        if place_left:
            left_y += cluster_depth + GUTTER
        else:
            right_y += cluster_depth + GUTTER

    next_y = max(left_y, right_y, top_y) + GUTTER
    return laid_out, next_y


def _layout_ground_private(project: ProjectSpec, rooms: list[RoomSpec], start_y: float, level: int) -> tuple[list[RoomSpec], float]:
    groups = _pair_private_groups(rooms)
    laid_out: list[RoomSpec] = []
    cursor_y = start_y
    for group in groups:
        anchor = group[0]
        stack = group[1:]
        laid_out.append(_clone_at(anchor, 0.0, cursor_y))
        stack_y = cursor_y
        for room in stack:
            laid_out.append(_clone_at(room, anchor.width + GUTTER, stack_y))
            stack_y += room.depth + GUTTER
        cursor_y += max(anchor.depth, stack_y - cursor_y - (GUTTER if stack else 0.0)) + GUTTER
    return laid_out, cursor_y


def _layout_service_band(project: ProjectSpec, rooms: list[RoomSpec], start_y: float, start_x: float = 0.0) -> tuple[list[RoomSpec], float]:
    ordered = sorted(rooms, key=lambda room: (_role(room), room.name.lower()))
    return _layout_grid(ordered, start_y, project.width, start_x=start_x)


def _layout_outdoor_band(project: ProjectSpec, rooms: list[RoomSpec], start_y: float) -> tuple[list[RoomSpec], float]:
    outdoor = sorted(rooms, key=lambda room: (_role(room), room.name.lower()))
    return _layout_grid(outdoor, start_y, project.width)


def _align_level_geometry(project: ProjectSpec, rooms: list[RoomSpec], level: int) -> list[RoomSpec]:
    if not rooms:
        return rooms

    center_axis = project.width * 0.5
    wet_stack_x = min(max(center_axis + 1.2, 0.0), max(project.width - 3.4, 0.0))
    adjusted: list[RoomSpec] = []

    for room in rooms:
        updated = room
        role = _role(room)

        if role in {"stairs", "circulation", "family_lounge"}:
            updated = replace(updated, x=round(max(center_axis - (room.width / 2), 0.0), 3))

        if role in {"bathroom", "powder_room", "service"}:
            updated = replace(updated, x=round(max(updated.x, wet_stack_x), 3))

        if level == 0 and role == "garage":
            updated = replace(updated, x=0.0, y=0.0)

        if level == 0 and role in {"pool", "veranda", "gourmet"}:
            updated = replace(updated, y=round(max(updated.y, project.depth - updated.depth - 0.6), 3))

        adjusted.append(updated)

    return adjusted


def _layout_level(project: ProjectSpec, rooms: list[RoomSpec], level: int) -> list[RoomSpec]:
    if not rooms:
        return []

    front_band, remainder = _split_rooms(rooms, lambda room: room.zone == "front" or _role(room) in {"garage", "office"})
    core_band, remainder = _split_rooms(remainder, lambda room: room.zone == "social_core" and _role(room) not in {"family_lounge"})
    outdoor_band, remainder = _split_rooms(remainder, lambda room: room.zone == "outdoor")
    private_band, remainder = _split_rooms(remainder, lambda room: room.category == "private" or room.zone in {"private_wing", "upper_private"} or _role(room) in {"family_lounge"})
    service_band = remainder

    laid_out: list[RoomSpec] = []
    cursor_y = 0.0

    if level == 0 and front_band:
        placed, cursor_y = _layout_row(_sort_front_band(front_band), cursor_y, project.width)
        laid_out.extend(placed)

    if core_band:
        placed, cursor_y = _layout_social_core(project, core_band, cursor_y, level)
        laid_out.extend(placed)

    if service_band:
        service_start_x = max(project.width * 0.52, 0.0) if any(_role(room) in {"service", "bathroom", "powder_room"} for room in service_band) else 0.0
        placed, cursor_y = _layout_service_band(project, service_band, cursor_y, start_x=min(service_start_x, max(project.width - 3.5, 0.0)))
        laid_out.extend(placed)

    if private_band:
        if level > 0:
            placed, cursor_y = _layout_upper_private(project, private_band, cursor_y, level)
        else:
            placed, cursor_y = _layout_ground_private(project, private_band, cursor_y, level)
        laid_out.extend(placed)

    if level == 0 and outdoor_band:
        placed, cursor_y = _layout_outdoor_band(project, outdoor_band, cursor_y)
        laid_out.extend(placed)

    return _align_level_geometry(project, laid_out, level)


def layout_project(project: ProjectSpec) -> ProjectSpec:
    if not project.rooms:
        return project

    normalized_rooms = [_normalized_room(room, project.floors) for room in project.rooms]
    normalized_rooms = _inject_vertical_core(project, normalized_rooms)

    laid_out_rooms: list[RoomSpec] = []
    max_level = max(project.floors - 1, max(room.level for room in normalized_rooms))
    for level in range(max_level + 1):
        level_rooms = [room for room in normalized_rooms if room.level == level]
        laid_out_rooms.extend(_layout_level(project, level_rooms, level))

    project.rooms = laid_out_rooms
    return project
