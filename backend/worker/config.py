from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from .utils.logger import log_event

PROJECT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_DIR / "backend"
CONFIG_DIR = PROJECT_DIR / "config"
DATA_DIR = PROJECT_DIR / "data"

load_dotenv(dotenv_path=CONFIG_DIR / ".env", override=True)

for stream_name in ("stdout", "stderr"):
    stream = getattr(sys, stream_name, None)
    if stream and hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name, "1" if default else "0").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    debug: bool
    poll_seconds: int
    requests_per_cycle: int
    heartbeat_seconds: int
    timezone: str
    force_phone: str
    accept_from_me: bool
    healthcheck_timeout_seconds: int
    request_timeout_seconds: int
    retry_attempts: int
    retry_backoff_seconds: float
    supabase_url: str
    supabase_service_role_key: str
    supabase_schema: str
    worker_company_id: str
    waha_base_url: str
    waha_session: str
    waha_api_key: str
    waha_chats_limit: int
    mercado_livre_site: str
    groq_api_key: str
    groq_model: str
    groq_base_url: str
    test_mode: bool
    legacy_google_sheets_enabled: bool
    state_file: Path
    data_dir: Path
    catalog_json: Path
    catalog_csv: Path


def load_settings() -> Settings:
    return Settings(
        debug=_env_bool("DEBUG", True),
        poll_seconds=max(1, _env_int("POLL_SECONDS", 5)),
        requests_per_cycle=max(1, _env_int("REQUESTS_PER_CYCLE", 10)),
        heartbeat_seconds=max(15, _env_int("HEARTBEAT_SECONDS", 60)),
        timezone=os.getenv("TIMEZONE", "America/Sao_Paulo").strip() or "America/Sao_Paulo",
        force_phone=os.getenv("FORCE_PHONE", "").strip(),
        accept_from_me=_env_bool("ACCEPT_FROM_ME", False),
        healthcheck_timeout_seconds=max(1, _env_int("HEALTHCHECK_TIMEOUT_SECONDS", 10)),
        request_timeout_seconds=max(3, _env_int("REQUEST_TIMEOUT_SECONDS", 20)),
        retry_attempts=max(1, _env_int("RETRY_ATTEMPTS", 3)),
        retry_backoff_seconds=max(0.2, float(os.getenv("RETRY_BACKOFF_SECONDS", "1.5"))),
        supabase_url=os.getenv("SUPABASE_URL", "").strip().rstrip("/"),
        supabase_service_role_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip(),
        supabase_schema=os.getenv("SUPABASE_SCHEMA", "public").strip() or "public",
        worker_company_id=os.getenv("WORKER_COMPANY_ID", os.getenv("DEFAULT_COMPANY_ID", "")).strip(),
        waha_base_url=os.getenv("WAHA_BASE_URL", "http://localhost:3000").strip().rstrip("/"),
        waha_session=os.getenv("WAHA_SESSION", "default").strip() or "default",
        waha_api_key=os.getenv("WAHA_API_KEY", "").strip(),
        waha_chats_limit=max(1, _env_int("WAHA_CHATS_LIMIT", 25)),
        mercado_livre_site=os.getenv("MERCADO_LIVRE_SITE", "MLB").strip() or "MLB",
        groq_api_key=os.getenv("GROQ_API_KEY", "").strip(),
        groq_model=os.getenv("GROQ_MODEL", "llama-3.1-8b-instant").strip() or "llama-3.1-8b-instant",
        groq_base_url=os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1").strip().rstrip("/"),
        test_mode=_env_bool("TEST_MODE", False),
        legacy_google_sheets_enabled=_env_bool("LEGACY_GOOGLE_SHEETS_ENABLED", False),
        state_file=BACKEND_DIR / "state.json",
        data_dir=DATA_DIR,
        catalog_json=DATA_DIR / "catalog.json",
        catalog_csv=DATA_DIR / "catalog.csv",
    )


def validate_settings(settings: Settings) -> None:
    missing = []
    if not settings.supabase_url:
        missing.append("SUPABASE_URL")
    if not settings.supabase_service_role_key:
        missing.append("SUPABASE_SERVICE_ROLE_KEY")
    if not settings.waha_base_url:
        missing.append("WAHA_BASE_URL")
    if not settings.waha_session:
        missing.append("WAHA_SESSION")

    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")
