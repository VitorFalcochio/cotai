from __future__ import annotations

from datetime import UTC, datetime
import re
from statistics import mean
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ...worker.config import Settings
from ...worker.services.search_service import SearchService
from ...worker.utils.telemetry import telemetry


class ConstructionMaterialPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material: str
    quantity: float | int
    unit: str
    notes: str
    unit_price_cents: int | None = None
    unit_price_display: str | None = None
    unit_price_range_min_cents: int | None = None
    unit_price_range_min_display: str | None = None
    unit_price_range_max_cents: int | None = None
    unit_price_range_max_display: str | None = None
    estimated_total_cents: int | None = None
    estimated_total_display: str | None = None
    estimated_total_range_min_cents: int | None = None
    estimated_total_range_min_display: str | None = None
    estimated_total_range_max_cents: int | None = None
    estimated_total_range_max_display: str | None = None
    pricing_source: str | None = None
    pricing_status: str
    reference_count: int = Field(default=0, ge=0)
    reference_age_days: int | None = None
    reference_age_label: str | None = None
    pricing_strength: str = "unavailable"


class ConstructionPhasePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    title: str
    share_label: str
    materials: list[ConstructionMaterialPayload]
    estimated_cost_cents: int | None = None
    estimated_cost_display: str | None = None
    estimated_cost_range_min_cents: int | None = None
    estimated_cost_range_min_display: str | None = None
    estimated_cost_range_max_cents: int | None = None
    estimated_cost_range_max_display: str | None = None
    priced_materials: int = Field(ge=0)
    missing_price_materials: int = Field(ge=0)
    reference_count: int = Field(default=0, ge=0)
    reference_age_days: int | None = None
    reference_age_label: str | None = None
    pricing_strength: str = "unavailable"


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


class ConstructionPhasePackagePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    title: str
    estimated_cost_cents: int | None = None
    estimated_cost_display: str | None = None
    estimated_cost_range_min_display: str | None = None
    estimated_cost_range_max_display: str | None = None
    item_count: int = Field(ge=0)
    pricing_strength: str = "unavailable"
    items: list[ConstructionMaterialPayload]


class ConstructionProcurementPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: str
    status: str
    project: dict[str, Any]
    summary: dict[str, Any]
    purchase_list: list[ConstructionMaterialPayload]
    phase_packages: list[ConstructionPhasePackagePayload]
    selected_phase_key: str | None = None
    live_quotes: list[dict[str, Any]] = Field(default_factory=list)
    message: str


