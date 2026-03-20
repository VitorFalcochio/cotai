from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..deps import get_current_admin, get_supabase
from ..services.supabase_service import SupabaseService
from ...worker.utils.telemetry import telemetry

router = APIRouter(prefix="/ops", tags=["ops"])


class ReprocessRequestPayload(BaseModel):
    reason: str = Field(min_length=5, max_length=500)


class ApproveRequestPayload(BaseModel):
    comment: str | None = Field(default=None, max_length=500)


@router.get("/overview")
def get_operations_overview(
    _: dict[str, Any] = Depends(get_current_admin),
    supabase: SupabaseService = Depends(get_supabase),
) -> dict[str, Any]:
    try:
        return supabase.get_operations_snapshot()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/telemetry")
def get_telemetry_snapshot(_: dict[str, Any] = Depends(get_current_admin)) -> dict[str, Any]:
    return telemetry.snapshot()


@router.post("/requests/{request_id}/reprocess")
def reprocess_request(
    request_id: str,
    payload: ReprocessRequestPayload,
    actor: dict[str, Any] = Depends(get_current_admin),
    supabase: SupabaseService = Depends(get_supabase),
) -> dict[str, Any]:
    try:
        return supabase.reprocess_request_as_admin(
            request_id=request_id,
            actor=actor,
            reason=payload.reason,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/requests/{request_id}/approve")
def approve_request(
    request_id: str,
    payload: ApproveRequestPayload,
    actor: dict[str, Any] = Depends(get_current_admin),
    supabase: SupabaseService = Depends(get_supabase),
) -> dict[str, Any]:
    try:
        return supabase.approve_request_as_admin(
            request_id=request_id,
            actor=actor,
            comment=payload.comment or "",
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc
