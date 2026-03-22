from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..deps import get_current_actor, get_project_service
from ..services.project_service import ProjectService

router = APIRouter(prefix="/projects", tags=["projects"])


class SaveProjectFromThreadPayload(BaseModel):
    thread_id: str = Field(min_length=1)
    name: str = Field(min_length=2, max_length=160)


@router.get("")
def list_projects(
    actor: dict = Depends(get_current_actor),
    project_service: ProjectService = Depends(get_project_service),
) -> dict:
    try:
        return project_service.list_projects(actor=actor)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{project_id}")
def get_project(
    project_id: str,
    actor: dict = Depends(get_current_actor),
    project_service: ProjectService = Depends(get_project_service),
) -> dict:
    try:
        return project_service.get_project(actor=actor, project_id=project_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/from-thread")
def save_project_from_thread(
    payload: SaveProjectFromThreadPayload,
    actor: dict = Depends(get_current_actor),
    project_service: ProjectService = Depends(get_project_service),
) -> dict:
    try:
        return project_service.save_project_from_thread(actor=actor, thread_id=payload.thread_id, name=payload.name)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
