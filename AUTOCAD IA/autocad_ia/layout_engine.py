from __future__ import annotations

from .models import ProjectSpec, RoomSpec


CATEGORY_ORDER = {
    0: ["social", "service", "leisure", "garage", "external", "private"],
    1: ["private", "social", "leisure", "service", "garage", "external"],
}

PRIVATE_TOKENS = ("suite", "quarto", "dormitorio")
BATH_TOKENS = ("banheiro", "wc")
CLOSET_TOKENS = ("closet",)
SOCIAL_TOKENS = ("sala de estar", "sala", "estar", "jantar", "cozinha")


def _default_room_level(room: RoomSpec, floors: int) -> int:
    if floors <= 1:
        return 0
    if room.level:
        return room.level
    if room.category == "private":
        return 1
    return 0


def _normalized_room(room: RoomSpec, floors: int) -> RoomSpec:
    return RoomSpec(
        name=room.name,
        width=room.width,
        depth=room.depth,
        level=_default_room_level(room, floors),
        category=room.category or "social",
        x=room.x,
        y=room.y,
    )


def _has_stair(rooms: list[RoomSpec]) -> bool:
    return any("escada" in room.name.lower() for room in rooms)


def _inject_stairs(project: ProjectSpec, rooms: list[RoomSpec]) -> list[RoomSpec]:
    if project.floors <= 1 or _has_stair(rooms):
        return rooms

    injected = list(rooms)
    for level in range(project.floors):
        injected.append(
            RoomSpec(
                name="Escada",
                width=3.2,
                depth=4.2,
                level=level,
                category="service",
            )
        )
    return injected


def _has_circulation(rooms: list[RoomSpec], level: int) -> bool:
    return any(room.level == level and any(token in room.name.lower() for token in ("hall", "circulacao", "corredor")) for room in rooms)


def _inject_circulation(project: ProjectSpec, rooms: list[RoomSpec]) -> list[RoomSpec]:
    injected = list(rooms)
    for level in range(project.floors):
        private_count = sum(1 for room in injected if room.level == level and _is_private_anchor(room))
        if private_count < 2 or _has_circulation(injected, level):
            continue
        injected.append(
            RoomSpec(
                name="Hall",
                width=2.2,
                depth=4.2,
                level=level,
                category="service",
            )
        )
    return injected


def _is_private_anchor(room: RoomSpec) -> bool:
    lowered = room.name.lower()
    return any(token in lowered for token in PRIVATE_TOKENS)


def _is_bath(room: RoomSpec) -> bool:
    lowered = room.name.lower()
    return any(token in lowered for token in BATH_TOKENS)


def _is_closet(room: RoomSpec) -> bool:
    lowered = room.name.lower()
    return any(token in lowered for token in CLOSET_TOKENS)


def _layout_generic_block(
    project: ProjectSpec,
    rooms: list[RoomSpec],
    start_y: float,
    preferred_start_x: float = 0.0,
) -> tuple[list[RoomSpec], float]:
    gutter = 0.3
    cursor_x = preferred_start_x
    cursor_y = start_y
    row_depth = 0.0
    laid_out: list[RoomSpec] = []

    for room in rooms:
        current = RoomSpec(
            name=room.name,
            width=room.width,
            depth=room.depth,
            level=room.level,
            category=room.category,
            x=room.x,
            y=room.y,
        )
        if cursor_x + current.width > project.width and cursor_x > preferred_start_x:
            cursor_x = 0.0
            cursor_y += row_depth + gutter
            row_depth = 0.0

        current.x = cursor_x
        current.y = cursor_y
        cursor_x += current.width + gutter
        row_depth = max(row_depth, current.depth)
        laid_out.append(current)

    return laid_out, cursor_y + row_depth + gutter


def _social_rank(room: RoomSpec) -> tuple[int, str]:
    lowered = room.name.lower()
    if "sala de estar" in lowered or lowered.startswith("sala"):
        return (0, lowered)
    if "jantar" in lowered:
        return (1, lowered)
    if "cozinha" in lowered:
        return (2, lowered)
    return (3, lowered)


def _layout_social_zone(project: ProjectSpec, rooms: list[RoomSpec], start_y: float, level: int) -> tuple[list[RoomSpec], float]:
    gutter = 0.3
    ordered = sorted(rooms, key=_social_rank)
    anchors = ordered[:3]
    leftovers = ordered[3:]
    if len(anchors) < 3:
        return _layout_generic_block(project, ordered, start_y)

    first, second, third = anchors
    cluster_width = max(first.width + gutter + second.width, first.width + gutter + third.width)
    cluster_depth = max(first.depth, second.depth + gutter + third.depth)
    placed: list[RoomSpec] = []

    x0 = 0.0
    y0 = start_y
    placed.append(RoomSpec(name=first.name, width=first.width, depth=first.depth, level=level, category=first.category, x=x0, y=y0))
    placed.append(RoomSpec(name=second.name, width=second.width, depth=second.depth, level=level, category=second.category, x=x0 + first.width + gutter, y=y0))
    placed.append(RoomSpec(name=third.name, width=third.width, depth=third.depth, level=level, category=third.category, x=x0 + first.width + gutter, y=y0 + second.depth + gutter))

    next_y = y0 + cluster_depth + gutter
    if leftovers:
        extra, next_y = _layout_generic_block(project, leftovers, next_y)
        placed.extend(extra)

    return placed, next_y


