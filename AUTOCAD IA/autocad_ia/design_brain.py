from __future__ import annotations

from dataclasses import replace

from .models import ProjectSpec, RoomSpec


FRONT_ANCHOR_TOKENS = ("garagem", "hall", "entrada", "escritorio")
SOCIAL_TOKENS = ("sala", "jantar", "cozinha", "gourmet", "varanda")
WET_TOKENS = ("banheiro", "lavabo", "wc", "lavanderia", "area de servico", "cozinha")
PRIVATE_TOKENS = ("suite", "quarto", "dormitorio", "closet")
OUTDOOR_TOKENS = ("piscina", "jardim", "quintal", "varanda")


def _room_role(room: RoomSpec) -> str:
    lowered = room.name.lower()
    if "suite master" in lowered:
        return "master_suite"
    if "suite" in lowered:
        return "suite"
    if any(token in lowered for token in ("quarto", "dormitorio")):
        return "bedroom"
    if "closet" in lowered:
        return "closet"
    if any(token in lowered for token in ("banheiro", "wc")):
        return "bathroom"
    if "lavabo" in lowered:
        return "powder_room"
    if "cozinha" in lowered:
        return "kitchen"
    if "jantar" in lowered:
        return "dining"
    if "sala intima" in lowered:
        return "family_lounge"
    if "sala" in lowered:
        return "living"
    if "escada" in lowered:
        return "stairs"
    if any(token in lowered for token in ("hall", "corredor", "circulacao")):
        return "circulation"
    if "garagem" in lowered:
        return "garage"
    if "lavanderia" in lowered or "servico" in lowered:
        return "service"
    if "gourmet" in lowered:
        return "gourmet"
    if "varanda" in lowered:
        return "veranda"
    if "piscina" in lowered:
        return "pool"
    if "escritorio" in lowered:
        return "office"
    return room.category or "room"


def _room_zone(room: RoomSpec, floors: int) -> str:
    lowered = room.name.lower()
    if room.level > 0 and any(token in lowered for token in PRIVATE_TOKENS + ("hall", "escada", "wc", "banheiro")):
        return "upper_private"
    if any(token in lowered for token in FRONT_ANCHOR_TOKENS):
        return "front"
    if any(token in lowered for token in OUTDOOR_TOKENS):
        return "outdoor"
    if any(token in lowered for token in SOCIAL_TOKENS):
        return "social_core"
    if any(token in lowered for token in WET_TOKENS):
        return "wet_core"
    if any(token in lowered for token in PRIVATE_TOKENS):
        return "private_wing"
    if floors > 1 and room.level == 1:
        return "upper_private"
    return "service_band"


def _cluster_name(room: RoomSpec) -> str:
    lowered = room.name.lower()
    if "suite master" in lowered:
        return "master"
    if any(token in lowered for token in ("suite", "quarto", "dormitorio", "closet")):
        return "private"
    if any(token in lowered for token in ("banheiro", "wc", "lavabo", "lavanderia", "servico")):
        return "wet"
    if any(token in lowered for token in ("sala", "jantar", "cozinha", "gourmet")):
        return "social"
    if any(token in lowered for token in ("garagem", "hall", "entrada", "escada", "corredor", "circulacao")):
        return "access"
    return room.category or "generic"


