from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4
import requests
from ...api.services.plan_limits import get_plan_definition, normalize_plan_key
from ..config import Settings
from ..utils.retry import retry_call


REQUEST_PENDING_STATUSES = ("NEW", "RECEIVED", "PENDING_QUOTE")
REQUEST_PROCESSING_STATUSES = ("QUOTING", "PROCESSING")
APPROVAL_PENDING_STATUS = "AWAITING_APPROVAL"


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def normalize_priority(value: str | None) -> str:
    priority = str(value or "MEDIUM").strip().upper()
    if priority not in {"LOW", "MEDIUM", "HIGH", "URGENT"}:
        return "MEDIUM"
    return priority


def normalize_search_text(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def generate_request_code(now: datetime | None = None) -> str:
    current = now or datetime.now(UTC)
    return f"CT-{current.strftime('%y%m%d')}-{uuid4().hex[:6].upper()}"


def is_request_code_conflict_error(error: Exception) -> bool:
    message = str(error or "").strip().casefold()
    return (
        "requests_request_code_key" in message
        or ("duplicate key value" in message and "request_code" in message)
        or ("unique constraint" in message and "request_code" in message)
    )


class SupabaseService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.session = requests.Session()
        self.rest_url = f"{settings.supabase_url}/rest/v1"
        self.auth_url = f"{settings.supabase_url}/auth/v1"

    def _headers(self, prefer: str | None = None, token: str | None = None) -> dict[str, str]:
        bearer = token or self.settings.supabase_service_role_key
        headers = {
            "apikey": self.settings.supabase_service_role_key,
            "Authorization": f"Bearer {bearer}",
            "Content-Type": "application/json",
            "Accept-Profile": self.settings.supabase_schema,
            "Content-Profile": self.settings.supabase_schema,
        }
        if prefer:
            headers["Prefer"] = prefer
        return headers

    def _request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        timeout = kwargs.pop("timeout", self.settings.request_timeout_seconds)

        def do_request() -> requests.Response:
            response = self.session.request(method, url, timeout=timeout, **kwargs)
            if response.status_code in {408, 409, 425, 429, 500, 502, 503, 504}:
                response.raise_for_status()
            return response

        return retry_call(
            do_request,
            attempts=self.settings.retry_attempts,
            backoff_seconds=self.settings.retry_backoff_seconds,
            max_backoff_seconds=max(self.settings.retry_backoff_seconds, self.settings.request_timeout_seconds),
        )

    def close(self) -> None:
        self.session.close()

    def _table_url(self, table: str) -> str:
        return f"{self.rest_url}/{table}"

    def _list(self, table: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        response = self._request("GET", self._table_url(table), params=params, headers=self._headers())
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, list) else []

    def _maybe_single(self, table: str, params: dict[str, Any]) -> dict[str, Any] | None:
        rows = self._list(table, {**params, "limit": 1})
        return rows[0] if rows else None

    def _insert_rows(self, table: str, payload: dict[str, Any] | list[dict[str, Any]], prefer: str = "return=representation") -> list[dict[str, Any]]:
        response = self._request(
            "POST",
            self._table_url(table),
            headers=self._headers(prefer=prefer),
            json=payload,
        )
        response.raise_for_status()
        rows = response.json()
        return rows if isinstance(rows, list) else []

    def _count(self, table: str, params: dict[str, Any] | None = None) -> int:
        response = self._request(
            "GET",
            self._table_url(table),
            params={"select": "id", **(params or {})},
            headers={**self._headers(prefer="count=exact"), "Range": "0-0"},
            timeout=self.settings.healthcheck_timeout_seconds,
        )
        response.raise_for_status()
        content_range = response.headers.get("Content-Range", "")
        if "/" in content_range:
            try:
                return int(content_range.rsplit("/", 1)[1])
            except ValueError:
                return 0
        payload = response.json()
        return len(payload) if isinstance(payload, list) else 0

    def healthcheck(self) -> dict[str, Any]:
        checks: dict[str, Any] = {}
        try:
            auth_response = self._request(
                "GET",
                f"{self.auth_url}/settings",
                headers={"apikey": self.settings.supabase_service_role_key},
                timeout=self.settings.healthcheck_timeout_seconds,
            )
            checks["auth"] = {"ok": auth_response.ok, "status_code": auth_response.status_code}
        except Exception as exc:  # noqa: BLE001
            checks["auth"] = {"ok": False, "error": str(exc)}

        for table in (
            "requests",
            "request_items",
            "quote_results",
            "request_quotes",
            "worker_processed_messages",
            "chat_threads",
            "chat_messages",
            "supplier_price_snapshots",
        ):
            try:
                response = self._request(
                    "GET",
                    self._table_url(table),
                    params={"select": "*", "limit": 1},
                    headers=self._headers(),
                    timeout=self.settings.healthcheck_timeout_seconds,
                )
                checks[table] = {"ok": response.ok, "status_code": response.status_code}
            except Exception as exc:  # noqa: BLE001
                checks[table] = {"ok": False, "error": str(exc)}

        checks["ok"] = all(item.get("ok") for item in checks.values())
        return checks

    def table_exists(self, table: str) -> bool:
        try:
            response = self._request(
                "GET",
                self._table_url(table),
                params={"select": "*", "limit": 1},
                headers=self._headers(),
                timeout=self.settings.healthcheck_timeout_seconds,
            )
            return response.ok
        except Exception:
            return False

    def get_operations_snapshot(self) -> dict[str, Any]:
        today_iso = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()

        latest_heartbeat = self._maybe_single(
            "worker_heartbeats",
            {"select": "worker_name,status,details,created_at", "order": "created_at.desc"},
        )
        latest_request = self._maybe_single(
            "requests",
            {"select": "id,request_code,status,created_at,updated_at", "order": "created_at.desc"},
        )
        latest_quote = self._maybe_single(
            "request_quotes",
            {
                "select": "id,request_id,status,error_message,started_at,finished_at,created_at,updated_at",
                "order": "created_at.desc",
            },
        )
        recent_done_quotes = self._list(
            "request_quotes",
            {
                "select": "id,started_at,finished_at,created_at",
                "status": "eq.DONE",
                "finished_at": f"gte.{quote(today_iso)}",
                "order": "finished_at.desc",
                "limit": 25,
            },
        )

        avg_quote_minutes = None
        durations = []
        for row in recent_done_quotes:
            started_at = row.get("started_at")
            finished_at = row.get("finished_at")
            if not started_at or not finished_at:
                continue
            start_dt = datetime.fromisoformat(str(started_at).replace("Z", "+00:00"))
            finish_dt = datetime.fromisoformat(str(finished_at).replace("Z", "+00:00"))
            if finish_dt > start_dt:
                durations.append((finish_dt - start_dt).total_seconds() / 60)
        if durations:
            avg_quote_minutes = round(sum(durations) / len(durations), 2)

        last_heartbeat_at = latest_heartbeat.get("created_at") if latest_heartbeat else None
        worker_online = False
        if last_heartbeat_at:
            last_seen = datetime.fromisoformat(str(last_heartbeat_at).replace("Z", "+00:00"))
            worker_online = (datetime.now(UTC) - last_seen).total_seconds() < max(self.settings.heartbeat_seconds * 2, 120)

        health = self.healthcheck()
        failing_checks = [name for name, item in health.items() if isinstance(item, dict) and not item.get("ok")]

        return {
            "api": {
                "status": "online",
                "base_url": self.settings.api_base_url,
                "debug": self.settings.debug,
            },
            "supabase": {
                "status": "healthy" if health.get("ok") else "degraded",
                "ok": bool(health.get("ok")),
                "failing_checks": failing_checks,
            },
            "worker": {
                "status": "online" if worker_online else "offline",
                "last_heartbeat_at": last_heartbeat_at,
                "last_heartbeat_status": latest_heartbeat.get("status") if latest_heartbeat else None,
                "details": latest_heartbeat.get("details") if latest_heartbeat else {},
            },
            "queue": {
                "pending_requests": self._count("requests", {"status": f"in.({','.join(REQUEST_PENDING_STATUSES)})"}),
                "processing_requests": self._count("requests", {"status": f"in.({','.join(REQUEST_PROCESSING_STATUSES)})"}),
                "quotes_done_today": self._count("request_quotes", {"status": "eq.DONE", "finished_at": f"gte.{quote(today_iso)}"}),
                "quotes_error_today": self._count("request_quotes", {"status": "eq.ERROR", "updated_at": f"gte.{quote(today_iso)}"}),
                "average_quote_minutes_today": avg_quote_minutes,
            },
            "recent": {
                "request": latest_request,
                "quote": latest_quote,
            },
        }

    def authenticate_user(self, access_token: str) -> dict[str, Any]:
        response = self._request(
            "GET",
            f"{self.auth_url}/user",
            headers=self._headers(token=access_token),
            timeout=self.settings.healthcheck_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or not payload.get("id"):
            raise RuntimeError("Supabase auth did not return a valid user payload.")
        return payload

    def get_profile(self, user_id: str) -> dict[str, Any] | None:
        return self._maybe_single("profiles", {"select": "*", "id": f"eq.{user_id}"})

    def get_company(self, company_id: str) -> dict[str, Any] | None:
        if not company_id or not self.table_exists("companies"):
            return None
        return self._maybe_single("companies", {"select": "*", "id": f"eq.{company_id}"})

    def get_company_active_subscription(self, company_id: str) -> dict[str, Any] | None:
        if not company_id or not self.table_exists("billing_subscriptions"):
            return None
        rows = self._list(
            "billing_subscriptions",
            {
                "select": "*",
                "company_id": f"eq.{company_id}",
                "order": "updated_at.desc,created_at.desc",
                "limit": 10,
            },
        )
        if not rows:
            return None
        preferred_statuses = {"active", "trial", "trialing", "paid", "past_due", "upgrade_pending"}
        for row in rows:
            status = str(row.get("status") or "").strip().casefold()
            if status in preferred_statuses:
                return row
        return rows[0]

    def list_company_profiles(self, company_id: str) -> list[dict[str, Any]]:
        if not company_id:
            return []
        return self._list("profiles", {"select": "*", "company_id": f"eq.{company_id}", "limit": 500})

    def count_company_active_profiles(self, company_id: str) -> int:
        inactive_statuses = {"inactive", "disabled", "blocked"}
        profiles = self.list_company_profiles(company_id)
        return sum(1 for profile in profiles if str(profile.get("status") or "active").strip().casefold() not in inactive_statuses)

    def count_company_requests_in_current_month(self, company_id: str) -> int:
        if not company_id:
            return 0
        month_start = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
        return self._count("requests", {"company_id": f"eq.{company_id}", "created_at": f"gte.{month_start}"})

    def get_company_plan_context(self, company_id: str, profile: dict[str, Any] | None = None) -> dict[str, Any]:
        company = self.get_company(company_id)
        subscription = self.get_company_active_subscription(company_id)
        raw_plan = company.get("plan") if company else None
        source = "company"
        if not raw_plan and subscription:
            raw_plan = subscription.get("plan")
            source = "billing_subscription"
        if not raw_plan and profile:
            raw_plan = profile.get("plan")
            source = "profile"
        if not raw_plan:
            raw_plan = "silver"
            source = "default"

        plan_key = normalize_plan_key(raw_plan)
        definition = get_plan_definition(plan_key)
        requests_used = self.count_company_requests_in_current_month(company_id)
        active_users = self.count_company_active_profiles(company_id)
        company_status = str((company or {}).get("status") or "active").strip().casefold()

        return {
            "plan_key": plan_key,
            "plan_label": definition["label"],
            "plan_tagline": definition.get("tagline"),
            "monthly_price": definition.get("monthly_price"),
            "billing_enabled": self.settings.billing_enabled,
            "plan_limits_enforced": self.settings.enforce_plan_limits,
            "request_limit": definition["request_limit"],
            "user_limit": definition["user_limit"],
            "supplier_limit": definition.get("supplier_limit"),
            "history_days": definition.get("history_days"),
            "csv_imports_per_month": definition.get("csv_imports_per_month"),
            "support_level": definition.get("support_level"),
            "recommended": bool(definition.get("recommended")),
            "requests_used": requests_used,
            "active_users": active_users,
            "company_status": company_status,
            "source": source,
            "company": company,
            "subscription": subscription,
        }

    def assert_company_can_create_request(self, company_id: str, profile: dict[str, Any] | None = None) -> dict[str, Any]:
        context = self.get_company_plan_context(company_id, profile=profile)
        plan_label = context["plan_label"]
        request_limit = context["request_limit"]
        user_limit = context["user_limit"]

        if context["company_status"] in {"inactive", "disabled", "blocked"}:
            raise RuntimeError("Sua empresa esta bloqueada para novas cotacoes no momento. Verifique o status do plano.")

        if not self.settings.enforce_plan_limits:
            return context

        if user_limit is not None and context["active_users"] > user_limit:
            raise RuntimeError(
                f"O plano {plan_label} permite ate {user_limit} usuario(s) ativo(s). "
                "Reduza a equipe ativa ou faca upgrade para continuar criando pedidos."
            )

        if request_limit is not None and context["requests_used"] >= request_limit:
            raise RuntimeError(
                f"O plano {plan_label} atingiu o limite de {request_limit} pedido(s) neste mes. "
                "Faca upgrade para continuar usando a Cotai sem bloqueio."
            )

        return context

    def get_request_by_id(self, request_id: Any) -> dict[str, Any] | None:
        return self._maybe_single("requests", {"select": "*", "id": f"eq.{request_id}"})

    def get_request_by_code(self, request_code: str) -> dict[str, Any] | None:
        return self._maybe_single("requests", {"select": "*", "request_code": f"eq.{request_code}"})

    def infer_request_defaults(
        self,
        *,
        notes: str,
        items: list[dict[str, Any]],
        priority: str | None = None,
    ) -> dict[str, Any]:
        normalized_priority = normalize_priority(priority)
        if priority is None:
            text = notes.casefold()
            if any(token in text for token in ("urgente", "hoje", "amanha", "amanhã", "imediat")):
                normalized_priority = "URGENT"
            elif any(token in text for token in ("rapido", "rápido", "prioridade", "sexta")):
                normalized_priority = "HIGH"

        now = datetime.now(UTC)
        hours_by_priority = {"LOW": 72, "MEDIUM": 48, "HIGH": 24, "URGENT": 8}
        sla_due_at = (now + timedelta(hours=hours_by_priority[normalized_priority])).isoformat()
        approval_required = normalized_priority in {"HIGH", "URGENT"} or len(items) >= 5
        approval_status = "PENDING" if approval_required else "NOT_REQUIRED"
        status = APPROVAL_PENDING_STATUS if approval_required else "PENDING_QUOTE"
        return {
            "priority": normalized_priority,
            "sla_due_at": sla_due_at,
            "approval_required": approval_required,
            "approval_status": approval_status,
            "status": status,
        }

    def find_duplicate_request(
        self,
        *,
        company_id: str,
        items: list[dict[str, Any]],
        limit: int = 25,
    ) -> dict[str, Any] | None:
        candidate_requests = self._list(
            "requests",
            {
                "select": "id,request_code,status,created_at,priority,sla_due_at,approval_status,duplicate_of_request_id",
                "company_id": f"eq.{company_id}",
                "order": "created_at.desc",
                "limit": limit,
            },
        )
        if not candidate_requests:
            return None

        request_ids = [row["id"] for row in candidate_requests if row.get("id")]
        if not request_ids:
            return None

        request_items = self._list(
            "request_items",
            {
                "select": "request_id,item_name,description",
                "request_id": f"in.({','.join(str(item) for item in request_ids)})",
                "limit": 500,
            },
        )
        normalized_target = {
            str(item.get("normalized_name") or item.get("name") or item.get("raw") or "").strip().casefold()
            for item in items
            if str(item.get("normalized_name") or item.get("name") or item.get("raw") or "").strip()
        }
        if not normalized_target:
            return None

        item_map: dict[str, set[str]] = {}
        for row in request_items:
            item_map.setdefault(str(row.get("request_id")), set()).add(
                str(row.get("item_name") or row.get("description") or "").strip().casefold()
            )

        best_match = None
        best_score = 0.0
        for candidate in candidate_requests:
            candidate_id = str(candidate.get("id"))
            normalized_candidate = {item for item in item_map.get(candidate_id, set()) if item}
            if not normalized_candidate:
                continue
            overlap = normalized_target.intersection(normalized_candidate)
            union = normalized_target.union(normalized_candidate)
            score = len(overlap) / len(union) if union else 0.0
            if score > best_score:
                best_score = score
                best_match = candidate

        if best_match and best_score >= 0.6:
            return {
                "request_id": best_match.get("id"),
                "request_code": best_match.get("request_code"),
                "status": best_match.get("status"),
                "created_at": best_match.get("created_at"),
                "score": round(best_score, 2),
            }
        return None

    def create_admin_audit_log(
        self,
        *,
        company_id: str | None,
        actor_id: str | None,
        actor_email: str | None,
        event_type: str,
        description: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        if not self.table_exists("admin_audit_logs"):
            return None
        rows = self._insert_rows(
            "admin_audit_logs",
            {
                "company_id": company_id,
                "actor_id": actor_id,
                "actor_email": actor_email,
                "event_type": event_type,
                "description": description,
                "metadata": metadata or {},
                "created_at": utc_now_iso(),
            },
        )
        return rows[0] if rows else None

    def safe_create_admin_audit_log(self, **kwargs: Any) -> None:
        try:
            self.create_admin_audit_log(**kwargs)
        except Exception:
            return

    def list_recent_request_item_names(self, *, company_id: str | None = None, limit: int = 100) -> list[str]:
        rows = self._list(
            "request_items",
            {
                "select": "item_name,request_id,created_at",
                "order": "created_at.desc",
                "limit": max(1, limit * 3),
            },
        )
        if company_id:
            request_rows = self._list(
                "requests",
                {
                    "select": "id",
                    "company_id": f"eq.{company_id}",
                    "order": "created_at.desc",
                    "limit": max(1, limit * 3),
                },
            )
            request_ids = {str(row.get("id")) for row in request_rows if row.get("id")}
            rows = [row for row in rows if str(row.get("request_id")) in request_ids]

        unique: list[str] = []
        seen: set[str] = set()
        for row in rows:
            item_name = str(row.get("item_name") or "").strip()
            normalized = normalize_search_text(item_name)
            if not item_name or normalized in seen:
                continue
            seen.add(normalized)
            unique.append(item_name)
        return unique[:limit]

    def insert_supplier_price_snapshots(self, rows: list[dict[str, Any]]) -> None:
        if not rows or not self.table_exists("supplier_price_snapshots"):
            return
        response = self._request(
            "POST",
            self._table_url("supplier_price_snapshots"),
            headers=self._headers(prefer="return=minimal"),
            json=rows,
        )
        response.raise_for_status()

    def get_latest_supplier_price_snapshots(
        self,
        *,
        item_name: str,
        company_id: str | None = None,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        if not self.table_exists("supplier_price_snapshots"):
            return []

        params = {
            "select": "*",
            "normalized_item_name": f"eq.{normalize_search_text(item_name)}",
            "order": "captured_at.desc",
            "limit": max(1, limit * 3),
        }
        if company_id:
            params["or"] = f"(company_id.eq.{company_id},company_id.is.null)"

        rows = self._list("supplier_price_snapshots", params)
        deduped: list[dict[str, Any]] = []
        seen: set[tuple[str, str, Any]] = set()
        for row in rows:
            key = (
                str(row.get("supplier_name") or "").strip().casefold(),
                str(row.get("title") or "").strip().casefold(),
                row.get("unit_price") if row.get("unit_price") is not None else row.get("price"),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(row)
        return deduped[:limit]

    def find_or_create_supplier(
        self,
        *,
        company_id: str | None,
        supplier_name: str,
        source_name: str | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any] | None:
        supplier_name = str(supplier_name or "").strip()
        if not supplier_name or not company_id or not self.table_exists("suppliers"):
            return None
        existing = self._maybe_single(
            "suppliers",
            {
                "select": "*",
                "company_id": f"eq.{company_id}",
                "name": f"eq.{supplier_name}",
            },
        )
        if existing:
            return existing
        try:
            rows = self._insert_rows(
                "suppliers",
                {
                    "company_id": company_id,
                    "name": supplier_name,
                    "region": source_name,
                    "material_tags": tags or [],
                    "status": "active",
                    "created_at": utc_now_iso(),
                    "updated_at": utc_now_iso(),
                },
            )
            return rows[0] if rows else None
        except Exception:
            return None

    def update_supplier_rollup(
        self,
        *,
        supplier_id: str | None,
        delivery_days: int | None = None,
        value_score: float | None = None,
    ) -> None:
        if not supplier_id or not self.table_exists("suppliers"):
            return
        supplier = self._maybe_single("suppliers", {"select": "*", "id": f"eq.{supplier_id}"})
        if not supplier:
            return
        participation = int(supplier.get("quote_participation_count") or 0) + 1
        avg_delivery = supplier.get("average_delivery_days")
        avg_score = supplier.get("average_price_score")

        def rolling_average(current: Any, incoming: float | int | None) -> Any:
            if incoming is None:
                return current
            current_value = float(current) if current is not None else None
            if current_value is None:
                return incoming
            return round(((current_value * (participation - 1)) + float(incoming)) / participation, 2)

        self.update_supplier(supplier_id, {
            "quote_participation_count": participation,
            "average_delivery_days": rolling_average(avg_delivery, delivery_days),
            "average_price_score": rolling_average(avg_score, value_score),
        })

    def update_supplier(self, supplier_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        response = self._request(
            "PATCH",
            self._table_url("suppliers"),
            params={"id": f"eq.{supplier_id}"},
            headers=self._headers(prefer="return=representation"),
            json={"updated_at": utc_now_iso(), **payload},
        )
        response.raise_for_status()
        rows = response.json()
        return rows[0] if isinstance(rows, list) and rows else None

    def create_supplier_review(
        self,
        *,
        supplier_id: str,
        request_id: str,
        company_id: str | None,
        reviewer_user_id: str | None,
        price_rating: int | None,
        delivery_rating: int | None,
        service_rating: int | None,
        reliability_rating: int | None,
        comment: str,
    ) -> dict[str, Any] | None:
        if not self.table_exists("supplier_reviews"):
            return None
        rows = self._insert_rows(
            "supplier_reviews",
            {
                "supplier_id": supplier_id,
                "request_id": request_id,
                "company_id": company_id,
                "reviewer_user_id": reviewer_user_id,
                "price_rating": price_rating,
                "delivery_rating": delivery_rating,
                "service_rating": service_rating,
                "reliability_rating": reliability_rating,
                "comment": comment,
                "created_at": utc_now_iso(),
            },
        )
        self.refresh_supplier_rating(supplier_id)
        return rows[0] if rows else None

    def refresh_supplier_rating(self, supplier_id: str) -> None:
        if not self.table_exists("supplier_reviews") or not self.table_exists("suppliers"):
            return
        rows = self._list(
            "supplier_reviews",
            {"select": "price_rating,delivery_rating,service_rating,reliability_rating", "supplier_id": f"eq.{supplier_id}", "limit": 200},
        )
        scores: list[float] = []
        for row in rows:
            ratings = [row.get("price_rating"), row.get("delivery_rating"), row.get("service_rating"), row.get("reliability_rating")]
            numeric = [float(item) for item in ratings if isinstance(item, (int, float))]
            if numeric:
                scores.append(sum(numeric) / len(numeric))
        average_rating = round(sum(scores) / len(scores), 2) if scores else None
        self.update_supplier(supplier_id, {"average_rating": average_rating})

    def create_project(
        self,
        *,
        company_id: str,
        created_by_user_id: str | None,
        name: str,
        location: str | None,
        notes: str | None,
    ) -> dict[str, Any] | None:
        if not self.table_exists("projects") or not company_id or not name:
            return None
        existing = self._maybe_single(
            "projects",
            {"select": "*", "company_id": f"eq.{company_id}", "name": f"eq.{name}"},
        )
        if existing:
            return existing
        rows = self._insert_rows(
            "projects",
            {
                "company_id": company_id,
                "name": name,
                "location": location,
                "notes": notes,
                "created_by_user_id": created_by_user_id,
                "created_at": utc_now_iso(),
                "updated_at": utc_now_iso(),
            },
        )
        return rows[0] if rows else None

    def upsert_project_materials(
        self,
        *,
        project_id: str | None,
        request_id: str,
        items: list[dict[str, Any]],
        status: str,
    ) -> None:
        if not project_id or not self.table_exists("project_materials"):
            return
        for item in items:
            material_name = str(item.get("normalized_name") or item.get("name") or item.get("raw") or "").strip()
            if not material_name:
                continue
            existing = self._maybe_single(
                "project_materials",
                {"select": "*", "project_id": f"eq.{project_id}", "material_name": f"eq.{material_name}"},
            )
            quantity = item.get("quantity")
            payload = {
                "project_id": project_id,
                "request_id": request_id,
                "material_name": material_name,
                "estimated_qty": quantity,
                "pending_qty": quantity,
                "status": status,
                "updated_at": utc_now_iso(),
            }
            if existing:
                self._request(
                    "PATCH",
                    self._table_url("project_materials"),
                    params={"id": f"eq.{existing['id']}"},
                    headers=self._headers(prefer="return=minimal"),
                    json=payload,
                ).raise_for_status()
            else:
                self._insert_rows("project_materials", {**payload, "created_at": utc_now_iso()})

    def record_price_history(self, rows: list[dict[str, Any]]) -> None:
        if not rows or not self.table_exists("price_history"):
            return
        try:
            self._request(
                "POST",
                self._table_url("price_history"),
                headers=self._headers(prefer="return=minimal"),
                json=rows,
            ).raise_for_status()
        except Exception:
            return

    def get_project_materials(self, project_id: str | None) -> list[dict[str, Any]]:
        if not project_id or not self.table_exists("project_materials"):
            return []
        return self._list(
            "project_materials",
            {
                "select": "*",
                "project_id": f"eq.{project_id}",
                "limit": 200,
            },
        )

    def get_price_history(self, *, request_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        if not request_id or not self.table_exists("price_history"):
            return []
        return self._list(
            "price_history",
            {
                "select": "*",
                "request_id": f"eq.{request_id}",
                "order": "captured_at.asc",
                "limit": limit,
            },
        )

    def get_project_events(self, project_id: str | None, limit: int = 50) -> list[dict[str, Any]]:
        if not project_id or not self.table_exists("project_events"):
            return []
        return self._list(
            "project_events",
            {
                "select": "*",
                "project_id": f"eq.{project_id}",
                "order": "created_at.desc",
                "limit": limit,
            },
        )

    def record_project_event(
        self,
        *,
        project_id: str,
        request_id: str | None,
        created_by_user_id: str | None,
        event_type: str,
        material_name: str | None = None,
        quantity: float | None = None,
        stage_label: str | None = None,
        supplier_name: str | None = None,
        note: str | None = None,
        impact_level: str = "info",
    ) -> dict[str, Any] | None:
        if not project_id or not self.table_exists("project_events"):
            return None
        rows = self._insert_rows(
            "project_events",
            {
                "project_id": project_id,
                "request_id": request_id,
                "event_type": event_type,
                "material_name": material_name,
                "quantity": quantity,
                "stage_label": stage_label,
                "supplier_name": supplier_name,
                "note": note,
                "impact_level": impact_level,
                "created_by_user_id": created_by_user_id,
                "created_at": utc_now_iso(),
            },
        )
        return rows[0] if rows else None

    def apply_project_execution_event(
        self,
        *,
        request_id: str,
        actor: dict[str, Any],
        event_type: str,
        material_name: str | None = None,
        quantity: float | None = None,
        stage_label: str | None = None,
        supplier_name: str | None = None,
        note: str | None = None,
    ) -> dict[str, Any]:
        request_row = self.get_request_by_id(request_id)
        if not request_row:
            raise RuntimeError("Request not found.")
        project_id = request_row.get("project_id")
        if not project_id:
            raise RuntimeError("Este pedido ainda nao esta vinculado a um projeto.")

        impact_level = "info"
        if event_type == "supplier_delay":
            impact_level = "warning"
        elif event_type == "stage_completed":
            impact_level = "success"

        material_row = None
        if material_name:
            material_row = self._maybe_single(
                "project_materials",
                {"select": "*", "project_id": f"eq.{project_id}", "material_name": f"eq.{material_name}"},
            )

        if event_type in {"material_received", "material_consumed", "purchase_executed"} and material_name and not material_row:
            payload = {
                "project_id": project_id,
                "request_id": request_id,
                "material_name": material_name,
                "estimated_qty": quantity,
                "purchased_qty": 0,
                "received_qty": 0,
                "consumed_qty": 0,
                "pending_qty": quantity,
                "status": "pending",
                "supplier_name": supplier_name,
                "last_event_type": event_type,
                "last_event_note": note,
                "last_event_at": utc_now_iso(),
                "created_at": utc_now_iso(),
                "updated_at": utc_now_iso(),
            }
            rows = self._insert_rows("project_materials", payload)
            material_row = rows[0] if rows else None

        if material_row:
            purchased_qty = float(material_row.get("purchased_qty") or 0)
            received_qty = float(material_row.get("received_qty") or 0)
            consumed_qty = float(material_row.get("consumed_qty") or 0)
            pending_qty = float(material_row.get("pending_qty") or 0)
            qty = float(quantity or 0)

            if event_type == "purchase_executed":
                purchased_qty += qty
                pending_qty = max(0.0, pending_qty - qty)
            elif event_type == "material_received":
                received_qty += qty
            elif event_type == "material_consumed":
                consumed_qty += qty

            status = str(material_row.get("status") or "pending")
            if event_type == "supplier_delay":
                status = "delayed"
            elif event_type == "stage_completed":
                status = "done"
            elif pending_qty <= 0 and purchased_qty > 0:
                status = "purchased"
            elif received_qty > 0:
                status = "received"
            elif purchased_qty > 0:
                status = "quoted"

            self._request(
                "PATCH",
                self._table_url("project_materials"),
                params={"id": f"eq.{material_row['id']}"},
                headers=self._headers(prefer="return=minimal"),
                json={
                    "purchased_qty": purchased_qty,
                    "received_qty": received_qty,
                    "consumed_qty": consumed_qty,
                    "pending_qty": pending_qty,
                    "status": status,
                    "supplier_name": supplier_name or material_row.get("supplier_name"),
                    "last_event_type": event_type,
                    "last_event_note": note,
                    "last_event_at": utc_now_iso(),
                    "updated_at": utc_now_iso(),
                },
            ).raise_for_status()

        if event_type == "stage_completed" and self.table_exists("projects"):
            self._request(
                "PATCH",
                self._table_url("projects"),
                params={"id": f"eq.{project_id}"},
                headers=self._headers(prefer="return=minimal"),
                json={"stage": stage_label or "execution", "updated_at": utc_now_iso()},
            ).raise_for_status()

        event_row = self.record_project_event(
            project_id=project_id,
            request_id=request_id,
            created_by_user_id=actor.get("user", {}).get("id"),
            event_type=event_type,
            material_name=material_name,
            quantity=quantity,
            stage_label=stage_label,
            supplier_name=supplier_name,
            note=note,
            impact_level=impact_level,
        )
        return {
            "ok": True,
            "event": event_row,
            "message": "Evento operacional registrado na obra.",
        }

    def create_internal_request(
        self,
        *,
        company_id: str,
        user_id: str,
        thread_id: str | None,
        customer_name: str,
        notes: str,
        items: list[dict[str, Any]],
        delivery_mode: str | None = None,
        delivery_location: str | None = None,
        project_name: str | None = None,
        priority: str | None = None,
        sla_due_at: str | None = None,
        approval_required: bool | None = None,
        approval_status: str | None = None,
        status: str | None = None,
        duplicate_of_request_id: str | None = None,
        duplicate_score: float | None = None,
    ) -> dict[str, Any]:
        self.assert_company_can_create_request(company_id)
        project_row = self.create_project(
            company_id=company_id,
            created_by_user_id=user_id,
            name=project_name or customer_name,
            location=delivery_location,
            notes=notes,
        )
        rows: list[dict[str, Any]] = []
        last_error: Exception | None = None
        request_code = ""

        for _attempt in range(5):
            request_code = generate_request_code()
            payload = {
                "request_code": request_code,
                "company_id": company_id,
                "project_id": project_row.get("id") if project_row else None,
                "requested_by_user_id": user_id,
                "chat_thread_id": thread_id,
                "customer_name": customer_name,
                "delivery_mode": delivery_mode,
                "delivery_location": delivery_location,
                "notes": notes,
                "status": status or "PENDING_QUOTE",
                "source_channel": "INTERNAL_CHAT",
                "updated_at": utc_now_iso(),
                "priority": normalize_priority(priority),
                "sla_due_at": sla_due_at,
                "approval_required": approval_required if approval_required is not None else False,
                "approval_status": approval_status or "NOT_REQUIRED",
                "duplicate_of_request_id": duplicate_of_request_id,
                "duplicate_score": duplicate_score,
            }
            payload_variants = [
                payload,
                {key: value for key, value in payload.items() if key not in {"project_id", "duplicate_of_request_id", "duplicate_score"}},
                {key: value for key, value in payload.items() if key not in {"project_id", "priority", "sla_due_at", "approval_required", "approval_status", "duplicate_of_request_id", "duplicate_score"}},
            ]
            should_retry_with_new_code = False

            for payload_variant in payload_variants:
                try:
                    rows = self._insert_rows("requests", payload_variant)
                    if rows:
                        break
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
                    if is_request_code_conflict_error(exc):
                        should_retry_with_new_code = True
                        break

            if rows:
                break
            if should_retry_with_new_code:
                continue
            if last_error is not None:
                raise last_error

        if not rows:
            if last_error is not None:
                raise last_error
            raise RuntimeError("Supabase did not return the inserted internal request.")
        request_row = rows[0]
        self.insert_request_items(request_row["id"], items)
        self.upsert_project_materials(
            project_id=project_row.get("id") if project_row else request_row.get("project_id"),
            request_id=request_row["id"],
            items=items,
            status="quoted" if request_row.get("status") == "DONE" else "pending",
        )
        if thread_id:
            thread_status = "PROCESSING" if request_row.get("status") != APPROVAL_PENDING_STATUS else APPROVAL_PENDING_STATUS
            self.update_chat_thread(thread_id, {"request_id": request_row["id"], "status": thread_status})
        self.safe_create_admin_audit_log(
            company_id=company_id,
            actor_id=user_id,
            actor_email=None,
            event_type="request_created",
            description=f"Pedido {request_code} criado pelo chatbot interno.",
            metadata={
                "request_id": request_row["id"],
                "request_code": request_code,
                "thread_id": thread_id,
                "item_count": len(items),
                "source_channel": "INTERNAL_CHAT",
                "priority": request_row.get("priority"),
                "approval_status": request_row.get("approval_status"),
                "duplicate_of_request_id": duplicate_of_request_id,
            },
        )
        return request_row

    def update_request(self, request_id: Any, payload: dict[str, Any]) -> dict[str, Any] | None:
        merged_payload = {"updated_at": utc_now_iso(), **payload}
        response = self._request(
            "PATCH",
            self._table_url("requests"),
            params={"id": f"eq.{request_id}"},
            headers=self._headers(prefer="return=representation"),
            json=merged_payload,
        )
        response.raise_for_status()
        rows = response.json()
        return rows[0] if isinstance(rows, list) and rows else None

    def fetch_pending_requests(self, limit: int) -> list[dict[str, Any]]:
        status_filter = ",".join(REQUEST_PENDING_STATUSES)
        return self._list(
            "requests",
            {
                "select": "*",
                "status": f"in.({status_filter})",
                "order": "created_at.asc",
                "limit": limit,
            },
        )

    def claim_request(self, request_id: Any) -> dict[str, Any] | None:
        allowed = ",".join(REQUEST_PENDING_STATUSES)
        response = self._request(
            "PATCH",
            self._table_url("requests"),
            params={"id": f"eq.{request_id}", "status": f"in.({allowed})"},
            headers=self._headers(prefer="return=representation"),
            json={"status": "PROCESSING", "updated_at": utc_now_iso()},
        )
        response.raise_for_status()
        rows = response.json()
        return rows[0] if isinstance(rows, list) and rows else None

    def get_request_items(self, request_id: Any) -> list[dict[str, Any]]:
        return self._list(
            "request_items",
            {"select": "*", "request_id": f"eq.{request_id}", "order": "line_number.asc.nullslast"},
        )

    def insert_request_items(self, request_id: Any, items: list[dict[str, Any]] | list[str]) -> None:
        normalized_items: list[dict[str, Any]] = []
        for index, item in enumerate(items, start=1):
            if isinstance(item, dict):
                item_name = str(item.get("normalized_name") or item.get("name") or item.get("item_name") or item.get("description") or item.get("raw") or "").strip()
                raw_text = str(item.get("raw") or item_name).strip()
                normalized_items.append(
                    {
                        "request_id": request_id,
                        "item_name": item_name or raw_text,
                        "description": raw_text or item_name,
                        "raw_text": raw_text or item_name,
                        "qty": item.get("quantity"),
                        "unit": item.get("unit"),
                        "line_number": index,
                    }
                )
            else:
                raw_text = str(item).strip()
                normalized_items.append(
                    {
                        "request_id": request_id,
                        "item_name": raw_text,
                        "description": raw_text,
                        "raw_text": raw_text,
                        "line_number": index,
                    }
                )

        payload_variants = [
            normalized_items,
            [
                {
                    "request_id": row["request_id"],
                    "item_name": row["item_name"],
                    "description": row["description"],
                    "line_number": row["line_number"],
                }
                for row in normalized_items
            ],
            [
                {
                    "request_id": row["request_id"],
                    "item_name": row["item_name"],
                    "line_number": row["line_number"],
                }
                for row in normalized_items
            ],
        ]

        last_error: Exception | None = None
        for payload in payload_variants:
            try:
                response = self._request(
                    "POST",
                    self._table_url("request_items"),
                    headers=self._headers(prefer="return=minimal"),
                    json=payload,
                )
                response.raise_for_status()
                return
            except Exception as exc:  # noqa: BLE001
                last_error = exc

        if last_error is not None:
            raise last_error

    def ensure_request_items(self, request_id: Any, items: list[dict[str, Any]] | list[str]) -> None:
        existing = self.get_request_items(request_id)
        existing_names = {
            str(item.get("item_name") or item.get("description") or "").strip().casefold()
            for item in existing
            if str(item.get("item_name") or item.get("description") or "").strip()
        }
        pending: list[dict[str, Any]] | list[str] = []
        for item in items:
            if isinstance(item, dict):
                item_name = str(item.get("normalized_name") or item.get("name") or item.get("item_name") or item.get("description") or item.get("raw") or "").strip()
                if item_name and item_name.casefold() not in existing_names:
                    pending.append(item)
            else:
                item_name = str(item).strip()
                if item_name and item_name.casefold() not in existing_names:
                    pending.append(item_name)
        if pending:
            self.insert_request_items(request_id, pending)

    def is_message_processed(self, message_id: str) -> bool:
        rows = self._list(
            "worker_processed_messages",
            {"select": "message_id", "message_id": f"eq.{message_id}", "limit": 1},
        )
        return len(rows) > 0

    def record_processed_message(
        self,
        message_id: str,
        chat_id: str,
        request_id: Any | None,
        request_quote_id: Any | None,
        payload_hash: str,
        processing_status: str,
        notes: str = "",
    ) -> None:
        response = self._request(
            "POST",
            self._table_url("worker_processed_messages"),
            headers=self._headers(prefer="return=minimal,resolution=ignore-duplicates"),
            json={
                "message_id": message_id,
                "chat_id": chat_id,
                "request_id": request_id,
                "request_quote_id": request_quote_id,
                "payload_hash": payload_hash,
                "processing_status": processing_status,
                "notes": notes,
                "created_at": utc_now_iso(),
            },
        )
        response.raise_for_status()

    def get_latest_quote_execution(self, request_id: Any) -> dict[str, Any] | None:
        return self._maybe_single(
            "request_quotes",
            {"select": "*", "request_id": f"eq.{request_id}", "order": "created_at.desc"},
        )

    def create_quote_execution(self, request_id: Any, status: str = "RECEIVED") -> dict[str, Any]:
        response = self._request(
            "POST",
            self._table_url("request_quotes"),
            headers=self._headers(prefer="return=representation"),
            json={
                "request_id": request_id,
                "status": status,
                "started_at": utc_now_iso(),
                "created_at": utc_now_iso(),
                "updated_at": utc_now_iso(),
            },
        )
        response.raise_for_status()
        rows = response.json()
        if not isinstance(rows, list) or not rows:
            raise RuntimeError("Supabase did not return the inserted request quote execution.")
        return rows[0]

    def get_or_create_active_quote_execution(self, request_id: Any) -> dict[str, Any]:
        latest = self.get_latest_quote_execution(request_id)
        if latest and latest.get("status") in {"RECEIVED", "QUOTING"}:
            return latest
        return self.create_quote_execution(request_id=request_id, status="RECEIVED")

    def update_quote_execution(self, request_quote_id: Any, payload: dict[str, Any]) -> dict[str, Any] | None:
        merged_payload = {"updated_at": utc_now_iso(), **payload}
        response = self._request(
            "PATCH",
            self._table_url("request_quotes"),
            params={"id": f"eq.{request_quote_id}"},
            headers=self._headers(prefer="return=representation"),
            json=merged_payload,
        )
        response.raise_for_status()
        rows = response.json()
        return rows[0] if isinstance(rows, list) and rows else None

    def replace_quote_results(self, request_id: Any, request_quote_id: Any, quote_results: list[dict[str, Any]]) -> None:
        delete_response = self._request(
            "DELETE",
            self._table_url("quote_results"),
            params={"request_quote_id": f"eq.{request_quote_id}"},
            headers=self._headers(prefer="return=minimal"),
        )
        delete_response.raise_for_status()

        request_row = self.get_request_by_id(request_id) or {}
        request_items = self.get_request_items(request_id)
        item_map = {
            str(item.get("item_name") or item.get("description") or "").strip().casefold(): item
            for item in request_items
        }

        rows = []
        price_history_rows = []
        position = 0
        for item_result in quote_results:
            item_name = item_result.get("item_name", "")
            item_row = item_map.get(str(item_name).strip().casefold(), {})
            quantity = item_row.get("qty")
            try:
                quantity_value = float(quantity) if quantity is not None else 1.0
            except (TypeError, ValueError):
                quantity_value = 1.0
            source_name = offer_source = item_result.get("source")
            for offer in item_result.get("offers", []):
                position += 1
                supplier_name = str(offer.get("supplier") or "Fornecedor").strip()
                supplier = self.find_or_create_supplier(
                    company_id=request_row.get("company_id"),
                    supplier_name=supplier_name,
                    source_name=str(offer.get("source") or item_result.get("source") or "").strip() or None,
                    tags=[item_name] if item_name else [],
                )
                price = offer.get("price")
                try:
                    price_value = float(price) if price is not None else None
                except (TypeError, ValueError):
                    price_value = None
                delivery_days = self._infer_delivery_days(offer, offer_source)
                total_price = round(price_value * quantity_value, 2) if price_value is not None else None
                value_score = self._compute_value_score(price_value, delivery_days)
                rows.append(
                    {
                        "request_id": request_id,
                        "request_quote_id": request_quote_id,
                        "item_name": item_name,
                        "title": offer.get("title"),
                        "supplier": supplier_name,
                        "supplier_name": supplier_name,
                        "supplier_id": supplier.get("id") if supplier else None,
                        "price": price,
                        "unit_price": price_value,
                        "total_price": total_price,
                        "link": offer.get("link"),
                        "result_url": offer.get("link"),
                        "source": offer.get("source") or item_result.get("source"),
                        "source_name": offer.get("source") or item_result.get("source"),
                        "origin_label": offer.get("source") or item_result.get("source"),
                        "delivery_days": delivery_days,
                        "delivery_label": f"{delivery_days} dia(s)" if delivery_days is not None else "Não informado",
                        "value_score": value_score,
                        "category": item_row.get("unit"),
                        "position": position,
                        "raw_payload": offer,
                    }
                )
                price_history_rows.append(
                    {
                        "request_id": request_id,
                        "request_quote_id": request_quote_id,
                        "supplier_id": supplier.get("id") if supplier else None,
                        "supplier_name": supplier_name,
                        "item_name": item_name,
                        "source_name": offer.get("source") or item_result.get("source"),
                        "price": price_value,
                        "unit_price": price_value,
                        "total_price": total_price,
                        "captured_at": utc_now_iso(),
                    }
                )
                self.update_supplier_rollup(
                    supplier_id=supplier.get("id") if supplier else None,
                    delivery_days=delivery_days,
                    value_score=value_score,
                )

        if not rows:
            return

        rows = self._mark_best_offers(rows)

        payload_variants = [
            rows,
            [
                {
                    "request_id": row["request_id"],
                    "request_quote_id": row["request_quote_id"],
                    "item_name": row["item_name"],
                    "title": row["title"],
                    "supplier_name": row["supplier_name"],
                    "price": row["price"],
                    "unit_price": row.get("unit_price"),
                    "total_price": row.get("total_price"),
                    "result_url": row["result_url"],
                    "source_name": row["source_name"],
                    "delivery_days": row.get("delivery_days"),
                    "delivery_label": row.get("delivery_label"),
                    "origin_label": row.get("origin_label"),
                    "value_score": row.get("value_score"),
                    "supplier_id": row.get("supplier_id"),
                    "is_best_price": row.get("is_best_price"),
                    "is_best_delivery": row.get("is_best_delivery"),
                    "is_best_overall": row.get("is_best_overall"),
                    "category": row.get("category"),
                    "position": row["position"],
                    "raw_payload": row["raw_payload"],
                }
                for row in rows
            ],
        ]

        last_error: Exception | None = None
        for payload in payload_variants:
            try:
                response = self._request(
                    "POST",
                    self._table_url("quote_results"),
                    headers=self._headers(prefer="return=minimal"),
                    json=payload,
                )
                response.raise_for_status()
                return
            except Exception as exc:  # noqa: BLE001
                last_error = exc

        if last_error is not None:
            raise last_error
        self.record_price_history(price_history_rows)

    def get_quote_results(self, request_id: Any) -> list[dict[str, Any]]:
        return self._list(
            "quote_results",
            {"select": "*", "request_id": f"eq.{request_id}", "order": "position.asc.nullslast,created_at.asc"},
        )

    def complete_quote_execution(
        self,
        request_quote_id: Any,
        status: str,
        response_text: str = "",
        source_summary: str = "",
        error_message: str = "",
    ) -> None:
        payload = {
            "status": status,
            "finished_at": utc_now_iso(),
            "response_text": response_text or None,
            "source_summary": source_summary or None,
            "error_message": error_message or None,
        }
        self.update_quote_execution(request_quote_id, payload)

    def record_heartbeat(self, worker_name: str, status: str, details: dict[str, Any] | None = None) -> None:
        response = self._request(
            "POST",
            self._table_url("worker_heartbeats"),
            headers=self._headers(prefer="return=minimal"),
            json={
                "worker_name": worker_name,
                "status": status,
                "details": details or {},
                "created_at": utc_now_iso(),
            },
        )
        response.raise_for_status()

    def create_chat_thread(
        self,
        *,
        user_id: str,
        company_id: str,
        title: str,
        status: str = "DRAFT",
        request_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        response = self._request(
            "POST",
            self._table_url("chat_threads"),
            headers=self._headers(prefer="return=representation"),
            json={
                "user_id": user_id,
                "company_id": company_id,
                "title": title,
                "status": status,
                "request_id": request_id,
                "metadata": metadata or {},
            },
        )
        response.raise_for_status()
        rows = response.json()
        if not isinstance(rows, list) or not rows:
            raise RuntimeError("Supabase did not return the inserted chat thread.")
        return rows[0]

    def get_chat_thread(self, thread_id: str, user_id: str | None = None) -> dict[str, Any] | None:
        params = {"select": "*", "id": f"eq.{thread_id}"}
        if user_id:
            params["user_id"] = f"eq.{user_id}"
        return self._maybe_single("chat_threads", params)

    def update_chat_thread(self, thread_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        response = self._request(
            "PATCH",
            self._table_url("chat_threads"),
            params={"id": f"eq.{thread_id}"},
            headers=self._headers(prefer="return=representation"),
            json={"updated_at": utc_now_iso(), **payload},
        )
        response.raise_for_status()
        rows = response.json()
        return rows[0] if isinstance(rows, list) and rows else None

    def list_chat_messages(self, thread_id: str) -> list[dict[str, Any]]:
        return self._list("chat_messages", {"select": "*", "thread_id": f"eq.{thread_id}", "order": "created_at.asc"})

    def insert_chat_message(
        self,
        thread_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        response = self._request(
            "POST",
            self._table_url("chat_messages"),
            headers=self._headers(prefer="return=representation"),
            json={
                "thread_id": thread_id,
                "role": role,
                "content": content,
                "metadata": metadata or {},
            },
        )
        response.raise_for_status()
        rows = response.json()
        if not isinstance(rows, list) or not rows:
            raise RuntimeError("Supabase did not return the inserted chat message.")
        return rows[0]

    def get_request_status_payload(self, request_id: str) -> dict[str, Any]:
        request_row = self.get_request_by_id(request_id)
        if request_row is None:
            raise RuntimeError("Request not found.")
        latest_quote = self.get_latest_quote_execution(request_id)
        results = self.get_quote_results(request_id)
        comparison = self.build_quote_comparison(results)
        project_materials = self.get_project_materials(request_row.get("project_id"))
        price_history = self.get_price_history(request_id=str(request_id))
        project_events = self.get_project_events(request_row.get("project_id"))
        return {
            "request": request_row,
            "latest_quote": latest_quote,
            "results": results,
            "items": self.get_request_items(request_id),
            "comparison": comparison,
            "project_materials": project_materials,
            "price_history": price_history,
            "project_events": project_events,
        }

    def reprocess_request_as_admin(self, request_id: str, actor: dict[str, Any], reason: str) -> dict[str, Any]:
        request_row = self.get_request_by_id(request_id)
        if request_row is None:
            raise RuntimeError("Request not found.")

        current_status = str(request_row.get("status") or "").upper()
        if current_status in {"PROCESSING", "QUOTING"}:
            raise RuntimeError("Este pedido ja esta em processamento.")

        latest_quote = self.get_latest_quote_execution(request_id)
        updated_request = self.update_request(
            request_id,
            {
                "status": "NEW",
                "last_error": None,
                "processed_at": None,
            },
        )
        if latest_quote and latest_quote.get("status") in {"RECEIVED", "QUOTING", "DONE", "ERROR"}:
            self.update_quote_execution(
                latest_quote["id"],
                {
                    "status": "REQUEUED",
                    "error_message": f"Reprocessado manualmente: {reason[:300]}",
                    "finished_at": utc_now_iso(),
                },
            )

        self.safe_create_admin_audit_log(
            company_id=request_row.get("company_id"),
            actor_id=actor.get("user", {}).get("id"),
            actor_email=actor.get("user", {}).get("email"),
            event_type="request_reprocess_requested",
            description=f"Pedido {request_row.get('request_code') or request_id} reenfileirado manualmente.",
            metadata={
                "request_id": request_id,
                "request_code": request_row.get("request_code"),
                "previous_status": current_status,
                "reason": reason,
                "latest_quote_id": latest_quote.get("id") if latest_quote else None,
            },
        )
        return {
            "request_id": request_id,
            "status": updated_request.get("status") if updated_request else "NEW",
            "previous_status": current_status,
            "message": "Pedido reenfileirado com seguranca.",
        }

    def approve_request_as_admin(self, request_id: str, actor: dict[str, Any], comment: str = "") -> dict[str, Any]:
        request_row = self.get_request_by_id(request_id)
        if request_row is None:
            raise RuntimeError("Request not found.")
        if not request_row.get("approval_required"):
            raise RuntimeError("Este pedido não exige aprovação.")
        if str(request_row.get("approval_status") or "").upper() == "APPROVED":
            raise RuntimeError("Este pedido ja foi aprovado.")

        updated = self.update_request(
            request_id,
            {
                "status": "NEW",
                "approval_status": "APPROVED",
                "approved_at": utc_now_iso(),
                "approved_by_user_id": actor.get("user", {}).get("id"),
            },
        )
        self.safe_create_admin_audit_log(
            company_id=request_row.get("company_id"),
            actor_id=actor.get("user", {}).get("id"),
            actor_email=actor.get("user", {}).get("email"),
            event_type="request_approved",
            description=f"Pedido {request_row.get('request_code') or request_id} aprovado para cotação.",
            metadata={
                "request_id": request_id,
                "request_code": request_row.get("request_code"),
                "comment": comment,
            },
        )
        return {
            "request_id": request_id,
            "status": updated.get("status") if updated else "NEW",
            "approval_status": "APPROVED",
            "message": "Pedido aprovado e reenfileirado para cotação.",
        }

    def _infer_delivery_days(self, offer: dict[str, Any], source_name: Any) -> int | None:
        if isinstance(offer.get("delivery_days"), (int, float)):
            return int(offer["delivery_days"])
        source = str(source_name or offer.get("source") or "").lower()
        if "catalog" in source:
            return 2
        if "mercado" in source:
            return 5
        return 4

    def _compute_value_score(self, price_value: float | None, delivery_days: int | None) -> float | None:
        if price_value is None:
            return None
        delivery_factor = delivery_days or 5
        return round(1000 / (price_value * max(delivery_factor, 1)), 4)

    def _mark_best_offers(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            grouped.setdefault(str(row.get("item_name") or ""), []).append(row)

        for item_rows in grouped.values():
            best_price_row = min(
                item_rows,
                key=lambda row: row.get("unit_price") if row.get("unit_price") is not None else float("inf"),
            )
            best_delivery_row = min(
                item_rows,
                key=lambda row: row.get("delivery_days") if row.get("delivery_days") is not None else float("inf"),
            )
            best_overall_row = max(
                item_rows,
                key=lambda row: row.get("value_score") if row.get("value_score") is not None else float("-inf"),
            )
            for row in item_rows:
                row["is_best_price"] = row is best_price_row
                row["is_best_delivery"] = row is best_delivery_row
                row["is_best_overall"] = row is best_overall_row
        return rows

    def build_quote_comparison(self, results: list[dict[str, Any]]) -> dict[str, Any]:
        suppliers: dict[str, dict[str, Any]] = {}
        for row in results:
            supplier = str(row.get("supplier_name") or row.get("supplier") or row.get("source_name") or "Fornecedor").strip()
            price = row.get("total_price") if row.get("total_price") is not None else row.get("price")
            try:
                price_value = float(price)
            except (TypeError, ValueError):
                price_value = None
            delivery_days = row.get("delivery_days")
            try:
                delivery_value = int(delivery_days) if delivery_days is not None else None
            except (TypeError, ValueError):
                delivery_value = None
            supplier_entry = suppliers.setdefault(
                supplier,
                {
                    "supplier": supplier,
                    "supplier_id": row.get("supplier_id"),
                    "items": 0,
                    "total_price": 0.0,
                    "average_delivery_days": None,
                    "value_score": 0.0,
                    "best_price_count": 0,
                    "best_delivery_count": 0,
                    "best_overall_count": 0,
                },
            )
            supplier_entry["items"] += 1
            if price_value is not None:
                supplier_entry["total_price"] += price_value
            if delivery_value is not None:
                if supplier_entry["average_delivery_days"] is None:
                    supplier_entry["average_delivery_days"] = delivery_value
                else:
                    supplier_entry["average_delivery_days"] = round((supplier_entry["average_delivery_days"] + delivery_value) / 2, 2)
            supplier_entry["value_score"] += float(row.get("value_score") or 0)
            supplier_entry["best_price_count"] += 1 if row.get("is_best_price") else 0
            supplier_entry["best_delivery_count"] += 1 if row.get("is_best_delivery") else 0
            supplier_entry["best_overall_count"] += 1 if row.get("is_best_overall") else 0

        ranked = sorted(
            suppliers.values(),
            key=lambda item: (
                item["total_price"] or float("inf"),
                item["average_delivery_days"] if item["average_delivery_days"] is not None else float("inf"),
                -item["best_overall_count"],
            ),
        )
        best_price = min(ranked, key=lambda item: item["total_price"] or float("inf")) if ranked else None
        best_delivery = min(
            ranked,
            key=lambda item: item["average_delivery_days"] if item["average_delivery_days"] is not None else float("inf"),
        ) if ranked else None
        return {
            "supplier_count": len(ranked),
            "best_supplier": ranked[0] if ranked else None,
            "best_price_supplier": best_price,
            "best_delivery_supplier": best_delivery,
            "potential_savings": round((ranked[-1]["total_price"] - ranked[0]["total_price"]), 2) if len(ranked) >= 2 else 0,
            "suppliers": ranked[:5],
        }

    def append_assistant_message_for_request(self, request_id: str, content: str, metadata: dict[str, Any] | None = None) -> None:
        request_row = self.get_request_by_id(request_id)
        if not request_row:
            return
        thread_id = request_row.get("chat_thread_id")
        if not thread_id:
            return
        self.insert_chat_message(thread_id, "assistant", content, metadata)

    def mark_request_received(self, request_id: Any) -> None:
        self.update_request(request_id, {"status": "RECEIVED"})

    def mark_request_quoting(self, request_id: Any) -> None:
        self.update_request(request_id, {"status": "PROCESSING"})

    def mark_request_error(self, request_id: Any, error_message: str) -> None:
        request_row = self.update_request(request_id, {"status": "ERROR", "last_error": error_message[:500]})
        if request_row and request_row.get("chat_thread_id"):
            self.update_chat_thread(request_row["chat_thread_id"], {"status": "ERROR"})
        if request_row:
            self.safe_create_admin_audit_log(
                company_id=request_row.get("company_id"),
                actor_id=None,
                actor_email="worker@cotai.local",
                event_type="request_error",
                description=f"Pedido {request_row.get('request_code') or request_id} falhou no worker.",
                metadata={
                    "request_id": request_row.get("id"),
                    "request_code": request_row.get("request_code"),
                    "error_message": error_message[:500],
                    "status": "ERROR",
                },
            )

    def mark_request_done(self, request_id: Any) -> None:
        request_row = self.update_request(
            request_id,
            {
                "status": "DONE",
                "last_error": None,
                "processed_at": utc_now_iso(),
            },
        )
        if request_row and request_row.get("chat_thread_id"):
            self.update_chat_thread(request_row["chat_thread_id"], {"status": "DONE"})
        if request_row:
            self.safe_create_admin_audit_log(
                company_id=request_row.get("company_id"),
                actor_id=None,
                actor_email="worker@cotai.local",
                event_type="request_completed",
                description=f"Pedido {request_row.get('request_code') or request_id} concluido pelo worker.",
                metadata={
                    "request_id": request_row.get("id"),
                    "request_code": request_row.get("request_code"),
                    "status": "DONE",
                },
            )
