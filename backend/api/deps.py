from __future__ import annotations

from functools import lru_cache
from typing import Any

from fastapi import Depends, Header, HTTPException

from ..worker.config import Settings, load_settings
from ..worker.services.ai_service import AIService
from .services.chat_service import ChatService
from .services.quote_service import QuoteService
from .services.request_parser import RequestParserService
from .services.supabase_service import SupabaseService


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()


def get_supabase(settings: Settings = Depends(get_settings)) -> SupabaseService:
    return SupabaseService(settings)


def get_ai_service(settings: Settings = Depends(get_settings)) -> AIService:
    return AIService(settings)


def get_request_parser(ai_service: AIService = Depends(get_ai_service)) -> RequestParserService:
    return RequestParserService(ai_service)


def get_chat_service(
    supabase: SupabaseService = Depends(get_supabase),
    parser: RequestParserService = Depends(get_request_parser),
) -> ChatService:
    return ChatService(supabase, parser)


def get_quote_service(supabase: SupabaseService = Depends(get_supabase)) -> QuoteService:
    return QuoteService(supabase)


def get_current_actor(
    authorization: str | None = Header(default=None),
    supabase: SupabaseService = Depends(get_supabase),
) -> dict[str, Any]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token.")

    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token.")

    try:
        user = supabase.authenticate_user(token)
        profile = supabase.get_profile(user["id"])
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    if not profile:
        raise HTTPException(status_code=403, detail="Profile not found for authenticated user.")

    return {"user": user, "profile": profile, "access_token": token}


def get_current_admin(actor: dict[str, Any] = Depends(get_current_actor)) -> dict[str, Any]:
    role = str(actor.get("profile", {}).get("role") or "").lower()
    if role not in {"admin", "owner"}:
        raise HTTPException(status_code=403, detail="Admin access required.")
    return actor
