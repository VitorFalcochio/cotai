from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..deps import get_chat_service, get_current_actor
from ..services.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatMessagePayload(BaseModel):
    thread_id: str | None = None
    message: str = Field(min_length=1, max_length=4000)


class ChatConfirmPayload(BaseModel):
    thread_id: str
    items: list[str | dict[str, Any]] | None = None
    delivery_mode: str | None = None
    delivery_location: str | None = None
    notes: str | None = None
    priority: str | None = None


class ChatDraftPayload(BaseModel):
    title: str | None = Field(default=None, max_length=120)
    items: list[str | dict[str, Any]] = Field(default_factory=list)
    delivery_mode: str | None = Field(default=None, max_length=120)
    delivery_location: str | None = Field(default=None, max_length=240)
    notes: str | None = Field(default=None, max_length=2000)
    priority: str | None = Field(default=None, max_length=20)


@router.post("/message")
def post_chat_message(
    payload: ChatMessagePayload,
    actor: dict[str, Any] = Depends(get_current_actor),
    chat_service: ChatService = Depends(get_chat_service),
) -> dict[str, Any]:
    try:
        return chat_service.handle_message(actor=actor, thread_id=payload.thread_id, message=payload.message)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/confirm")
def confirm_chat_thread(
    payload: ChatConfirmPayload,
    actor: dict[str, Any] = Depends(get_current_actor),
    chat_service: ChatService = Depends(get_chat_service),
) -> dict[str, Any]:
    try:
        return chat_service.confirm_thread(
            actor=actor,
            thread_id=payload.thread_id,
            overrides={
                "items": payload.items,
                "delivery_mode": payload.delivery_mode,
                "delivery_location": payload.delivery_location,
                "notes": payload.notes,
                "priority": payload.priority,
            },
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/thread/{thread_id}/draft")
def update_chat_draft(
    thread_id: str,
    payload: ChatDraftPayload,
    actor: dict[str, Any] = Depends(get_current_actor),
    chat_service: ChatService = Depends(get_chat_service),
) -> dict[str, Any]:
    try:
        return chat_service.update_draft(
            actor=actor,
            thread_id=thread_id,
            draft_data=payload.model_dump(),
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/thread/{thread_id}")
def get_chat_thread(
    thread_id: str,
    actor: dict[str, Any] = Depends(get_current_actor),
    chat_service: ChatService = Depends(get_chat_service),
) -> dict[str, Any]:
    try:
        return chat_service.get_thread_payload(actor, thread_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=404, detail=str(exc)) from exc