def _layout_private_zone(project: ProjectSpec, rooms: list[RoomSpec], start_y: float, level: int) -> tuple[list[RoomSpec], float]:
    gutter = 0.3
    anchors = [room for room in rooms if _is_private_anchor(room)]
    closets = [room for room in rooms if _is_closet(room)]
    baths = [room for room in rooms if _is_bath(room)]
    leftovers = [room for room in rooms if room not in anchors and room not in closets and room not in baths]

    if not anchors:
        return _layout_generic_block(project, rooms, start_y)

    laid_out: list[RoomSpec] = []
    cursor_x = 0.0
    cursor_y = start_y
    row_depth = 0.0

    for anchor in anchors:
        stack: list[RoomSpec] = []
        if closets:
            stack.append(closets.pop(0))
        if baths:
            stack.append(baths.pop(0))

        stack_width = max((room.width for room in stack), default=0.0)
        stack_depth = sum(room.depth for room in stack) + (gutter * max(len(stack) - 1, 0))
        cluster_width = anchor.width + (stack_width + gutter if stack else 0.0)
        cluster_depth = max(anchor.depth, stack_depth)

        if cursor_x + cluster_width > project.width and cursor_x > 0:
            cursor_x = 0.0
            cursor_y += row_depth + gutter
            row_depth = 0.0

        placed_anchor = RoomSpec(
            name=anchor.name,
            width=anchor.width,
            depth=anchor.depth,
            level=level,
            category=anchor.category,
            x=cursor_x,
            y=cursor_y,
        )
        laid_out.append(placed_anchor)

        stack_y = cursor_y
        for room in stack:
            placed_stack = RoomSpec(
                name=room.name,
                width=room.width,
                depth=room.depth,
                level=level,
                category=room.category,
                x=cursor_x + anchor.width + gutter,
                y=stack_y,
            )
            laid_out.append(placed_stack)
            stack_y += room.depth + gutter

        cursor_x += cluster_width + gutter
        row_depth = max(row_depth, cluster_depth)

    next_y = cursor_y + row_depth + gutter
    remainder = leftovers + closets + baths
    if remainder:
        extra, next_y = _layout_generic_block(project, remainder, next_y)
        laid_out.extend(extra)

    return laid_out, next_y


def _layout_level(project: ProjectSpec, rooms: list[RoomSpec], level: int) -> list[RoomSpec]:
    ordered_categories = CATEGORY_ORDER.get(level, CATEGORY_ORDER[0])
    laid_out: list[RoomSpec] = []
    cursor_y = 0.0

    for category in ordered_categories:
        category_rooms = [room for room in rooms if room.category == category]
        if not category_rooms:
            continue

        if category == "private":
            category_layout, cursor_y = _layout_private_zone(project, category_rooms, cursor_y, level)
        elif category == "social":
            category_layout, cursor_y = _layout_social_zone(project, category_rooms, cursor_y, level)
        else:
            preferred_start_x = 0.0
            if category == "service" and any(any(token in room.name.lower() for token in ("escada", "hall", "circulacao", "corredor")) for room in category_rooms):
                preferred_start_x = max((project.width * 0.5) - 1.8, 0.0)
            category_layout, cursor_y = _layout_generic_block(project, category_rooms, cursor_y, preferred_start_x)
        laid_out.extend(category_layout)

    leftovers = [room for room in rooms if room.category not in ordered_categories]
    if leftovers:
        extra_layout, _ = _layout_generic_block(project, leftovers, cursor_y)
        laid_out.extend(extra_layout)

    return laid_out


def layout_project(project: ProjectSpec) -> ProjectSpec:
    if not project.rooms:
        return project

    normalized_rooms = [_normalized_room(room, project.floors) for room in project.rooms]
    normalized_rooms = _inject_stairs(project, normalized_rooms)
    normalized_rooms = _inject_circulation(project, normalized_rooms)

    laid_out_rooms: list[RoomSpec] = []
    max_level = max(project.floors - 1, max(room.level for room in normalized_rooms))
    for level in range(max_level + 1):
        level_rooms = [room for room in normalized_rooms if room.level == level]
        if not level_rooms:
            continue
        laid_out_rooms.extend(_layout_level(project, level_rooms, level))

    project.rooms = laid_out_rooms
    return project