class ConstructionModeService:
    SAFETY_MARGIN_MULTIPLIER = 1.10
    MAX_REASONABLE_AREA_M2 = 1_000_000.0

    PROJECT_TYPE_LABELS = {
        "house": "casa",
        "townhouse": "sobrado",
        "warehouse": "galpao",
        "commercial": "obra comercial",
        "renovation": "reforma",
        "wall": "muro",
        "sidewalk": "calcada",
        "screed": "contrapiso",
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
        "demolition": (
            {"material": "Caixa de entulho 4m3", "unit": "un", "factor": 0.03, "notes": "Remocao inicial de entulho de reforma."},
            {"material": "Disco de corte diamantado", "unit": "un", "factor": 0.012, "notes": "Apoio para demolicao e cortes pontuais."},
            {"material": "Argamassa de regularizacao", "unit": "saco", "factor": 0.08, "notes": "Regularizacao preliminar apos demolicao."},
        ),
        "wall_foundation": (
            {"material": "Concreto usinado fck 25", "unit": "m3", "factor": 0.06, "notes": "Base corrida para muro."},
            {"material": "Aco CA-50", "unit": "kg", "factor": 1.8, "notes": "Armadura inicial de baldrame e pilares."},
            {"material": "Brita 1", "unit": "m3", "factor": 0.04, "notes": "Agregado para base do muro."},
        ),
        "wall_masonry": (
            {"material": "Bloco estrutural 14x19x39", "unit": "un", "factor": 12.0, "notes": "Fechamento de muro por area estimada."},
            {"material": "Argamassa de assentamento", "unit": "m3", "factor": 0.018, "notes": "Assentamento dos blocos do muro."},
            {"material": "Cimento CP II 50kg", "unit": "saco", "factor": 0.1, "notes": "Complemento para alvenaria e pilares."},
        ),
        "wall_finish": (
            {"material": "Chapisco rolado 18L", "unit": "balde", "factor": 0.012, "notes": "Preparacao inicial da superficie do muro."},
            {"material": "Massa para reboco", "unit": "saco", "factor": 0.14, "notes": "Revestimento basico do muro."},
            {"material": "Tinta acrilica fosca 18L", "unit": "lata", "factor": 0.012, "notes": "Acabamento externo preliminar."},
        ),
        "pavement_base": (
            {"material": "Bica corrida", "unit": "m3", "factor": 0.12, "notes": "Base compactada para calcada."},
            {"material": "Brita 1", "unit": "m3", "factor": 0.05, "notes": "Regularizacao da base."},
            {"material": "Lona preta 200 micras", "unit": "m2", "factor": 1.05, "notes": "Separacao e cura inicial."},
        ),
        "pavement_finish": (
            {"material": "Concreto usinado fck 25", "unit": "m3", "factor": 0.08, "notes": "Lancamento principal da calcada."},
            {"material": "Tela soldada Q138", "unit": "m2", "factor": 1.0, "notes": "Armadura leve para calcada."},
            {"material": "Junta de dilatacao", "unit": "m", "factor": 0.45, "notes": "Controle de fissuracao e modulo da calcada."},
        ),
        "screed_base": (
            {"material": "Areia media", "unit": "m3", "factor": 0.04, "notes": "Base para contrapiso e regularizacao."},
            {"material": "Cimento CP II 50kg", "unit": "saco", "factor": 0.12, "notes": "Traco preliminar do contrapiso."},
            {"material": "Aditivo plastificante", "unit": "l", "factor": 0.08, "notes": "Melhora de trabalhabilidade do contrapiso."},
        ),
        "screed_finish": (
            {"material": "Argamassa de regularizacao", "unit": "saco", "factor": 0.14, "notes": "Camada principal do contrapiso."},
            {"material": "Tela de reforco leve", "unit": "m2", "factor": 1.0, "notes": "Reforco leve onde houver solicitacao."},
            {"material": "Selador acrilico", "unit": "l", "factor": 0.1, "notes": "Preparacao final para revestimento futuro."},
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

    PROJECT_PHASES = {
        "house": PHASE_ORDER,
        "townhouse": PHASE_ORDER,
        "commercial": PHASE_ORDER,
        "warehouse": (
            ("foundation", "Fundacao", "Base estrutural"),
            ("structure", "Estrutura", "Pilares e travamentos"),
            ("roof", "Cobertura", "Fechamento superior"),
            ("electrical", "Eletrica", "Infra e distribuicao"),
            ("hydraulic", "Hidraulica", "Apoios e drenagem"),
            ("finishing", "Acabamentos", "Piso e pintura industrial"),
        ),
        "renovation": (
            ("demolition", "Demolicao e preparo", "Remocao e regularizacao"),
            ("masonry", "Ajustes de alvenaria", "Fechamentos e reparos"),
            ("hydraulic", "Hidraulica", "Trocas e adaptacoes"),
            ("electrical", "Eletrica", "Revisoes e novos pontos"),
            ("finishing", "Acabamentos", "Revestimento e pintura"),
        ),
        "wall": (
            ("wall_foundation", "Fundacao do muro", "Base corrida"),
            ("wall_masonry", "Elevacao do muro", "Blocos e pilares"),
            ("wall_finish", "Acabamento", "Reboco e pintura"),
        ),
        "sidewalk": (
            ("pavement_base", "Base da calcada", "Compactacao e regularizacao"),
            ("pavement_finish", "Concretagem", "Lancamento e juntas"),
            ("wall_finish", "Acabamento", "Protecao superficial"),
        ),
        "screed": (
            ("screed_base", "Base do contrapiso", "Traco e preparo"),
            ("screed_finish", "Execucao do contrapiso", "Regularizacao final"),
        ),
    }

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
            telemetry.record("construction_analysis_completed", project_type=project_type or "unknown", status="needs_clarification")
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
        roof_type = str(merged_context.get("roof_type") or self._infer_roof_type(text, project_type) or "")
        foundation_type = merged_context.get("foundation_type")
        bedrooms = merged_context.get("bedrooms")
        bathrooms = merged_context.get("bathrooms")

        assumptions = self._build_assumptions(text, project_type, standard, floors, roof_type or None, location, foundation_type)
        next_questions = self._build_next_questions(merged_context)
        phase_area = area_m2 / max(floors, 1) if project_type == "townhouse" else area_m2
        phase_multiplier = self.STANDARD_MULTIPLIERS.get(standard, 1.0)
        phase_order = self.PROJECT_PHASES.get(project_type, self.PHASE_ORDER)

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
                        roof_type=roof_type or "telha_ceramica",
                    ),
                }
            )
            for phase_key, title, share_label in phase_order
        ]

        procurement_items = self._merge_procurement_items(phases)
        project_label = self.PROJECT_TYPE_LABELS[project_type]
        estimated_total_cents = sum(int(phase.get("estimated_cost_cents") or 0) for phase in phases if phase.get("estimated_cost_cents") is not None)
        estimated_total_range_min_cents = sum(int(phase.get("estimated_cost_range_min_cents") or 0) for phase in phases if phase.get("estimated_cost_range_min_cents") is not None)
        estimated_total_range_max_cents = sum(int(phase.get("estimated_cost_range_max_cents") or 0) for phase in phases if phase.get("estimated_cost_range_max_cents") is not None)
        priced_materials = sum(int(phase.get("priced_materials") or 0) for phase in phases)
        missing_price_materials = sum(int(phase.get("missing_price_materials") or 0) for phase in phases)
        reference_count = sum(int(phase.get("reference_count") or 0) for phase in phases)
        total_materials = priced_materials + missing_price_materials
        pricing_coverage_pct = round((priced_materials / total_materials) * 100, 1) if total_materials else 0.0
        reference_ages = [int(phase["reference_age_days"]) for phase in phases if phase.get("reference_age_days") is not None]
        freshest_reference_days = min(reference_ages) if reference_ages else None
        pricing_strength = self._classify_pricing_strength(
            coverage_pct=pricing_coverage_pct,
            freshest_reference_days=freshest_reference_days,
            reference_count=reference_count,
        )
        conversation = self._build_conversation_state(merged_context, [], next_questions=next_questions)
        telemetry.record("construction_analysis_completed", project_type=project_type, status="ok", pricing_strength=pricing_strength)

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
                    "estimated_total_cost_range_min_cents": estimated_total_range_min_cents if estimated_total_range_min_cents > 0 else None,
                    "estimated_total_cost_range_min_display": self._format_brl_from_cents(estimated_total_range_min_cents) if estimated_total_range_min_cents > 0 else None,
                    "estimated_total_cost_range_max_cents": estimated_total_range_max_cents if estimated_total_range_max_cents > 0 else None,
                    "estimated_total_cost_range_max_display": self._format_brl_from_cents(estimated_total_range_max_cents) if estimated_total_range_max_cents > 0 else None,
                    "priced_materials": priced_materials,
                    "missing_price_materials": missing_price_materials,
                    "pricing_coverage_pct": pricing_coverage_pct,
                    "reference_count": reference_count,
                    "freshest_reference_days": freshest_reference_days,
                    "freshest_reference_label": self._format_reference_age_label(freshest_reference_days),
                    "pricing_strength": pricing_strength,
                    "pricing_strength_label": self._pricing_strength_label(pricing_strength),
                    "disclaimer": "Estimativa preliminar por tipologia de obra. Validar estrutura, fundacao, instalacoes e arquitetura antes de comprar.",
                },
                "conversation": conversation,
                "missing_fields": [],
                "message": self._build_guided_message(next_questions),
            }
        ).model_dump()

    def build_procurement_plan(self, analysis: dict[str, Any], *, selected_phase: str | None = None) -> dict[str, Any]:
        if str(analysis.get("status") or "").lower() != "ok":
            telemetry.record("construction_procurement_completed", status="needs_clarification")
            return ConstructionProcurementPayload.model_validate(
                {
                    "mode": "construction_procurement",
                    "status": "needs_clarification",
                    "project": analysis.get("project") or {},
                    "summary": {
                        "title": "Preciso fechar o escopo antes de montar a compra",
                        "subtitle": "Complete a analise da obra para gerar a lista de compra.",
                    },
                    "purchase_list": [],
                    "phase_packages": [],
                    "selected_phase_key": selected_phase,
                    "live_quotes": [],
                    "message": "A lista de compra so fica confiavel depois que a analise da obra estiver pronta.",
                }
            ).model_dump()

        purchase_list = list(analysis.get("procurement_items") or [])
        phases = list(analysis.get("phases") or [])
        selected_phase_key = selected_phase or (phases[0]["key"] if phases else None)
        telemetry.record("construction_procurement_completed", status="ok", selected_phase=selected_phase_key or "all")
        phase_packages = [
            {
                "key": phase["key"],
                "title": phase["title"],
                "estimated_cost_cents": phase.get("estimated_cost_cents"),
                "estimated_cost_display": phase.get("estimated_cost_display"),
                "estimated_cost_range_min_display": phase.get("estimated_cost_range_min_display"),
                "estimated_cost_range_max_display": phase.get("estimated_cost_range_max_display"),
                "item_count": len(phase.get("materials") or []),
                "pricing_strength": phase.get("pricing_strength") or "unavailable",
                "items": phase.get("materials") or [],
            }
            for phase in phases
        ]
        return ConstructionProcurementPayload.model_validate(
            {
                "mode": "construction_procurement",
                "status": "ok",
                "project": analysis.get("project") or {},
                "summary": {
                    "title": "Lista de compra pronta para a obra",
                    "subtitle": "A Cota separou um pacote geral e os pacotes por fase para voce comprar com mais controle.",
                    "selected_phase_title": next((phase["title"] for phase in phase_packages if phase["key"] == selected_phase_key), None),
                    "estimated_total_cost_display": analysis.get("summary", {}).get("estimated_total_cost_display"),
                    "pricing_strength_label": analysis.get("summary", {}).get("pricing_strength_label"),
                },
                "purchase_list": purchase_list,
                "phase_packages": phase_packages,
                "selected_phase_key": selected_phase_key,
                "live_quotes": [],
                "message": "Transformei a previsao em lista de compra. Se quiser, eu tambem puxo cotacao real por fase.",
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
            "roof_type": roof_type or self._default_roof_for_project(project_type),
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
        required_fields = self._required_context_fields(context.get("project_type"))
        answered = [key for key in required_fields if context.get(key) not in (None, "", 0)]
        remaining = [key for key in required_fields if key not in answered]
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
        total_range_min_cents = 0
        total_range_max_cents = 0
        reference_count = 0
        reference_ages: list[int] = []

        for material in phase["materials"]:
            priced = self._price_material(material)
            priced_materials.append(priced)
            if priced.get("estimated_total_cents") is not None:
                priced_count += 1
                total_cost_cents += int(priced["estimated_total_cents"])
                total_range_min_cents += int(priced.get("estimated_total_range_min_cents") or priced["estimated_total_cents"])
                total_range_max_cents += int(priced.get("estimated_total_range_max_cents") or priced["estimated_total_cents"])
                reference_count += int(priced.get("reference_count") or 0)
                if priced.get("reference_age_days") is not None:
                    reference_ages.append(int(priced["reference_age_days"]))
            else:
                missing_count += 1

        freshest_reference_days = min(reference_ages) if reference_ages else None
        total_materials = priced_count + missing_count
        coverage_pct = round((priced_count / total_materials) * 100, 1) if total_materials else 0.0
        pricing_strength = self._classify_pricing_strength(
            coverage_pct=coverage_pct,
            freshest_reference_days=freshest_reference_days,
            reference_count=reference_count,
        )
        return {
            **phase,
            "materials": priced_materials,
            "estimated_cost_cents": total_cost_cents if priced_count else None,
            "estimated_cost_display": self._format_brl_from_cents(total_cost_cents) if priced_count else None,
            "estimated_cost_range_min_cents": total_range_min_cents if priced_count else None,
            "estimated_cost_range_min_display": self._format_brl_from_cents(total_range_min_cents) if priced_count else None,
            "estimated_cost_range_max_cents": total_range_max_cents if priced_count else None,
            "estimated_cost_range_max_display": self._format_brl_from_cents(total_range_max_cents) if priced_count else None,
            "priced_materials": priced_count,
            "missing_price_materials": missing_count,
            "reference_count": reference_count,
            "reference_age_days": freshest_reference_days,
            "reference_age_label": self._format_reference_age_label(freshest_reference_days),
            "pricing_strength": pricing_strength,
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
                "unit_price_range_min_cents": None,
                "unit_price_range_min_display": None,
                "unit_price_range_max_cents": None,
                "unit_price_range_max_display": None,
                "estimated_total_cents": None,
                "estimated_total_display": None,
                "estimated_total_range_min_cents": None,
                "estimated_total_range_min_display": None,
                "estimated_total_range_max_cents": None,
                "estimated_total_range_max_display": None,
                "reference_count": 0,
                "reference_age_days": None,
                "reference_age_label": None,
                "pricing_strength": "unavailable",
            }

        avg_price = mean(prices)
        min_price = min(prices)
        max_price = max(prices)
        unit_price_cents = int(round(avg_price * 100))
        unit_price_range_min_cents = int(round(min_price * 100))
        unit_price_range_max_cents = int(round(max_price * 100))
        quantity = float(material["quantity"])
        estimated_total_cents = int(round(unit_price_cents * quantity))
        estimated_total_range_min_cents = int(round(unit_price_range_min_cents * quantity))
        estimated_total_range_max_cents = int(round(unit_price_range_max_cents * quantity))
        sources = sorted({str(offer.get("source") or "reference") for offer in offers if offer.get("source")})
        reference_age_days = self._extract_freshest_reference_age_days(offers)
        pricing_strength = self._classify_pricing_strength(
            coverage_pct=100.0,
            freshest_reference_days=reference_age_days,
            reference_count=len(prices),
        )

        return {
            **material,
            "pricing_status": "estimated",
            "pricing_source": "+".join(sources) or "reference",
            "unit_price_cents": unit_price_cents,
            "unit_price_display": self._format_brl_from_cents(unit_price_cents),
            "unit_price_range_min_cents": unit_price_range_min_cents,
            "unit_price_range_min_display": self._format_brl_from_cents(unit_price_range_min_cents),
            "unit_price_range_max_cents": unit_price_range_max_cents,
            "unit_price_range_max_display": self._format_brl_from_cents(unit_price_range_max_cents),
            "estimated_total_cents": estimated_total_cents,
            "estimated_total_display": self._format_brl_from_cents(estimated_total_cents),
            "estimated_total_range_min_cents": estimated_total_range_min_cents,
            "estimated_total_range_min_display": self._format_brl_from_cents(estimated_total_range_min_cents),
            "estimated_total_range_max_cents": estimated_total_range_max_cents,
            "estimated_total_range_max_display": self._format_brl_from_cents(estimated_total_range_max_cents),
            "reference_count": len(prices),
            "reference_age_days": reference_age_days,
            "reference_age_label": self._format_reference_age_label(reference_age_days),
            "pricing_strength": pricing_strength,
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
                    "unit_price_range_min_cents": item.get("unit_price_range_min_cents"),
                    "unit_price_range_min_display": item.get("unit_price_range_min_display"),
                    "unit_price_range_max_cents": item.get("unit_price_range_max_cents"),
                    "unit_price_range_max_display": item.get("unit_price_range_max_display"),
                    "estimated_total_cents": 0 if item.get("estimated_total_cents") is not None else None,
                    "estimated_total_display": None,
                    "estimated_total_range_min_cents": 0 if item.get("estimated_total_range_min_cents") is not None else None,
                    "estimated_total_range_min_display": None,
                    "estimated_total_range_max_cents": 0 if item.get("estimated_total_range_max_cents") is not None else None,
                    "estimated_total_range_max_display": None,
                    "pricing_source": item.get("pricing_source"),
                    "reference_count": int(item.get("reference_count") or 0),
                    "reference_age_days": item.get("reference_age_days"),
                    "reference_age_label": item.get("reference_age_label"),
                    "pricing_strength": item.get("pricing_strength") or "unavailable",
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
                if item.get("estimated_total_range_min_cents") is not None:
                    current["estimated_total_range_min_cents"] = int(current.get("estimated_total_range_min_cents") or 0) + int(item["estimated_total_range_min_cents"])
                    current["estimated_total_range_min_display"] = self._format_brl_from_cents(int(current["estimated_total_range_min_cents"]))
                if item.get("estimated_total_range_max_cents") is not None:
                    current["estimated_total_range_max_cents"] = int(current.get("estimated_total_range_max_cents") or 0) + int(item["estimated_total_range_max_cents"])
                    current["estimated_total_range_max_display"] = self._format_brl_from_cents(int(current["estimated_total_range_max_cents"]))
                current["reference_count"] = int(current.get("reference_count") or 0) + int(item.get("reference_count") or 0)
                if item.get("reference_age_days") is not None:
                    existing_age = current.get("reference_age_days")
                    current["reference_age_days"] = min(int(existing_age), int(item["reference_age_days"])) if existing_age is not None else int(item["reference_age_days"])
                    current["reference_age_label"] = self._format_reference_age_label(int(current["reference_age_days"]))
                current["pricing_strength"] = self._merge_pricing_strength(
                    current.get("pricing_strength") or "unavailable",
                    item.get("pricing_strength") or "unavailable",
                )
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
        project_type: str,
        standard: str,
        floors: int,
        roof_type: str | None,
        location: str | None,
        foundation_type: str | None,
    ) -> list[str]:
        assumptions: list[str] = []
        lowered = str(text or "").lower()
        if not any(token in lowered for token in ("economico", "medio", "alto", "premium", "padrao")):
            assumptions.append(f"Padrao de acabamento assumido como {standard}.")
        if project_type in {"house", "townhouse", "commercial", "warehouse"} and "pavimento" not in lowered and "sobrado" not in lowered and "terrea" not in lowered and "terreo" not in lowered:
            assumptions.append(f"Quantidade de pavimentos assumida como {floors}.")
        if roof_type and project_type in {"house", "townhouse", "commercial", "warehouse"} and "telha" not in lowered and "laje" not in lowered and "fibrocimento" not in lowered:
            assumptions.append(f"Cobertura preliminar assumida como {roof_type.replace('_', ' ')}.")
        if not location:
            assumptions.append("Localidade ainda nao informada; a previsao nao considera logistica nem variacao regional de preco.")
        if not foundation_type and project_type in {"house", "townhouse", "commercial", "warehouse", "wall"}:
            assumptions.append("Fundacao ainda nao definida; esta previsao considera apenas uma base preliminar de consumo.")
        return assumptions[:5]

    def _build_next_questions(self, context: dict[str, Any]) -> list[str]:
        questions: list[str] = []
        project_type = context.get("project_type")
        if not context.get("area_m2"):
            questions.append("Qual e a area aproximada da obra em m2?")
        if not context.get("project_type"):
            questions.append("Voce esta falando de casa, sobrado, galpao, reforma, muro, calcada, contrapiso ou obra comercial?")
        if not context.get("building_standard"):
            questions.append("Qual padrao de acabamento voce quer considerar: economico, medio ou alto?")
        elif context.get("building_standard") == "medio" and not context.get("location"):
            questions.append("Em qual cidade ou regiao sera a obra? Isso ajuda na compra e nos precos.")
        if project_type in {"house", "townhouse", "commercial", "warehouse"} and not context.get("roof_type"):
            questions.append("Na cobertura, quer telha ceramica, fibrocimento, metalica ou laje impermeabilizada?")
        if project_type in {"house", "townhouse", "commercial", "warehouse", "wall"} and not context.get("foundation_type"):
            questions.append("Se ja souber, qual fundacao pretende usar: sapata, radier, estaca ou bloco?")
        return questions[:4]

    def _extract_area(self, text: str) -> float | None:
        match = re.search(r"(\d+(?:[.,]\d+)?)\s*m2\b", text or "", flags=re.IGNORECASE)
        if not match:
            return None
        return float(match.group(1).replace(",", "."))

    def _infer_project_type(self, text: str) -> str | None:
        lowered = str(text or "").lower()
        if any(token in lowered for token in ("contrapiso", "regularizacao de piso", "regularização de piso")):
            return "screed"
        if any(token in lowered for token in ("calcada", "calçada", "passeio", "piso externo")):
            return "sidewalk"
        if any(token in lowered for token in ("muro", "mureta", "fechamento lateral")):
            return "wall"
        if any(token in lowered for token in ("reforma", "reformar", "retrofit", "ampliacao", "ampliação")):
            return "renovation"
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
        if project_type in {"wall", "sidewalk", "screed"}:
            return 1
        if any(token in lowered for token in ("2 pavimentos", "dois pavimentos", "sobrado")):
            return 2
        if any(token in lowered for token in ("1 pavimento", "um pavimento", "terrea", "terreo")):
            return 1
        return None

    def _infer_roof_type(self, text: str, project_type: str | None) -> str | None:
        if project_type in {"renovation", "wall", "sidewalk", "screed"}:
            return None
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

    def _required_context_fields(self, project_type: str | None) -> tuple[str, ...]:
        base_fields = ("area_m2", "project_type", "building_standard", "location")
        if project_type in {"house", "townhouse", "commercial", "warehouse"}:
            return (*base_fields, "roof_type", "foundation_type")
        if project_type == "wall":
            return (*base_fields, "foundation_type")
        return base_fields

    def _default_roof_for_project(self, project_type: str | None) -> str | None:
        if project_type == "warehouse":
            return "telha_fibrocimento"
        if project_type in {"house", "townhouse", "commercial"}:
            return "telha_ceramica"
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

    def _extract_freshest_reference_age_days(self, offers: list[dict[str, Any]]) -> int | None:
        ages: list[int] = []
        now = datetime.now(UTC)
        for offer in offers:
            captured_at = offer.get("captured_at")
            if not captured_at:
                continue
            try:
                parsed = datetime.fromisoformat(str(captured_at).replace("Z", "+00:00"))
            except ValueError:
                continue
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            ages.append(max(0, int((now - parsed.astimezone(UTC)).total_seconds() // 86400)))
        return min(ages) if ages else None

    def _format_reference_age_label(self, reference_age_days: int | None) -> str | None:
        if reference_age_days is None:
            return "Sem data recente"
        if reference_age_days <= 1:
            return "Referencia de hoje"
        if reference_age_days <= 7:
            return f"Referencia de {reference_age_days} dia(s)"
        if reference_age_days <= 30:
            weeks = max(1, round(reference_age_days / 7))
            return f"Referencia de {weeks} semana(s)"
        return f"Referencia de {reference_age_days} dia(s)"

    def _classify_pricing_strength(
        self,
        *,
        coverage_pct: float,
        freshest_reference_days: int | None,
        reference_count: int,
    ) -> str:
        if coverage_pct <= 0 or reference_count <= 0:
            return "unavailable"
        if coverage_pct >= 80 and reference_count >= 8 and (freshest_reference_days is None or freshest_reference_days <= 7):
            return "strong"
        if coverage_pct >= 50 and reference_count >= 3 and (freshest_reference_days is None or freshest_reference_days <= 30):
            return "moderate"
        return "weak"

    def _pricing_strength_label(self, strength: str) -> str:
        labels = {
            "strong": "Confianca alta",
            "moderate": "Confianca media",
            "weak": "Confianca baixa",
            "unavailable": "Sem confianca de preco",
        }
        return labels.get(strength, "Confianca indefinida")

    def _merge_pricing_strength(self, left: str, right: str) -> str:
        order = {"strong": 3, "moderate": 2, "weak": 1, "unavailable": 0}
        return left if order.get(left, 0) <= order.get(right, 0) else right

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
