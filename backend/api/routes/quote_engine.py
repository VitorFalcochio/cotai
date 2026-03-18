from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..deps import get_current_actor, get_dynamic_quote_service
from ..services.dynamic_quote_service import DynamicQuoteService

router = APIRouter(tags=["search"])


class QuoteSearchPayload(BaseModel):
    query: str = Field(min_length=3, max_length=4000, description="Pedido de material em texto livre.")


class ConstructionEstimatePayload(BaseModel):
    query: str | None = Field(default=None, max_length=4000, description="Pedido em texto livre com area, sistema e padrao.")
    area_m2: float | None = Field(default=None, gt=0)
    building_standard: str | None = Field(default=None, max_length=40)
    system_type: str | None = Field(default=None, max_length=40)


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
