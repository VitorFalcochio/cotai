from __future__ import annotations

from collections import defaultdict

from .models import ProjectSpec, RoomSpec


def _distance(a: RoomSpec, b: RoomSpec) -> float:
    ax = a.x + (a.width / 2)
    ay = a.y + (a.depth / 2)
    bx = b.x + (b.width / 2)
    by = b.y + (b.depth / 2)
    return abs(ax - bx) + abs(ay - by)


def _find_rooms(project: ProjectSpec, predicate) -> list[RoomSpec]:
    return [room for room in project.rooms if predicate(room)]


def _avg_distance(pairs: list[tuple[RoomSpec, RoomSpec]]) -> float:
    if not pairs:
        return 0.0
    return sum(_distance(a, b) for a, b in pairs) / len(pairs)


def _privacy_score(project: ProjectSpec) -> float:
    social = _find_rooms(project, lambda room: room.role in {"living", "dining", "kitchen", "gourmet"})
    private = _find_rooms(project, lambda room: room.role in {"master_suite", "suite", "bedroom"})
    if not social or not private:
        return 6.5
    pairs = [(s, p) for s in social for p in private if s.level == p.level]
    avg = _avg_distance(pairs)
    return min(max(6.0 + (avg * 0.22), 0.0), 10.0)


def _wet_stack_score(project: ProjectSpec) -> float:
    wet = _find_rooms(project, lambda room: room.role in {"bathroom", "powder_room", "service", "kitchen"})
    if len(wet) <= 1:
        return 7.0
    xs = [room.x for room in wet]
    spread = max(xs) - min(xs)
    return max(4.5, min(10.0, 10.0 - (spread * 0.38)))


def _circulation_score(project: ProjectSpec) -> float:
    hubs = _find_rooms(project, lambda room: room.role in {"circulation", "stairs", "family_lounge"})
    anchors = _find_rooms(project, lambda room: room.role in {"living", "kitchen", "master_suite", "suite", "bedroom"})
    if not hubs or not anchors:
        return 6.8
    pairs = [(hub, anchor) for hub in hubs for anchor in anchors if hub.level == anchor.level]
    avg = _avg_distance(pairs)
    return max(4.5, min(10.0, 9.8 - (avg * 0.18)))


def _social_score(project: ProjectSpec) -> float:
    living = _find_rooms(project, lambda room: room.role == "living")
    dining = _find_rooms(project, lambda room: room.role == "dining")
    kitchen = _find_rooms(project, lambda room: room.role == "kitchen")
    pairs: list[tuple[RoomSpec, RoomSpec]] = []
    if living and dining:
        pairs.append((living[0], dining[0]))
    if dining and kitchen:
        pairs.append((dining[0], kitchen[0]))
    if living and kitchen:
        pairs.append((living[0], kitchen[0]))
    if not pairs:
        return 6.0
    avg = _avg_distance(pairs)
    return max(5.0, min(10.0, 9.6 - (avg * 0.22)))


def _constructability_score(project: ProjectSpec) -> float:
    floors = defaultdict(list)
    for room in project.rooms:
        floors[room.level].append(room)

    penalty = 0.0
    for level_rooms in floors.values():
        widths = [room.width for room in level_rooms]
        depths = [room.depth for room in level_rooms]
        if widths and (max(widths) - min(widths)) > project.width * 0.65:
            penalty += 0.6
        if depths and (max(depths) - min(depths)) > project.depth * 0.75:
            penalty += 0.6

    return max(5.0, min(10.0, 8.8 - penalty))


def _rect_overlap(a: RoomSpec, b: RoomSpec) -> float:
    ax1, ay1, ax2, ay2 = a.x, a.y, a.x + a.width, a.y + a.depth
    bx1, by1, bx2, by2 = b.x, b.y, b.x + b.width, b.y + b.depth
    overlap_w = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    overlap_h = max(0.0, min(ay2, by2) - max(ay1, by1))
    return overlap_w * overlap_h


def _layout_integrity_score(project: ProjectSpec) -> float:
    penalty = 0.0
    for index, room in enumerate(project.rooms):
        if room.x < -0.01 or room.y < -0.01:
            penalty += 0.35
        if room.x + room.width > project.width + 0.8:
            penalty += 0.35
        if room.depth <= 0 or room.width <= 0:
            penalty += 0.8

        for other in project.rooms[index + 1:]:
            if room.level != other.level:
                continue
            overlap = _rect_overlap(room, other)
            if overlap > 0.2:
                penalty += min(1.2, overlap * 0.18)

    return max(3.5, min(10.0, 9.5 - penalty))


def score_project(project: ProjectSpec) -> dict[str, float]:
    privacy = round(_privacy_score(project), 1)
    wet_stack = round(_wet_stack_score(project), 1)
    circulation = round(_circulation_score(project), 1)
    social = round(_social_score(project), 1)
    constructability = round(_constructability_score(project), 1)
    layout_integrity = round(_layout_integrity_score(project), 1)
    overall = round((privacy + wet_stack + circulation + social + constructability + layout_integrity) / 6, 1)

    return {
        "privacy_score": privacy,
        "wet_stack_score": wet_stack,
        "circulation_score": circulation,
        "social_score": social,
        "constructability_score": constructability,
        "layout_integrity_score": layout_integrity,
        "overall_score": overall,
    }
