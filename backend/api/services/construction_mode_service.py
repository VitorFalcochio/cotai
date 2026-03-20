from __future__ import annotations

import re
from statistics import mean
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ...worker.config import Settings
from ...worker.services.search_service import SearchService


class ConstructionMaterialPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material: str
    quantity: float | int
    unit: str
    notes: str
    unit_price_cents: int | None = None
    unit_price_display: str | None = None
    estimated_total_cents: int | None = None
    estimated_total_display: str | None = None
    pricing_source: str | None = None
    pricing_status: str


class ConstructionPhasePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    title: str
    share_label: str
    materials: list[ConstructionMaterialPayload]
    estimated_cost_cents: int | None = None
    estimated_cost_display: str | None = None
    priced_materials: int = Field(ge=0)
    missing_price_materials: int = Field(ge=0)


class ConstructionProjectPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: str
    status: str
    project: dict[str, Any]
    assumptions: list[str]
    next_questions: list[str]
    phases: list[ConstructionPhasePayload]
    procurement_items: list[ConstructionMaterialPayload]
    summary: dict[str, Any]
    conversation: dict[str, Any]
    missing_fields: list[str] = Field(default_factory=list)
    message: str


class ConstructionModeService:
    SAFETY_MARGIN_MULTIPLIER = 1.10
    MAX_REASONABLE_AREA_M2 = 1_000_000.0

    PROJECT_TYPE_LABELS = {
        "house": "casa",
        "townhouse": "sobrado",
        "warehouse": "galpao",
        "commercial": "obra comercial",
    }

    STANDARD_MULTIPLIERS = {
        "economico": 0.93,
        "medio": 1.0,
        "alto": 1.14,
    }

    PHASE_LIBRARY: dict[str, tuple[dict[str, Any], ...]] = {
        "foundation": (
            {"material": "Concreto usinado fck 25", "unit": "m3", "factor": 0.11, "notes": "Base preliminar para fundacao e baldrame."},
            {"material": "Aco CA-50", "unit": "kg", "factor": 4.2, "notes": "Armadura inicial de fundacao."},
            {"material": "Brita 1", "unit": "m3", "factor": 0.08, "notes": "Agregado base para concreto e regularizacao."},
            {"material": "Areia media", "unit": "m3", "factor": 0.09, "notes": "Consumo preliminar para concreto e argamassa."},
        ),
        "structure": (
            {"material": "Concreto usinado fck 25", "unit": "m3", "factor": 0.06, "notes": "Pilares, vigas e cintas preliminares."},
            {"material": "Aco CA-50", "unit": "kg", "factor": 3.1, "notes": "Aco estrutural inicial por area construida."},
            {"material": "Forma compensada plastificada", "unit": "m2", "factor": 0.65, "notes": "Forma estimada para estrutura."},
        ),
        "masonry": (
            {"material": "Bloco estrutural 14x19x39", "unit": "un", "factor": 16.0, "notes": "Base preliminar de alvenaria por m2 de area construida."},
            {"material": "Argamassa de assentamento", "unit": "m3", "factor": 0.025, "notes": "Assentamento e amarracao inicial."},
            {"material": "Cimento CP II 50kg", "unit": "saco", "factor": 0.18, "notes": "Equivalente medio para alvenaria."},
        ),
        "roof": (
            {"material": "Telha ceramica", "unit": "m2", "factor": 1.18, "notes": "Cobertura com perda tecnica e recortes."},
            {"material": "Madeiramento para telhado", "unit": "m2", "factor": 1.0, "notes": "Estrutura base da cobertura."},
            {"material": "Manta termica", "unit": "m2", "factor": 0.92, "notes": "Camada de apoio e conforto termico."},
        ),
        "hydraulic": (
            {"material": "Tubo PVC soldavel 25mm", "unit": "m", "factor": 0.9, "notes": "Rede preliminar de agua fria."},
            {"material": "Tubo PVC esgoto 100mm", "unit": "m", "factor": 0.32, "notes": "Rede principal de esgoto."},
            {"material": "Conexoes hidraulicas", "unit": "un", "factor": 1.6, "notes": "Joelhos, tees e adaptadores."},
        ),
        "electrical": (
            {"material": "Fio 2.5mm", "unit": "m", "factor": 5.0, "notes": "Circuitos de tomadas e uso geral."},
            {"material": "Fio 1.5mm", "unit": "m", "factor": 3.2, "notes": "Circuitos de iluminacao."},
            {"material": "Caixa 4x2", "unit": "un", "factor": 0.55, "notes": "Pontos eletricos iniciais."},
        ),
        "finishing": (
            {"material": "Piso ceramico", "unit": "m2", "factor": 1.08, "notes": "Piso com margem de perda inicial."},
            {"material": "Argamassa colante AC-II 20kg", "unit": "saco", "factor": 0.22, "notes": "Assentamento de revestimento."},
            {"material": "Rejunte 1kg", "unit": "un", "factor": 0.08, "notes": "Acabamento de juntas."},
            {"material": "Tinta acrilica fosca 18L", "unit": "lata", "factor": 0.018, "notes": "Pintura preliminar de paredes internas e externas."},
        ),
    }

    PHASE_ORDER = (
        ("foundation", "Fundacao", "Base estrutural"),
        ("structure", "Estrutura", "Travamento e concreto"),
        ("masonry", "Alvenaria", "Fechamento e elevacao"),
        ("roof", "Cobertura", "Telhado e protecao"),
        ("hydraulic", "Hidraulica", "Agua e esgoto"),
        ("electrical", "Eletrica", "Infra e pontos"),
        ("finishing", "Acabamentos", "Revestimento e pintura"),
    )

    def __init__(self, settings: Settings, search_service: SearchService) -> None:
        self.settings = settings
        self.search_service = search_service

    def analyze_project(self, text: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        merged_context = self._merge_context(text, context or {})
        area_m2 = merged_context.get("area_m2")
        project_type = merged_context.get("project_type")

        missing_fields: list[str] = []
        if area_m2 is None:
            missing_fields.append("area_m2")
        if project_type is None:
            missing_fields.append("project_type")

        conversation = self._build_conversation_state(merged_context, missing_fields)
        if missing_fields:
            return ConstructionProjectPayload.model_validate(
                {
                    "mode": "construction_project",
                    "status": "needs_clarification",
                    "project": self._serialize_project_state(merged_context, text),
                    "assumptions": [],
                    "next_questions": conversation["next_questions"],
                    "phases": [],
                    "procurement_items": [],
                    "summary": {
                        "analysis_level": "pending",
                        "pricing_coverage_pct": 0,
                        "workflow_stage": conversation["stage"],
                        "ready_for_procurement": False,
                    },
                    "conversation": conversation,
                    "missing_fields": missing_fields,
                    "message": "Preciso fechar o escopo principal da obra antes de montar a previsao por fase.",
                }
            ).model_dump()

        assert isinstance(area_m2, float)
        if area_m2 <= 0:
            raise ValueError("A area precisa ser maior que zero.")
        if area_m2 > self.MAX_REASONABLE_AREA_M2:
            raise ValueError("A area informada esta fora de uma faixa plausivel para estudo preliminar.")

        standard = str(merged_context.get("building_standard") or "medio")
        floors = int(merged_context.get("floors") or 1)
        location = merged_context.get("location")
        roof_type = str(merged_context.get("roof_type") or self._infer_roof_type(text, project_type))
        foundation_type = merged_context.get("foundation_type")
        bedrooms = merged_context.get("bedrooms")
        bathrooms = merged_context.get("bathrooms")

        assumptions = self._build_assumptions(text, standard, floors, roof_type, location, foundation_type)
        next_questions = self._build_next_questions(merged_context)
        phase_area = area_m2 / max(floors, 1) if project_type == "townhouse" else area_m2
        phase_multiplier = self.STANDARD_MULTIPLIERS.get(standard, 1.0)

        phases = [
            self._price_phase(
                {
                    "key": phase_key,
                    "title": title,
                    "share_label": share_label,
                    "materials": self._build_phase_materials(
                        phase_key=phase_key,
                        area_m2=phase_area if phase_key == "roof" else area_m2,
                        multiplier=phase_multiplier,
                        roof_type=roof_type,
                    ),
                }
            )
            for phase_key, title, share_label in self.PHASE_ORDER
        ]

        procurement_items = self._merge_procurement_items(phases)
        project_label = self.PROJECT_TYPE_LABELS[project_type]
        estimated_total_cents = sum(int(phase.get("estimated_cost_cents") or 0) for phase in phases if phase.get("estimated_cost_cents") is not None)
        priced_materials = sum(int(phase.get("priced_materials") or 0) for phase in phases)
        missing_price_materials = sum(int(phase.get("missing_price_materials") or 0) for phase in phases)
        total_materials = priced_materials + missing_price_materials
        pricing_coverage_pct = round((priced_materials / total_materials) * 100, 1) if total_materials else 0.0
        conversation = self._build_conversation_state(merged_context, [], next_questions=next_questions)

        return ConstructionProjectPayload.model_validate(
            {
                "mode": "construction_project",
                "status": "ok",
                "project": {
                    **self._serialize_project_state(merged_context, text),
                    "project_label": project_label,
                    "safety_margin_pct": 10,
                },
                "assumptions": assumptions,
                "next_questions": next_questions,
                "phases": phases,
                "procurement_items": procurement_items,
                "summary": {
                    "analysis_level": "preliminary" if assumptions else "guided",
                    "workflow_stage": conversation["stage"],
                    "ready_for_procurement": len(next_questions) == 0,
                    "title": f"Previsao inicial para {project_label} de {round(area_m2, 2)} m2",
                    "subtitle": f"Padrao {standard} | {floors} pavimento(s) | margem tecnica de 10%",
                    "estimated_total_cost_cents": estimated_total_cents if estimated_total_cents > 0 else None,
                    "estimated_total_cost_display": self._format_brl_from_cents(estimated_total_cents) if estimated_total_cents > 0 else None,
                    "priced_materials": priced_materials,
                    "missing_price_materials": missing_price_materials,
                    "pricing_coverage_pct": pricing_coverage_pct,
                    "disclaimer": "Estimativa preliminar por tipologia de obra. Validar estrutura, fundacao, instalacoes e arquitetura antes de comprar.",
                },
                "conversation": conversation,
                "missing_fields": [],
                "message": self._build_guided_message(next_questions),
            }
        ).model_dump()

    def _merge_context(self, text: str, context: dict[str, Any]) -> dict[str, Any]:
        project_type = self._infer_project_type(text) or self._clean_choice(context.get("project_type"), set(self.PROJECT_TYPE_LABELS))
        standard = self._infer_standard(text) or self._clean_choice(context.get("building_standard"), set(self.STANDARD_MULTIPLIERS))
        floors = self._infer_floors(text, project_type) if project_type else self._coerce_int(context.get("floors"))
        if floors is None:
            floors = 1
        area_m2 = self._extract_area(text)
        if area_m2 is None:
            area_m2 = self._coerce_float(context.get("area_m2"))
        roof_type = self._infer_roof_type(text, project_type) if project_type else self._clean_choice(
            context.get("roof_type"),
            {"telha_ceramica", "telha_fibrocimento", "telha_metalica", "laje_impermeabilizada"},
        )
        foundation_type = self._infer_foundation_type(text) or self._clean_choice(
            context.get("foundation_type"),
            {"sapata", "radier", "estaca", "bloco"},
        )
        location = self._infer_location(text) or self._clean_text(context.get("location"))
        bedrooms = self._extract_room_count(text, ("quarto", "quartos"))
        if bedrooms is None:
            bedrooms = self._coerce_int(context.get("bedrooms"))
        bathrooms = self._extract_room_count(text, ("banheiro", "banheiros"))
        if bathrooms is None:
            bathrooms = self._coerce_int(context.get("bathrooms"))

        return {
            "area_m2": area_m2,
            "project_type": project_type,
            "building_standard": standard or "medio",
            "floors": floors,
            "roof_type": roof_type or ("telha_ceramica" if project_type == "house" else None),
            "foundation_type": foundation_type,
            "location": location,
            "bedrooms": bedrooms,
            "bathrooms": bathrooms,
        }

    def _build_conversation_state(
        self,
        context: dict[str, Any],
        missing_fields: list[str],
        *,
        next_questions: list[str] | None = None,
    ) -> dict[str, Any]:
        answered = [
            key
            for key in ("area_m2", "project_type", "building_standard", "location", "roof_type", "foundation_type")
            if context.get(key) not in (None, "", 0)
        ]
        remaining = [key for key in ("area_m2", "project_type", "building_standard", "location", "roof_type", "foundation_type") if key not in answered]
        stage = "scope"
        if not missing_fields:
            if remaining:
                stage = "refinement"
            else:
                stage = "ready"
        return {
            "stage": stage,
            "answered_fields": answered,
            "pending_fields": missing_fields or remaining[:3],
            "ready_for_estimate": not missing_fields,
            "ready_for_procurement": not remaining,
            "context": self._serialize_project_state(context, ""),
            "next_questions": next_questions or self._build_next_questions(context),
        }

    def _serialize_project_state(self, context: dict[str, Any], raw_text: str) -> dict[str, Any]:
        return {
            "raw_text": raw_text or context.get("raw_text") or "",
            "area_m2": context.get("area_m2"),
            "project_type": context.get("project_type"),
            "building_standard": context.get("building_standard"),
            "floors": context.get("floors"),
            "roof_type": context.get("roof_type"),
            "foundation_type": context.get("foundation_type"),
            "location": context.get("location"),
            "bedrooms": context.get("bedrooms"),
            "bathrooms": context.get("bathrooms"),
        }

    def _build_guided_message(self, next_questions: list[str]) -> str:
        if next_questions:
            return "Montei a previsao inicial da obra e deixei os proximos pontos que eu, como mestre de obra, refinaria antes da compra."
        return "Montei a previsao inicial da obra com o escopo principal ja bem fechado para seguir para refinamento de compra."

    def _build_phase_materials(self, *, phase_key: str, area_m2: float, multiplier: float, roof_type: str) -> list[dict[str, Any]]:
        rows = []
        for item in self.PHASE_LIBRARY[phase_key]:
            material_name = item["material"]
            notes = item["notes"]
            if phase_key == "roof" and "Telha" in material_name:
                material_name = self._roof_material_label(roof_type)
                notes = f"Cobertura assumida como {roof_type.replace('_', ' ')}."

            quantity = self._round_quantity(item["factor"] * area_m2 * multiplier * self.SAFETY_MARGIN_MULTIPLIER, item["unit"])
            rows.append(
                {
                    "material": material_name,
                    "quantity": quantity,
                    "unit": item["unit"],
                    "notes": notes,
                    "pricing_status": "pending",
                }
            )
        return rows

    def _price_phase(self, phase: dict[str, Any]) -> dict[str, Any]:
        priced_materials = []
        priced_count = 0
        missing_count = 0
        total_cost_cents = 0

        for material in phase["materials"]:
            priced = self._price_material(material)
            priced_materials.append(priced)
            if priced.get("estimated_total_cents") is not None:
                priced_count += 1
                total_cost_cents += int(priced["estimated_total_cents"])
            else:
                missing_count += 1

        return {
            **phase,
            "materials": priced_materials,
            "estimated_cost_cents": total_cost_cents if priced_count else None,
            "estimated_cost_display": self._format_brl_from_cents(total_cost_cents) if priced_count else None,
            "priced_materials": priced_count,
            "missing_price_materials": missing_count,
        }

    def _price_material(self, material: dict[str, Any]) -> dict[str, Any]:
        offers = []
        item_name = str(material["material"]).strip()
        try:
            offers.extend(self.search_service.search_supplier_snapshots(item_name, limit=5))
        except Exception:
            pass
        try:
            offers.extend(self.search_service.search_catalog(item_name, limit=5))
        except Exception:
            pass

        prices = [float(offer.get("price")) for offer in offers if isinstance(offer.get("price"), (int, float))]
        if not prices:
            return {
                **material,
                "pricing_status": "unavailable",
                "pricing_source": None,
                "unit_price_cents": None,
                "unit_price_display": None,
                "estimated_total_cents": None,
                "estimated_total_display": None,
            }

        avg_price = mean(prices)
        unit_price_cents = int(round(avg_price * 100))
        quantity = float(material["quantity"])
        estimated_total_cents = int(round(unit_price_cents * quantity))
        sources = sorted({str(offer.get("source") or "reference") for offer in offers if offer.get("source")})

        return {
            **material,
            "pricing_status": "estimated",
            "pricing_source": "+".join(sources) or "reference",
            "unit_price_cents": unit_price_cents,
            "unit_price_display": self._format_brl_from_cents(unit_price_cents),
            "estimated_total_cents": estimated_total_cents,
            "estimated_total_display": self._format_brl_from_cents(estimated_total_cents),
        }

    def _merge_procurement_items(self, phases: list[dict[str, Any]]) -> list[dict[str, Any]]:
        merged: dict[tuple[str, str], dict[str, Any]] = {}
        for phase in phases:
            for item in phase["materials"]:
                key = (item["material"], item["unit"])
                current = merged.get(key) or {
                    "material": item["material"],
                    "quantity": 0.0,
                    "unit": item["unit"],
                    "notes": "Consolidado preliminar para compra por fase.",
                    "pricing_status": item.get("pricing_status") or "pending",
                    "unit_price_cents": item.get("unit_price_cents"),
                    "unit_price_display": item.get("unit_price_display"),
                    "estimated_total_cents": 0 if item.get("estimated_total_cents") is not None else None,
                    "estimated_total_display": None,
                    "pricing_source": item.get("pricing_source"),
                }
                current["quantity"] = round(float(current["quantity"]) + float(item["quantity"]), 2)
                if item.get("unit_price_cents") is not None and current.get("unit_price_cents") is None:
                    current["unit_price_cents"] = item["unit_price_cents"]
                    current["unit_price_display"] = item.get("unit_price_display")
                    current["pricing_status"] = item.get("pricing_status") or "estimated"
                    current["pricing_source"] = item.get("pricing_source")
                if item.get("estimated_total_cents") is not None:
                    current["estimated_total_cents"] = int(current.get("estimated_total_cents") or 0) + int(item["estimated_total_cents"])
                    current["estimated_total_display"] = self._format_brl_from_cents(int(current["estimated_total_cents"]))
                merged[key] = current
        ranked = sorted(
            merged.values(),
            key=lambda row: (
                -(int(row.get("estimated_total_cents") or 0)),
                -float(row["quantity"]),
                row["material"],
            ),
        )
        return ranked[:12]

    def _build_assumptions(
        self,
        text: str,
        standard: str,
        floors: int,
        roof_type: str,
        location: str | None,
        foundation_type: str | None,
    ) -> list[str]:
        assumptions: list[str] = []
        lowered = str(text or "").lower()
        if not any(token in lowered for token in ("economico", "medio", "alto", "premium", "padrao")):
            assumptions.append(f"Padrao de acabamento assumido como {standard}.")
        if "pavimento" not in lowered and "sobrado" not in lowered and "terrea" not in lowered and "terreo" not in lowered:
            assumptions.append(f"Quantidade de pavimentos assumida como {floors}.")
        if roof_type and "telha" not in lowered and "laje" not in lowered and "fibrocimento" not in lowered:
            assumptions.append(f"Cobertura preliminar assumida como {roof_type.replace('_', ' ')}.")
        if not location:
            assumptions.append("Localidade ainda nao informada; a previsao nao considera logistica nem variacao regional de preco.")
        if not foundation_type:
            assumptions.append("Fundacao ainda nao definida; esta previsao considera apenas uma base preliminar de consumo.")
        return assumptions[:5]

    def _build_next_questions(self, context: dict[str, Any]) -> list[str]:
        questions: list[str] = []
        if not context.get("area_m2"):
            questions.append("Qual e a area aproximada da obra em m2?")
        if not context.get("project_type"):
            questions.append("Voce esta falando de casa, sobrado, galpao ou obra comercial?")
        if not context.get("building_standard"):
            questions.append("Qual padrao de acabamento voce quer considerar: economico, medio ou alto?")
        elif context.get("building_standard") == "medio" and not context.get("location"):
            questions.append("Em qual cidade ou regiao sera a obra? Isso ajuda na compra e nos precos.")
        if not context.get("roof_type"):
            questions.append("Na cobertura, quer telha ceramica, fibrocimento, metalica ou laje impermeabilizada?")
        if not context.get("foundation_type"):
            questions.append("Se ja souber, qual fundacao pretende usar: sapata, radier, estaca ou bloco?")
        return questions[:4]

    def _extract_area(self, text: str) -> float | None:
        match = re.search(r"(\d+(?:[.,]\d+)?)\s*m2\b", text or "", flags=re.IGNORECASE)
        if not match:
            return None
        return float(match.group(1).replace(",", "."))

    def _infer_project_type(self, text: str) -> str | None:
        lowered = str(text or "").lower()
        if "sobrado" in lowered:
            return "townhouse"
        if any(token in lowered for token in ("galpao", "galpão", "barracao")):
            return "warehouse"
        if any(token in lowered for token in ("comercial", "loja", "sala comercial")):
            return "commercial"
        if any(token in lowered for token in ("casa", "residencia", "residencial", "edicula")):
            return "house"
        return None

    def _infer_standard(self, text: str) -> str | None:
        lowered = str(text or "").lower()
        if any(token in lowered for token in ("alto padrao", "premium", "alto")):
            return "alto"
        if any(token in lowered for token in ("economico", "popular", "baixo")):
            return "economico"
        if any(token in lowered for token in ("medio", "padrao medio", "standard")):
            return "medio"
        return None

    def _infer_floors(self, text: str, project_type: str | None) -> int | None:
        lowered = str(text or "").lower()
        if project_type == "townhouse":
            return 2
        if any(token in lowered for token in ("2 pavimentos", "dois pavimentos", "sobrado")):
            return 2
        if any(token in lowered for token in ("1 pavimento", "um pavimento", "terrea", "terreo")):
            return 1
        return None

    def _infer_roof_type(self, text: str, project_type: str | None) -> str | None:
        lowered = str(text or "").lower()
        if "laje" in lowered:
            return "laje_impermeabilizada"
        if "fibrocimento" in lowered:
            return "telha_fibrocimento"
        if "metalica" in lowered or "metálica" in lowered:
            return "telha_metalica"
        if "ceramica" in lowered or "cerâmica" in lowered:
            return "telha_ceramica"
        if project_type == "warehouse":
            return "telha_fibrocimento"
        if project_type:
            return "telha_ceramica"
        return None

    def _infer_foundation_type(self, text: str) -> str | None:
        lowered = str(text or "").lower()
        if "radier" in lowered:
            return "radier"
        if "sapata" in lowered:
            return "sapata"
        if "estaca" in lowered:
            return "estaca"
        if "bloco" in lowered and "fundacao" in lowered:
            return "bloco"
        return None

    def _infer_location(self, text: str) -> str | None:
        match = re.search(r"\bem\s+([A-Za-zÀ-ÿ\s\-]+)", text or "", flags=re.IGNORECASE)
        if not match:
            return None
        location = match.group(1).strip(" .,-")
        location = re.split(r"\b(com|padrao|padrão|fundacao|fundação|telha|laje|sobrado|casa)\b", location, maxsplit=1, flags=re.IGNORECASE)[0]
        return location.strip(" .,-") or None

    def _extract_room_count(self, text: str, tokens: tuple[str, ...]) -> int | None:
        pattern = rf"(\d+)\s+(?:{'|'.join(tokens)})\b"
        match = re.search(pattern, text or "", flags=re.IGNORECASE)
        return int(match.group(1)) if match else None

    def _roof_material_label(self, roof_type: str) -> str:
        labels = {
            "telha_ceramica": "Telha ceramica",
            "telha_fibrocimento": "Telha fibrocimento",
            "telha_metalica": "Telha metalica",
            "laje_impermeabilizada": "Impermeabilizacao para laje",
        }
        return labels.get(roof_type, "Cobertura")

    def _round_quantity(self, value: float, unit: str) -> float | int:
        rounded = round(value, 2)
        if unit in {"un", "saco"}:
            return max(1, int(round(rounded)))
        return rounded

    def _format_brl_from_cents(self, value_cents: int) -> str:
        raw = f"{value_cents / 100:,.2f}"
        return "R$ " + raw.replace(",", "X").replace(".", ",").replace("X", ".")

    def _clean_choice(self, value: Any, allowed: set[str]) -> str | None:
        text = self._clean_text(value)
        if not text or text not in allowed:
            return None
        return text

    def _clean_text(self, value: Any) -> str | None:
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None

    def _coerce_float(self, value: Any) -> float | None:
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _coerce_int(self, value: Any) -> int | None:
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
