from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..deps import get_current_actor, get_quote_service
from ..services.quote_service import QuoteService

router = APIRouter(prefix="/requests", tags=["requests"])


class SupplierReviewPayload(BaseModel):
    supplier_id: str = Field(min_length=1)
    price_rating: int | None = Field(default=None, ge=1, le=5)
    delivery_rating: int | None = Field(default=None, ge=1, le=5)
    service_rating: int | None = Field(default=None, ge=1, le=5)
    reliability_rating: int | None = Field(default=None, ge=1, le=5)
    comment: str = Field(default="", max_length=1000)


@router.get("/{request_id}/status")
def get_request_status(
    request_id: str,
    _: dict = Depends(get_current_actor),
    quote_service: QuoteService = Depends(get_quote_service),
) -> dict:
    try:
        return quote_service.get_request_status(request_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{request_id}/results")
def get_request_results(
    request_id: str,
    _: dict = Depends(get_current_actor),
    quote_service: QuoteService = Depends(get_quote_service),
) -> dict:
    try:
        return quote_service.get_request_results(request_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{request_id}/supplier-review")
def submit_supplier_review(
    request_id: str,
    payload: SupplierReviewPayload,
    actor: dict = Depends(get_current_actor),
    quote_service: QuoteService = Depends(get_quote_service),
) -> dict:
    try:
        return quote_service.submit_supplier_review(request_id=request_id, actor=actor, payload=payload.model_dump())
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
