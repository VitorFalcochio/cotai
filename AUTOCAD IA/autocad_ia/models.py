from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RoomSpec:
    name: str
    width: float
    depth: float
    level: int = 0
    category: str = "social"
    x: float = 0.0
    y: float = 0.0

    @property
    def area(self) -> float:
        return round(self.width * self.depth, 2)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RoomSpec":
        return cls(
            name=str(payload.get("name", "Ambiente")).strip() or "Ambiente",
            width=float(payload.get("width", 3.0)),
            depth=float(payload.get("depth", 3.0)),
            level=int(payload.get("level", 0) or 0),
            category=str(payload.get("category", "social")).strip() or "social",
            x=float(payload.get("x", 0.0)),
            y=float(payload.get("y", 0.0)),
        )


@dataclass
class ProjectSpec:
    title: str
    project_type: str = "residencial"
    floors: int = 1
    width: float = 12.0
    depth: float = 8.0
    wall_thickness: float = 0.15
    rooms: list[RoomSpec] = field(default_factory=list)
    notes: str = ""

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ProjectSpec":
        rooms = [RoomSpec.from_dict(item) for item in payload.get("rooms", [])]
        return cls(
            title=str(payload.get("title", "Projeto Beta")).strip() or "Projeto Beta",
            project_type=str(payload.get("project_type", "residencial")).strip() or "residencial",
            floors=int(payload.get("floors", 1) or 1),
            width=float(payload.get("width", 12.0)),
            depth=float(payload.get("depth", 8.0)),
            wall_thickness=float(payload.get("wall_thickness", 0.15)),
            rooms=rooms,
            notes=str(payload.get("notes", "")).strip(),
        )
