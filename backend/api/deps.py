from __future__ import annotations

from functools import lru_cache
from typing import Any

from fastapi import Depends, Header, HTTPException

from ..worker.config import Settings, load_settings
from ..worker.services.ai_service import AIService
from ..worker.services.search_service import SearchService
from .services.chat_service import ChatService
from .services.construction_brain_service import ConstructionBrainService
from .services.construction_execution_insight_service import ConstructionExecutionInsightService
from .services.conversation_intelligence_service import ConversationIntelligenceService
from .services.construction_mode_service import ConstructionModeService
from .services.dynamic_quote_service import DynamicQuoteService
from .services.dynamic_search_engine import SearchEngine
from .services.material_extraction_service import MaterialExtractionService
from .services.parametric_budget_service import ParametricBudgetService
from .services.project_service import ProjectService
from .services.quote_service import QuoteService
from .services.request_parser import RequestParserService
from .services.search_cache_service import SearchCacheService
from .services.supabase_service import SupabaseService


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()


def get_supabase(settings: Settings = Depends(get_settings)) -> SupabaseService:
    return SupabaseService(settings)


def get_ai_service(settings: Settings = Depends(get_settings)) -> AIService:
    return AIService(settings)


@lru_cache(maxsize=1)
def get_search_cache() -> SearchCacheService:
    return SearchCacheService()


def get_request_parser(ai_service: AIService = Depends(get_ai_service)) -> RequestParserService:
    return RequestParserService(ai_service)


def get_conversation_intelligence_service() -> ConversationIntelligenceService:
    return ConversationIntelligenceService()


def get_construction_brain_service() -> ConstructionBrainService:
    return ConstructionBrainService()


def get_construction_execution_insight_service() -> ConstructionExecutionInsightService:
    return ConstructionExecutionInsightService()


def get_material_extractor(
    settings: Settings = Depends(get_settings),
    ai_service: AIService = Depends(get_ai_service),
) -> MaterialExtractionService:
    return MaterialExtractionService(settings, ai_service)


def get_search_engine(settings: Settings = Depends(get_settings)) -> SearchEngine:
    return SearchEngine(settings)


def get_historical_search_service(settings: Settings = Depends(get_settings)) -> SearchService:
    return SearchService(settings)


def get_parametric_budget_service() -> ParametricBudgetService:
    return ParametricBudgetService()


def get_construction_mode_service(
    settings: Settings = Depends(get_settings),
    fallback_search: SearchService = Depends(get_historical_search_service),
    ai_service: AIService = Depends(get_ai_service),
) -> ConstructionModeService:
    return ConstructionModeService(settings, fallback_search, ai_service)


def get_dynamic_quote_service(
    settings: Settings = Depends(get_settings),
    extractor: MaterialExtractionService = Depends(get_material_extractor),
    search_engine: SearchEngine = Depends(get_search_engine),
    fallback_search: SearchService = Depends(get_historical_search_service),
    cache: SearchCacheService = Depends(get_search_cache),
    budget_service: ParametricBudgetService = Depends(get_parametric_budget_service),
) -> DynamicQuoteService:
    return DynamicQuoteService(settings, extractor, search_engine, cache, budget_service, fallback_search)


def get_project_service(supabase: SupabaseService = Depends(get_supabase)) -> ProjectService:
    return ProjectService(supabase)


def get_chat_service(
    supabase: SupabaseService = Depends(get_supabase),
    parser: RequestParserService = Depends(get_request_parser),
    construction_service: ConstructionModeService = Depends(get_construction_mode_service),
    intelligence_service: ConversationIntelligenceService = Depends(get_conversation_intelligence_service),
    brain_service: ConstructionBrainService = Depends(get_construction_brain_service),
    execution_insight_service: ConstructionExecutionInsightService = Depends(get_construction_execution_insight_service),
    project_service: ProjectService = Depends(get_project_service),
) -> ChatService:
    return ChatService(
        supabase,
        parser,
        construction_service,
        intelligence_service,
        brain_service,
        execution_insight_service,
        project_service,
    )


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
