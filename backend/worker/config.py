from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

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
    healthcheck_timeout_seconds: int
    request_timeout_seconds: int
    retry_attempts: int
    retry_backoff_seconds: float
    supabase_url: str
    supabase_service_role_key: str
    supabase_schema: str
    worker_company_id: str
    api_host: str
    api_port: int
    api_base_url: str
    mercado_livre_site: str
    gemini_api_key: str
    gemini_model: str
    gemini_base_url: str
    groq_api_key: str
    groq_model: str
    groq_base_url: str
    test_mode: bool
    legacy_google_sheets_enabled: bool
    state_file: Path
    data_dir: Path
    catalog_json: Path
    catalog_csv: Path
    price_sources_json: Path
    search_cache_ttl_seconds: int
    scraping_headless: bool
    scraping_timeout_ms: int
    scraping_max_offers_per_store: int


def load_settings() -> Settings:
    api_host = os.getenv("API_HOST", "127.0.0.1").strip() or "127.0.0.1"
    api_port = max(1, _env_int("API_PORT", 8000))
    return Settings(
        debug=_env_bool("DEBUG", True),
        poll_seconds=max(1, _env_int("POLL_SECONDS", 5)),
        requests_per_cycle=max(1, _env_int("REQUESTS_PER_CYCLE", 10)),
        heartbeat_seconds=max(15, _env_int("HEARTBEAT_SECONDS", 60)),
        timezone=os.getenv("TIMEZONE", "America/Sao_Paulo").strip() or "America/Sao_Paulo",
        healthcheck_timeout_seconds=max(1, _env_int("HEALTHCHECK_TIMEOUT_SECONDS", 10)),
        request_timeout_seconds=max(3, _env_int("REQUEST_TIMEOUT_SECONDS", 20)),
        retry_attempts=max(1, _env_int("RETRY_ATTEMPTS", 3)),
        retry_backoff_seconds=max(0.2, float(os.getenv("RETRY_BACKOFF_SECONDS", "1.5"))),
        supabase_url=os.getenv("SUPABASE_URL", "").strip().rstrip("/"),
        supabase_service_role_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip(),
        supabase_schema=os.getenv("SUPABASE_SCHEMA", "public").strip() or "public",
        worker_company_id=os.getenv("WORKER_COMPANY_ID", os.getenv("DEFAULT_COMPANY_ID", "")).strip(),
        api_host=api_host,
        api_port=api_port,
        api_base_url=os.getenv("API_BASE_URL", f"http://{api_host}:{api_port}").strip().rstrip("/"),
        mercado_livre_site=os.getenv("MERCADO_LIVRE_SITE", "MLB").strip() or "MLB",
        gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip(),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash",
        gemini_base_url=os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta").strip().rstrip("/"),
        groq_api_key=os.getenv("GROQ_API_KEY", "").strip(),
        groq_model=os.getenv("GROQ_MODEL", "llama-3.1-8b-instant").strip() or "llama-3.1-8b-instant",
        groq_base_url=os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1").strip().rstrip("/"),
        test_mode=_env_bool("TEST_MODE", False),
        legacy_google_sheets_enabled=_env_bool("LEGACY_GOOGLE_SHEETS_ENABLED", False),
        state_file=BACKEND_DIR / "state.json",
        data_dir=DATA_DIR,
        catalog_json=DATA_DIR / "catalog.json",
        catalog_csv=DATA_DIR / "catalog.csv",
        price_sources_json=DATA_DIR / "price_sources.json",
        search_cache_ttl_seconds=max(60, _env_int("SEARCH_CACHE_TTL_SECONDS", 86400)),
        scraping_headless=_env_bool("SCRAPING_HEADLESS", True),
        scraping_timeout_ms=max(2000, _env_int("SCRAPING_TIMEOUT_MS", 20000)),
        scraping_max_offers_per_store=max(1, _env_int("SCRAPING_MAX_OFFERS_PER_STORE", 6)),
    )


def validate_settings(settings: Settings) -> None:
    missing = []
    if not settings.supabase_url:
        missing.append("SUPABASE_URL")
    if not settings.supabase_service_role_key:
        missing.append("SUPABASE_SERVICE_ROLE_KEY")

    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")