def _adjacency_targets(room: RoomSpec) -> list[str]:
    role = room.role or _room_role(room)
    if role == "living":
        return ["Sala de Jantar", "Cozinha", "Varanda"]
    if role == "dining":
        return ["Sala de Estar", "Cozinha"]
    if role == "kitchen":
        return ["Sala de Jantar", "Area de Servico", "Espaco Gourmet"]
    if role == "service":
        return ["Cozinha", "Garagem"]
    if role == "garage":
        return ["Hall", "Area de Servico"]
    if role == "master_suite":
        return ["Closet", "Banheiro", "Sala Intima"]
    if role == "suite":
        return ["Banheiro", "Hall"]
    if role == "bedroom":
        return ["Hall", "Banheiro"]
    if role == "closet":
        return ["Suite Master", "Suite", "Banheiro"]
    if role == "bathroom":
        return ["Suite", "Quarto", "Hall"]
    if role == "family_lounge":
        return ["Escada", "Suite", "Quarto"]
    if role in {"stairs", "circulation"}:
        return ["Hall", "Sala Intima", "Sala de Estar"]
    if role in {"veranda", "gourmet", "pool"}:
        return ["Sala de Estar", "Cozinha", "Espaco Gourmet"]
    return []


def _project_strategy(project: ProjectSpec) -> tuple[str, list[str]]:
    notes: list[str] = []
    if project.floors > 1:
        notes.append("Projeto multi-pavimento com setor intimo elevado.")
    if any(room.role == "garage" for room in project.rooms):
        notes.append("Garagem posicionada como ancora frontal de acesso.")
    if any(room.role in {"pool", "veranda", "gourmet"} for room in project.rooms):
        notes.append("Area de lazer conectada ao nucleo social.")
    if any(room.role == "master_suite" for room in project.rooms):
        notes.append("Suite master tratada como conjunto privativo com apoio molhado.")

    if project.width <= 10:
        strategy = "lote_estreito_linear"
        notes.append("Terreno estreito: priorizar eixo central de circulacao e integracao social.")
    elif project.width >= 18:
        strategy = "casa_espraiada_setorizada"
        notes.append("Terreno largo: distribuir programa em alas com patios e respiros.")
    elif project.floors > 1:
        strategy = "sobrado_setorizado"
        notes.append("Sobrado: base social/servico no terreo e setor intimo no pavimento superior.")
    else:
        strategy = "casa_compacta_integrada"
        notes.append("Casa terrea compacta com zona social central.")

    return strategy, notes


def _spatial_constraints(project: ProjectSpec) -> dict[str, float | str | bool]:
    corridor_width = 1.35 if project.floors > 1 else 1.2
    stair_width = 2.6 if project.width >= 12 else 2.2
    hall_depth = 3.6 if project.floors > 1 else 2.8

    if project.width >= 18:
        corridor_width = 1.5
        stair_width = 3.0
        hall_depth = 4.0
    elif project.width <= 10:
        corridor_width = 1.1
        stair_width = 2.0
        hall_depth = 2.4

    return {
        "corridor_width": corridor_width,
        "stair_width_target": stair_width,
        "hall_depth_target": hall_depth,
        "core_axis_mode": "central",
        "private_access_mode": "spine",
        "facade_mass_mode": "stepped" if project.width >= 12 else "compact",
    }


def enrich_project(project: ProjectSpec) -> ProjectSpec:
    enriched_rooms: list[RoomSpec] = []
    for room in project.rooms:
        role = room.role or _room_role(room)
        zone = room.zone or _room_zone(room, project.floors)
        cluster = room.cluster or _cluster_name(room)
        adjacency = room.adjacency or _adjacency_targets(replace(room, role=role))
        enriched_rooms.append(
            replace(
                room,
                role=role,
                zone=zone,
                cluster=cluster,
                adjacency=adjacency,
            )
        )

    enriched = replace(project, rooms=enriched_rooms)
    strategy, notes = _project_strategy(enriched)
    enriched.design_strategy = strategy
    enriched.processing_notes = notes
    base_constraints = dict(project.constraints or {})
    base_constraints.update({
        "max_floor_plate_area": round(project.width * project.depth, 2),
        "requires_circulation_core": project.floors > 1 or len(enriched_rooms) >= 7,
        "needs_wet_stack_alignment": any(room.role in {"bathroom", "powder_room", "service"} for room in enriched_rooms),
    })
    base_constraints.update(_spatial_constraints(project))
    enriched.constraints = base_constraints
    return enriched
