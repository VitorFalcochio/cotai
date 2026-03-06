from __future__ import annotations

import json
from typing import Any

from .config import load_settings, validate_settings
from .services.supabase_service import SupabaseService
from .services.whatsapp_service import WhatsAppService


def run_bootstrap() -> int:
    settings = load_settings()
    report: dict[str, Any] = {"ok": False, "checks": {}}

    try:
        validate_settings(settings)
        report["checks"]["env"] = {"ok": True}
    except Exception as exc:  # noqa: BLE001
        report["checks"]["env"] = {"ok": False, "error": str(exc)}
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1

    supabase = SupabaseService(settings)
    whatsapp = WhatsAppService(settings)

    report["checks"]["supabase_connection"] = supabase.healthcheck()
    report["checks"]["waha_connection"] = whatsapp.healthcheck()

    required_tables = [
        "requests",
        "request_items",
        "quote_results",
        "request_quotes",
        "worker_processed_messages",
    ]
    table_checks: dict[str, Any] = {}
    for table in required_tables:
        table_checks[table] = {"ok": supabase.table_exists(table)}
    report["checks"]["tables"] = table_checks

    report["ok"] = (
        report["checks"]["env"].get("ok")
        and report["checks"]["supabase_connection"].get("ok")
        and report["checks"]["waha_connection"].get("ok")
        and all(check["ok"] for check in table_checks.values())
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(run_bootstrap())
