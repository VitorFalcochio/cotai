from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CompositionItem:
    material: str
    unit: str
    base_factor_per_m2: float
    notes: str = ""


class ParametricBudgetService:
    """Builds first-pass material estimates from area and construction standard.

    This service is intentionally lightweight and transparent. It does not aim
    to replace SINAPI or a full engineering budget yet; instead, it gives Cotai
    a reliable first version of "modo construcao" with:

    - input by text or structured params
    - a clear construction system (`wall`, `floor`, `slab`)
    - a building standard multiplier (`economico`, `medio`, `alto`)
    - a normalized list of base inputs ready for future composition tables
    """

    STANDARD_MULTIPLIERS = {
        "economico": 0.92,
        "medio": 1.0,
        "alto": 1.12,
    }

    SYSTEM_LABELS = {
        "wall": "parede",
        "floor": "piso",
        "slab": "laje",
    }

    COMPOSITIONS: dict[str, tuple[CompositionItem, ...]] = {
        "wall": (
            CompositionItem("Bloco estrutural 14x19x39", "un", 12.5, "Base para vedacao/alvenaria modular."),
            CompositionItem("Argamassa de assentamento", "m3", 0.018, "Consumo medio por metro quadrado."),
            CompositionItem("Cimento CP II 50kg", "saco", 0.11, "Equivalente medio para preparo de argamassa."),
            CompositionItem("Areia media", "m3", 0.038, "Volume base de agregado para assentamento."),
        ),
        "floor": (
            CompositionItem("Piso ceramico", "m2", 1.08, "Ja considera perda tecnica inicial."),
            CompositionItem("Argamassa colante AC-II 20kg", "saco", 0.22, "Base de assentamento para revestimento."),
            CompositionItem("Rejunte 1kg", "un", 0.12, "Consumo medio para juntas padrao."),
            CompositionItem("Regularizacao cimenticia", "m3", 0.015, "Base para contrapiso/regularizacao."),
        ),
        "slab": (
            CompositionItem("Concreto usinado fck 25", "m3", 0.12, "Espessura inicial de referencia."),
            CompositionItem("Aco CA-50", "kg", 3.2, "Armadura media inicial por m2."),
            CompositionItem("Forma compensada plastificada", "m2", 1.05, "Base de forma com perda tecnica."),
            CompositionItem("Cimento CP II 50kg", "saco", 0.84, "Equivalente medio quando nao houver concreto usinado."),
        ),
    }

    def estimate_from_text(self, text: str) -> dict[str, Any]:
        parsed = self.parse_request(text)
        return self.estimate_from_area(
            area_m2=parsed["area_m2"],
            building_standard=parsed["building_standard"],
            system_type=parsed["system_type"],
            raw_text=text,
        )

    def estimate_from_area(
        self,
        *,
        area_m2: float,
        building_standard: str,
        system_type: str | None = None,
        raw_text: str | None = None,
    ) -> dict[str, Any]:
        normalized_system = self._normalize_system(system_type)
        normalized_standard = self._normalize_standard(building_standard)
        if area_m2 <= 0:
            raise ValueError("A area precisa ser maior que zero.")

        composition = self.COMPOSITIONS.get(normalized_system)
        if not composition:
            raise ValueError("Sistema construtivo nao suportado. Use parede, piso ou laje.")

        multiplier = self.STANDARD_MULTIPLIERS[normalized_standard]
        items = []
        for row in composition:
            quantity = self._round_quantity(row.base_factor_per_m2 * area_m2 * multiplier, row.unit)
            items.append(
                {
                    "material": row.material,
                    "quantity": quantity,
                    "unit": row.unit,
                    "display_quantity": f"{quantity} {row.unit}",
                    "notes": row.notes,
                }
            )

        return {
            "mode": "construction",
            "input": {
                "area_m2": round(area_m2, 2),
                "building_standard": normalized_standard,
                "system_type": normalized_system,
                "raw_text": raw_text or "",
            },
            "summary": {
                "title": f"Estimativa inicial para {self.SYSTEM_LABELS[normalized_system]}",
                "subtitle": f"{round(area_m2, 2)} m2 • padrao {normalized_standard}",
                "disclaimer": "Estimativa inicial para estudo e compra preliminar. Validar em projeto executivo e composicoes oficiais.",
            },
            "items": items,
            "future_ready": {
                "sinapi_composition_ready": True,
                "composition_table_key": f"{normalized_system}:{normalized_standard}",
            },
        }

    def parse_request(self, text: str) -> dict[str, Any]:
        area_match = re.search(r"(\d+(?:[.,]\d+)?)\s*m2\b", text or "", flags=re.IGNORECASE)
        if not area_match:
            raise ValueError("Nao identifiquei a area em m2. Exemplo: 120 m2 de piso padrao medio.")

        area_m2 = float(area_match.group(1).replace(",", "."))
        system_type = self._normalize_system(self._infer_system(text))
        building_standard = self._normalize_standard(self._infer_standard(text))
        return {
            "area_m2": area_m2,
            "system_type": system_type,
            "building_standard": building_standard,
        }

    def _infer_system(self, text: str) -> str:
        lowered = str(text or "").lower()
        if "laje" in lowered:
            return "slab"
        if "piso" in lowered or "revestimento" in lowered:
            return "floor"
        return "wall"

    def _infer_standard(self, text: str) -> str:
        lowered = str(text or "").lower()
        if any(token in lowered for token in ("alto padrao", "premium", "alto")):
            return "alto"
        if any(token in lowered for token in ("economico", "popular", "baixo")):
            return "economico"
        return "medio"

    def _normalize_system(self, value: str | None) -> str:
        normalized = str(value or "wall").strip().lower()
        aliases = {
            "parede": "wall",
            "wall": "wall",
            "alvenaria": "wall",
            "piso": "floor",
            "floor": "floor",
            "revestimento": "floor",
            "laje": "slab",
            "slab": "slab",
        }
        return aliases.get(normalized, "wall")

    def _normalize_standard(self, value: str | None) -> str:
        normalized = str(value or "medio").strip().lower()
        aliases = {
            "economico": "economico",
            "baixo": "economico",
            "popular": "economico",
            "medio": "medio",
            "padrao medio": "medio",
            "standard": "medio",
            "alto": "alto",
            "alto padrao": "alto",
            "premium": "alto",
        }
        return aliases.get(normalized, "medio")

    def _round_quantity(self, value: float, unit: str) -> float | int:
        rounded = round(value, 2)
        if unit in {"un", "saco"}:
            return max(1, int(round(rounded)))
        return rounded

