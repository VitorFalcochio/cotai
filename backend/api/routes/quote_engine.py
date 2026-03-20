from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..deps import get_construction_mode_service, get_current_actor, get_dynamic_quote_service
from ..services.construction_mode_service import ConstructionModeService
from ..services.dynamic_quote_service import DynamicQuoteService

router = APIRouter(tags=["search"])


class QuoteSearchPayload(BaseModel):
    query: str = Field(min_length=3, max_length=4000, description="Pedido de material em texto livre.")


class ConstructionEstimatePayload(BaseModel):
    query: str | None = Field(default=None, max_length=4000, description="Pedido em texto livre com area, sistema e padrao.")
    area_m2: float | None = Field(default=None, gt=0)
    building_standard: str | None = Field(default=None, max_length=40)
    system_type: str | None = Field(default=None, max_length=40)


class ConstructionProjectPayload(BaseModel):
    query: str = Field(min_length=3, max_length=4000, description="Pedido em texto livre descrevendo uma obra completa.")
    context: dict[str, Any] | None = Field(default=None, description="Contexto acumulado da conversa para refino guiado.")


class ConstructionProcurementRequestPayload(BaseModel):
    query: str = Field(min_length=3, max_length=4000, description="Pedido em texto livre descrevendo a obra.")
    context: dict[str, Any] | None = Field(default=None, description="Contexto acumulado do modo construcao.")
    selected_phase: str | None = Field(default=None, max_length=40, description="Fase a ser priorizada para compra ou cotacao.")
    include_live_quotes: bool = Field(default=False, description="Quando verdadeiro, tenta cotar os itens da fase selecionada.")


@router.post("/cotar")
async def quote_materials(
    payload: QuoteSearchPayload,
    _: dict[str, Any] = Depends(get_current_actor),
    quote_service: DynamicQuoteService = Depends(get_dynamic_quote_service),
) -> dict[str, Any]:
    try:
        return await quote_service.quote_materials(payload.query)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/modo-construcao/estimar")
async def estimate_construction(
    payload: ConstructionEstimatePayload,
    _: dict[str, Any] = Depends(get_current_actor),
    quote_service: DynamicQuoteService = Depends(get_dynamic_quote_service),
) -> dict[str, Any]:
    try:
        if payload.query:
            return quote_service.budget_service.estimate_from_text(payload.query)
        if payload.area_m2 is None:
            raise ValueError("Informe uma area em m2 ou uma consulta em texto livre.")
        return quote_service.budget_service.estimate_from_area(
            area_m2=payload.area_m2,
            building_standard=payload.building_standard or "medio",
            system_type=payload.system_type or "wall",
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/modo-construcao/analisar")
async def analyze_construction_project(
    payload: ConstructionProjectPayload,
    _: dict[str, Any] = Depends(get_current_actor),
    construction_service: ConstructionModeService = Depends(get_construction_mode_service),
) -> dict[str, Any]:
    try:
        return construction_service.analyze_project(payload.query, context=payload.context)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/modo-construcao/compra")
async def build_construction_procurement(
    payload: ConstructionProcurementRequestPayload,
    _: dict[str, Any] = Depends(get_current_actor),
    construction_service: ConstructionModeService = Depends(get_construction_mode_service),
    quote_service: DynamicQuoteService = Depends(get_dynamic_quote_service),
) -> dict[str, Any]:
    try:
        analysis = construction_service.analyze_project(payload.query, context=payload.context)
        procurement = construction_service.build_procurement_plan(analysis, selected_phase=payload.selected_phase)
        if (
            payload.include_live_quotes
            and str(procurement.get("status") or "").lower() == "ok"
            and procurement.get("selected_phase_key")
        ):
            selected_phase = next(
                (phase for phase in procurement.get("phase_packages", []) if phase.get("key") == procurement.get("selected_phase_key")),
                None,
            )
            live_quotes = []
            for item in (selected_phase or {}).get("items", [])[:4]:
                query = f"{item.get('quantity')} {item.get('unit')} {item.get('material')}".strip()
                quote_payload = await quote_service.quote_materials(query)
                live_quotes.append(
                    {
                        "material": item.get("material"),
                        "query": query,
                        "status": quote_payload.get("status"),
                        "message": quote_payload.get("message"),
                        "offers": quote_payload.get("offers", [])[:2],
                    }
                )
            procurement["live_quotes"] = live_quotes
            procurement["message"] = "Transformei a previsao em compra e puxei uma cotacao real inicial para a fase selecionada."
        return procurement
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
