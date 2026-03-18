from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from ..api.services.plan_limits import get_plan_definition, normalize_plan_key


@dataclass
class InMemorySupabase:
    requests: dict[str, dict[str, Any]] = field(default_factory=dict)
    requests_by_id: dict[str, dict[str, Any]] = field(default_factory=dict)
    request_items: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    request_quotes: dict[str, dict[str, Any]] = field(default_factory=dict)
    quote_results: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    processed_messages: set[str] = field(default_factory=set)
    heartbeats: list[dict[str, Any]] = field(default_factory=list)
    chat_threads: dict[str, dict[str, Any]] = field(default_factory=dict)
    chat_messages: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    profiles: dict[str, dict[str, Any]] = field(default_factory=lambda: {
        "user-1": {
            "id": "user-1",
            "email": "user@example.com",
            "full_name": "User Test",
            "company_name": "Cotai Teste",
            "company_id": "company-1",
            "plan": "silver",
            "role": "owner",
            "status": "active",
        }
    })
    companies: dict[str, dict[str, Any]] = field(default_factory=lambda: {
        "company-1": {
            "id": "company-1",
            "name": "Cotai Teste",
            "plan": "silver",
            "status": "active",
        }
    })
    billing_subscriptions: list[dict[str, Any]] = field(default_factory=list)
    admin_audit_logs: list[dict[str, Any]] = field(default_factory=list)
    suppliers: dict[str, dict[str, Any]] = field(default_factory=dict)
    supplier_reviews: list[dict[str, Any]] = field(default_factory=list)
    projects: dict[str, dict[str, Any]] = field(default_factory=dict)
    project_materials: list[dict[str, Any]] = field(default_factory=list)
    price_history: list[dict[str, Any]] = field(default_factory=list)
    _request_counter: int = 0
    _quote_counter: int = 0
    _thread_counter: int = 0
    _message_counter: int = 0

    def healthcheck(self) -> dict[str, Any]:
        return {"ok": True}

    def close(self) -> None:
        return None

    def authenticate_user(self, access_token: str) -> dict[str, Any]:
        return {"id": "user-1", "email": "user@example.com"}

    def get_profile(self, user_id: str) -> dict[str, Any] | None:
        return self.profiles.get(user_id)

    def get_company(self, company_id: str) -> dict[str, Any] | None:
        return self.companies.get(company_id)

    def get_company_active_subscription(self, company_id: str) -> dict[str, Any] | None:
        matches = [row for row in self.billing_subscriptions if row.get("company_id") == company_id]
        if not matches:
            return None
        preferred_statuses = {"active", "trial", "trialing", "paid", "past_due", "upgrade_pending"}
        for row in reversed(matches):
            status = str(row.get("status") or "").strip().casefold()
            if status in preferred_statuses:
                return row
        return matches[-1]

    def list_company_profiles(self, company_id: str) -> list[dict[str, Any]]:
        return [profile for profile in self.profiles.values() if profile.get("company_id") == company_id]

    def count_company_active_profiles(self, company_id: str) -> int:
        inactive_statuses = {"inactive", "disabled", "blocked"}
        return sum(1 for profile in self.list_company_profiles(company_id) if str(profile.get("status") or "active").casefold() not in inactive_statuses)

    def count_company_requests_in_current_month(self, company_id: str) -> int:
        month_start = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        total = 0
        for row in self.requests_by_id.values():
            if row.get("company_id") != company_id:
                continue
            created_at = row.get("created_at")
            if not created_at:
                total += 1
                continue
            try:
                created_at_value = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
            except ValueError:
                total += 1
                continue
            if created_at_value >= month_start:
                total += 1
        return total

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
        return {
            "plan_key": plan_key,
            "plan_label": definition["label"],
            "plan_tagline": definition.get("tagline"),
            "monthly_price": definition.get("monthly_price"),
            "request_limit": definition["request_limit"],
            "user_limit": definition["user_limit"],
            "supplier_limit": definition.get("supplier_limit"),
            "history_days": definition.get("history_days"),
            "csv_imports_per_month": definition.get("csv_imports_per_month"),
            "support_level": definition.get("support_level"),
            "recommended": bool(definition.get("recommended")),
            "requests_used": self.count_company_requests_in_current_month(company_id),
            "active_users": self.count_company_active_profiles(company_id),
            "company_status": str((company or {}).get("status") or "active").casefold(),
            "source": source,
            "company": company,
            "subscription": subscription,
        }

    def assert_company_can_create_request(self, company_id: str, profile: dict[str, Any] | None = None) -> dict[str, Any]:
        context = self.get_company_plan_context(company_id, profile=profile)
        if context["company_status"] in {"inactive", "disabled", "blocked"}:
            raise RuntimeError("Sua empresa esta bloqueada para novas cotacoes no momento. Verifique o status do plano.")
        if context["user_limit"] is not None and context["active_users"] > context["user_limit"]:
            raise RuntimeError(
                f"O plano {context['plan_label']} permite ate {context['user_limit']} usuario(s) ativo(s). "
                "Reduza a equipe ativa ou faca upgrade para continuar criando pedidos."
            )
        if context["request_limit"] is not None and context["requests_used"] >= context["request_limit"]:
            raise RuntimeError(
                f"O plano {context['plan_label']} atingiu o limite de {context['request_limit']} pedido(s) neste mes. "
                "Faca upgrade para continuar usando a Cotai sem bloqueio."
            )
        return context

    def get_request_by_id(self, request_id: Any) -> dict[str, Any] | None:
        return self.requests_by_id.get(str(request_id))

    def get_request_by_code(self, request_code: str) -> dict[str, Any] | None:
        return self.requests.get(request_code)

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
        profile = self.get_profile(user_id)
        self.assert_company_can_create_request(company_id, profile=profile)
        self._request_counter += 1
        request_id = f"req-{self._request_counter}"
        request_code = f"CT-{1000 + self._request_counter}"
        created_at = datetime.now(UTC).isoformat()
        project = self.create_project(
            company_id=company_id,
            created_by_user_id=user_id,
            name=project_name or customer_name,
            location=delivery_location,
            notes=notes,
        )
        row = {
            "id": request_id,
            "request_code": request_code,
            "company_id": company_id,
            "project_id": project["id"] if project else None,
            "requested_by_user_id": user_id,
            "chat_thread_id": thread_id,
            "customer_name": customer_name,
            "delivery_mode": delivery_mode,
            "delivery_location": delivery_location,
            "notes": notes,
            "status": status or "PENDING_QUOTE",
            "source_channel": "INTERNAL_CHAT",
            "priority": priority or "MEDIUM",
            "sla_due_at": sla_due_at,
            "approval_required": approval_required if approval_required is not None else False,
            "approval_status": approval_status or "NOT_REQUIRED",
            "duplicate_of_request_id": duplicate_of_request_id,
            "duplicate_score": duplicate_score,
            "created_at": created_at,
        }
        self.requests[request_code] = row
        self.requests_by_id[request_id] = row
        self.insert_request_items(request_id, items)
        self.upsert_project_materials(
            project_id=row.get("project_id"),
            request_id=request_id,
            items=items,
            status="quoted" if row["status"] == "DONE" else "pending_quote",
        )
        if thread_id:
            self.update_chat_thread(thread_id, {"request_id": request_id, "status": "PROCESSING" if row["status"] != "AWAITING_APPROVAL" else "AWAITING_APPROVAL"})
        return row

    def infer_request_defaults(self, *, notes: str, items: list[dict[str, Any]], priority: str | None = None) -> dict[str, Any]:
        normalized_priority = str(priority or "MEDIUM").upper()
        if priority is None and "urgente" in notes.casefold():
            normalized_priority = "URGENT"
        approval_required = normalized_priority in {"HIGH", "URGENT"} or len(items) >= 5
        return {
            "priority": normalized_priority,
            "sla_due_at": (datetime.now(UTC) + timedelta(hours=24 if normalized_priority in {"HIGH", "URGENT"} else 48)).isoformat(),
            "approval_required": approval_required,
            "approval_status": "PENDING" if approval_required else "NOT_REQUIRED",
            "status": "AWAITING_APPROVAL" if approval_required else "PENDING_QUOTE",
        }

    def find_duplicate_request(self, *, company_id: str, items: list[dict[str, Any]], limit: int = 25) -> dict[str, Any] | None:
        target = {
            str(item.get("normalized_name") or item.get("name") or item.get("raw") or "").strip().casefold()
            for item in items
            if str(item.get("normalized_name") or item.get("name") or item.get("raw") or "").strip()
        }
        best = None
        best_score = 0.0
        for row in self.requests_by_id.values():
            if row.get("company_id") != company_id:
                continue
            candidate_items = {
                str(item.get("item_name") or item.get("description") or "").strip().casefold()
                for item in self.get_request_items(row["id"])
            }
            if not candidate_items:
                continue
            overlap = target.intersection(candidate_items)
            union = target.union(candidate_items)
            score = len(overlap) / len(union) if union else 0.0
            if score > best_score:
                best_score = score
                best = row
        if best and best_score >= 0.6:
            return {"request_id": best["id"], "request_code": best["request_code"], "status": best["status"], "score": round(best_score, 2)}
        return None

    def update_request(self, request_id: Any, payload: dict[str, Any]) -> dict[str, Any] | None:
        row = self.requests_by_id.get(str(request_id))
        if row is None:
            return None
        row.update(payload)
        return row

    def get_request_items(self, request_id: Any) -> list[dict[str, Any]]:
        return list(self.request_items.get(str(request_id), []))

    def insert_request_items(self, request_id: Any, items: list[dict[str, Any]] | list[str]) -> None:
        rows = self.request_items.setdefault(str(request_id), [])
        next_line = len(rows) + 1
        for index, item in enumerate(items, start=next_line):
            if isinstance(item, dict):
                rows.append(
                    {
                        "request_id": request_id,
                        "item_name": item.get("normalized_name") or item.get("name") or item.get("raw"),
                        "description": item.get("raw") or item.get("name") or item.get("item_name"),
                        "raw_text": item.get("raw") or item.get("name") or item.get("item_name"),
                        "qty": item.get("quantity"),
                        "unit": item.get("unit"),
                        "line_number": index,
                    }
                )
            else:
                rows.append({"request_id": request_id, "item_name": item, "description": item, "raw_text": item, "line_number": index})

    def ensure_request_items(self, request_id: Any, items: list[dict[str, Any]] | list[str]) -> None:
        existing = {row["item_name"].casefold() for row in self.get_request_items(request_id)}
        pending = []
        for item in items:
            name = (item.get("normalized_name") or item.get("name") or item.get("raw")) if isinstance(item, dict) else item
            if str(name).casefold() not in existing:
                pending.append(item)
        if pending:
            self.insert_request_items(request_id, pending)

    def is_message_processed(self, message_id: str) -> bool:
        return message_id in self.processed_messages

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
        self.processed_messages.add(message_id)

    def fetch_pending_requests(self, limit: int) -> list[dict[str, Any]]:
        pending = [row for row in self.requests.values() if row.get("status") in {"NEW", "RECEIVED", "PENDING_QUOTE"}]
        return pending[:limit]

    def claim_request(self, request_id: Any) -> dict[str, Any] | None:
        row = self.requests_by_id.get(str(request_id))
        if row and row.get("status") in {"NEW", "RECEIVED", "PENDING_QUOTE"}:
            row["status"] = "PROCESSING"
            return row
        return None

    def get_latest_quote_execution(self, request_id: Any) -> dict[str, Any] | None:
        matches = [row for row in self.request_quotes.values() if row["request_id"] == request_id]
        return matches[-1] if matches else None

    def create_quote_execution(self, request_id: Any, status: str = "RECEIVED") -> dict[str, Any]:
        self._quote_counter += 1
        quote_id = f"rq-{self._quote_counter}"
        row = {"id": quote_id, "request_id": request_id, "status": status}
        self.request_quotes[quote_id] = row
        return row

    def get_or_create_active_quote_execution(self, request_id: Any) -> dict[str, Any]:
        latest = self.get_latest_quote_execution(request_id)
        if latest and latest.get("status") in {"RECEIVED", "QUOTING"}:
            return latest
        return self.create_quote_execution(request_id, status="RECEIVED")

    def update_quote_execution(self, request_quote_id: Any, payload: dict[str, Any]) -> dict[str, Any] | None:
        row = self.request_quotes.get(str(request_quote_id))
        if row is None:
            return None
        row.update(payload)
        return row

    def replace_quote_results(self, request_id: Any, request_quote_id: Any, quote_results: list[dict[str, Any]]) -> None:
        request_row = self.get_request_by_id(request_id) or {}
        request_items = self.get_request_items(request_id)
        item_map = {
            str(item.get("item_name") or item.get("description") or "").strip().casefold(): item
            for item in request_items
        }
        rows: list[dict[str, Any]] = []
        price_history_rows: list[dict[str, Any]] = []

        for item_result in quote_results:
            item_name = str(item_result.get("item_name") or "").strip()
            item_row = item_map.get(item_name.casefold(), {})
            quantity = item_row.get("qty")
            try:
                quantity_value = float(quantity) if quantity is not None else 1.0
            except (TypeError, ValueError):
                quantity_value = 1.0
            for offer in item_result.get("offers", []):
                price = offer.get("price")
                try:
                    unit_price = float(price) if price is not None else None
                except (TypeError, ValueError):
                    unit_price = None
                total_price = unit_price * quantity_value if unit_price is not None else None
                delivery_days = self._infer_delivery_days(offer)
                supplier = self.find_or_create_supplier(
                    company_id=request_row.get("company_id"),
                    supplier_name=str(offer.get("supplier") or "Fornecedor"),
                    source_name=str(offer.get("source") or item_result.get("source") or "").strip() or None,
                    tags=[item_name] if item_name else [],
                )
                value_score = self._compute_value_score(unit_price, delivery_days)
                row = {
                    "request_id": request_id,
                    "request_quote_id": request_quote_id,
                    "item_name": item_name,
                    "supplier_id": supplier.get("id") if supplier else None,
                    "supplier_name": supplier.get("name") if supplier else str(offer.get("supplier") or "Fornecedor"),
                    "supplier": str(offer.get("supplier") or "Fornecedor"),
                    "source_name": str(offer.get("source") or item_result.get("source") or ""),
                    "source_url": offer.get("link"),
                    "price": unit_price,
                    "unit_price": unit_price,
                    "total_price": total_price,
                    "delivery_days": delivery_days,
                    "delivery_label": f"{delivery_days} dia(s)" if delivery_days is not None else "Prazo nao informado",
                    "origin_label": str(offer.get("source") or item_result.get("source") or "cotai"),
                    "value_score": value_score,
                    "is_best_price": False,
                    "is_best_delivery": False,
                    "is_best_overall": False,
                }
                rows.append(row)
                self.update_supplier_rollup(
                    supplier_id=supplier.get("id") if supplier else None,
                    delivery_days=delivery_days,
                    value_score=value_score,
                )
                price_history_rows.append(
                    {
                        "request_id": request_id,
                        "supplier_id": supplier.get("id") if supplier else None,
                        "item_name": item_name,
                        "price": unit_price,
                        "unit_price": unit_price,
                        "captured_at": datetime.now(UTC).isoformat(),
                    }
                )

        self._mark_best_offers(rows)
        self.quote_results[str(request_quote_id)] = rows
        if price_history_rows:
            self.record_price_history(price_history_rows)

    def get_quote_results(self, request_id: Any) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for quote_id, quote in self.request_quotes.items():
            if quote["request_id"] != request_id:
                continue
            for item in self.quote_results.get(quote_id, []):
                rows.append(item)
        return rows

    def complete_quote_execution(
        self,
        request_quote_id: Any,
        status: str,
        response_text: str = "",
        source_summary: str = "",
        error_message: str = "",
    ) -> None:
        row = self.request_quotes[str(request_quote_id)]
        row.update(
            {
                "status": status,
                "response_text": response_text,
                "source_summary": source_summary,
                "error_message": error_message,
            }
        )

    def mark_request_quoting(self, request_id: Any) -> None:
        self.update_request(request_id, {"status": "PROCESSING"})

    def mark_request_error(self, request_id: Any, error_message: str) -> None:
        row = self.update_request(request_id, {"status": "ERROR", "last_error": error_message})
        if row and row.get("chat_thread_id"):
            self.update_chat_thread(row["chat_thread_id"], {"status": "ERROR"})
        if row:
            self.safe_create_admin_audit_log(
                company_id=row.get("company_id"),
                actor_id=None,
                actor_email="worker@cotai.local",
                event_type="request_error",
                description=f"Pedido {row.get('request_code') or request_id} falhou no worker.",
                metadata={"request_id": row.get("id"), "request_code": row.get("request_code"), "error_message": error_message},
            )

    def mark_request_done(self, request_id: Any) -> None:
        row = self.update_request(request_id, {"status": "DONE", "last_error": None})
        if row and row.get("chat_thread_id"):
            self.update_chat_thread(row["chat_thread_id"], {"status": "DONE"})
        if row:
            self.safe_create_admin_audit_log(
                company_id=row.get("company_id"),
                actor_id=None,
                actor_email="worker@cotai.local",
                event_type="request_completed",
                description=f"Pedido {row.get('request_code') or request_id} concluido pelo worker.",
                metadata={"request_id": row.get("id"), "request_code": row.get("request_code"), "status": "DONE"},
            )

    def record_heartbeat(self, worker_name: str, status: str, details: dict[str, Any] | None = None) -> None:
        self.heartbeats.append({"worker_name": worker_name, "status": status, "details": details or {}})

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
        self._thread_counter += 1
        thread_id = f"thread-{self._thread_counter}"
        row = {
            "id": thread_id,
            "user_id": user_id,
            "company_id": company_id,
            "title": title,
            "status": status,
            "request_id": request_id,
            "metadata": metadata or {},
        }
        self.chat_threads[thread_id] = row
        self.chat_messages.setdefault(thread_id, [])
        return row

    def get_chat_thread(self, thread_id: str, user_id: str | None = None) -> dict[str, Any] | None:
        row = self.chat_threads.get(thread_id)
        if row is None:
            return None
        if user_id and row.get("user_id") != user_id:
            return None
        return row

    def update_chat_thread(self, thread_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        row = self.chat_threads.get(thread_id)
        if row is None:
            return None
        row.update(payload)
        return row

    def list_chat_messages(self, thread_id: str) -> list[dict[str, Any]]:
        return list(self.chat_messages.get(thread_id, []))

    def insert_chat_message(self, thread_id: str, role: str, content: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        self._message_counter += 1
        row = {
            "id": f"msg-{self._message_counter}",
            "thread_id": thread_id,
            "role": role,
            "content": content,
            "metadata": metadata or {},
        }
        self.chat_messages.setdefault(thread_id, []).append(row)
        return row

    def get_request_status_payload(self, request_id: str) -> dict[str, Any]:
        request_row = self.get_request_by_id(request_id)
        if request_row is None:
            raise RuntimeError("Request not found.")
        results = self.get_quote_results(request_id)
        return {
            "request": request_row,
            "latest_quote": self.get_latest_quote_execution(request_id),
            "results": results,
            "items": self.get_request_items(request_id),
            "comparison": self.build_quote_comparison(results),
        }

    def table_exists(self, table: str) -> bool:
        return table != "missing_table"

    def find_or_create_supplier(
        self,
        *,
        company_id: str | None,
        supplier_name: str,
        source_name: str | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any] | None:
        for supplier in self.suppliers.values():
            if supplier.get("company_id") == company_id and supplier.get("name") == supplier_name:
                return supplier
        supplier_id = f"supplier-{len(self.suppliers) + 1}"
        row = {
            "id": supplier_id,
            "company_id": company_id,
            "name": supplier_name,
            "region": source_name,
            "material_tags": tags or [],
            "quote_participation_count": 0,
            "average_rating": None,
            "average_price_score": None,
            "average_delivery_days": None,
            "status": "active",
        }
        self.suppliers[supplier_id] = row
        return row

    def update_supplier_rollup(self, *, supplier_id: str | None, delivery_days: int | None = None, value_score: float | None = None) -> None:
        if not supplier_id or supplier_id not in self.suppliers:
            return
        supplier = self.suppliers[supplier_id]
        supplier["quote_participation_count"] = int(supplier.get("quote_participation_count") or 0) + 1
        if delivery_days is not None:
            supplier["average_delivery_days"] = delivery_days
        if value_score is not None:
            supplier["average_price_score"] = value_score

    def update_supplier(self, supplier_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        supplier = self.suppliers.get(supplier_id)
        if not supplier:
            return None
        supplier.update(payload)
        return supplier

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
        row = {
            "id": f"review-{len(self.supplier_reviews) + 1}",
            "supplier_id": supplier_id,
            "request_id": request_id,
            "company_id": company_id,
            "reviewer_user_id": reviewer_user_id,
            "price_rating": price_rating,
            "delivery_rating": delivery_rating,
            "service_rating": service_rating,
            "reliability_rating": reliability_rating,
            "comment": comment,
        }
        self.supplier_reviews.append(row)
        self.refresh_supplier_rating(supplier_id)
        return row

    def refresh_supplier_rating(self, supplier_id: str) -> None:
        supplier = self.suppliers.get(supplier_id)
        if not supplier:
            return
        rows = [row for row in self.supplier_reviews if row["supplier_id"] == supplier_id]
        scores = []
        for row in rows:
            ratings = [row.get("price_rating"), row.get("delivery_rating"), row.get("service_rating"), row.get("reliability_rating")]
            numeric = [float(item) for item in ratings if isinstance(item, (int, float))]
            if numeric:
                scores.append(sum(numeric) / len(numeric))
        supplier["average_rating"] = sum(scores) / len(scores) if scores else None

    def create_project(self, *, company_id: str, created_by_user_id: str | None, name: str, location: str | None, notes: str | None) -> dict[str, Any] | None:
        for project in self.projects.values():
            if project.get("company_id") == company_id and project.get("name") == name:
                return project
        project_id = f"project-{len(self.projects) + 1}"
        row = {"id": project_id, "company_id": company_id, "name": name, "location": location, "notes": notes, "status": "active"}
        self.projects[project_id] = row
        return row

    def upsert_project_materials(self, *, project_id: str | None, request_id: str, items: list[dict[str, Any]], status: str) -> None:
        if not project_id:
            return
        for item in items:
            self.project_materials.append(
                {
                    "project_id": project_id,
                    "request_id": request_id,
                    "material_name": item.get("normalized_name") or item.get("name") or item.get("raw"),
                    "estimated_qty": item.get("quantity"),
                    "pending_qty": item.get("quantity"),
                    "status": status,
                }
            )

    def record_price_history(self, rows: list[dict[str, Any]]) -> None:
        self.price_history.extend(rows)

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
        row = {
            "id": f"audit-{len(self.admin_audit_logs) + 1}",
            "company_id": company_id,
            "actor_id": actor_id,
            "actor_email": actor_email,
            "event_type": event_type,
            "description": description,
            "metadata": metadata or {},
        }
        self.admin_audit_logs.append(row)
        return row

    def safe_create_admin_audit_log(self, **kwargs: Any) -> None:
        self.create_admin_audit_log(**kwargs)

    def reprocess_request_as_admin(self, request_id: str, actor: dict[str, Any], reason: str) -> dict[str, Any]:
        request_row = self.get_request_by_id(request_id)
        if request_row is None:
            raise RuntimeError("Request not found.")
        current_status = str(request_row.get("status") or "").upper()
        if current_status in {"PROCESSING", "QUOTING"}:
            raise RuntimeError("Este pedido ja esta em processamento.")
        self.update_request(request_id, {"status": "NEW", "last_error": None, "processed_at": None})
        self.safe_create_admin_audit_log(
            company_id=request_row.get("company_id"),
            actor_id=actor.get("user", {}).get("id"),
            actor_email=actor.get("user", {}).get("email"),
            event_type="request_reprocess_requested",
            description=f"Pedido {request_row.get('request_code') or request_id} reenfileirado manualmente.",
            metadata={"request_id": request_id, "reason": reason, "previous_status": current_status},
        )
        return {
            "request_id": request_id,
            "status": "NEW",
            "previous_status": current_status,
            "message": "Pedido reenfileirado com seguranca.",
        }

    def approve_request_as_admin(self, request_id: str, actor: dict[str, Any], comment: str = "") -> dict[str, Any]:
        row = self.get_request_by_id(request_id)
        if not row:
            raise RuntimeError("Request not found.")
        if not row.get("approval_required"):
            raise RuntimeError("Este pedido nao exige aprovacao.")
        self.update_request(
            request_id,
            {
                "status": "NEW",
                "approval_status": "APPROVED",
                "approved_at": datetime.now(UTC).isoformat(),
                "approved_by_user_id": actor.get("user", {}).get("id"),
            },
        )
        return {"request_id": request_id, "status": "NEW", "approval_status": "APPROVED", "message": "Pedido aprovado e reenfileirado para cotacao."}

    def build_quote_comparison(self, results: list[dict[str, Any]]) -> dict[str, Any]:
        suppliers: dict[str, dict[str, Any]] = {}
        for row in results:
            supplier = str(row.get("supplier_name") or row.get("supplier") or "Fornecedor")
            entry = suppliers.setdefault(
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
            entry["items"] += 1
            entry["total_price"] += float(row.get("total_price") or row.get("price") or 0)
            delivery_days = row.get("delivery_days")
            if isinstance(delivery_days, (int, float)):
                entry["average_delivery_days"] = delivery_days if entry["average_delivery_days"] is None else round((entry["average_delivery_days"] + delivery_days) / 2, 2)
            entry["value_score"] += float(row.get("value_score") or 0)
            entry["best_price_count"] += 1 if row.get("is_best_price") else 0
            entry["best_delivery_count"] += 1 if row.get("is_best_delivery") else 0
            entry["best_overall_count"] += 1 if row.get("is_best_overall") else 0
        ranked = sorted(
            suppliers.values(),
            key=lambda item: (item["total_price"], -(item["best_overall_count"]), item["average_delivery_days"] or 999),
        )
        price_values = [item["total_price"] for item in ranked if item["total_price"]]
        return {
            "supplier_count": len(ranked),
            "best_supplier": ranked[0] if ranked else None,
            "best_price_supplier": min(ranked, key=lambda item: item["total_price"]) if ranked else None,
            "best_delivery_supplier": min(ranked, key=lambda item: item["average_delivery_days"] or 999) if ranked else None,
            "potential_savings": (max(price_values) - min(price_values)) if len(price_values) >= 2 else 0.0,
            "suppliers": ranked[:5],
        }

    def _infer_delivery_days(self, offer: dict[str, Any]) -> int | None:
        shipping = str(offer.get("shipping") or offer.get("delivery") or "").strip()
        digits = "".join(char for char in shipping if char.isdigit())
        if digits:
            return int(digits)
        return None

    def _compute_value_score(self, price: float | None, delivery_days: int | None) -> float:
        if price is None:
            return 0.0
        delivery_penalty = float(delivery_days or 7) * 0.75
        return round(max(0.0, 1000.0 / max(price, 1.0) - delivery_penalty), 2)

    def _mark_best_offers(self, rows: list[dict[str, Any]]) -> None:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            grouped.setdefault(str(row.get("item_name") or ""), []).append(row)
        for item_rows in grouped.values():
            price_candidates = [row for row in item_rows if isinstance(row.get("total_price"), (int, float))]
            if price_candidates:
                best_price = min(row["total_price"] for row in price_candidates)
                for row in price_candidates:
                    row["is_best_price"] = row["total_price"] == best_price
            delivery_candidates = [row for row in item_rows if isinstance(row.get("delivery_days"), (int, float))]
            if delivery_candidates:
                best_delivery = min(row["delivery_days"] for row in delivery_candidates)
                for row in delivery_candidates:
                    row["is_best_delivery"] = row["delivery_days"] == best_delivery
            best_overall = sorted(
                item_rows,
                key=lambda row: (
                    -(float(row.get("value_score") or 0)),
                    float(row.get("total_price") or 999999),
                    float(row.get("delivery_days") or 999),
                ),
            )[0]
            best_overall["is_best_overall"] = True

    def get_operations_snapshot(self) -> dict[str, Any]:
        latest_request = next(reversed(list(self.requests_by_id.values())), None) if self.requests_by_id else None
        latest_quote = next(reversed(list(self.request_quotes.values())), None) if self.request_quotes else None
        latest_heartbeat = self.heartbeats[-1] if self.heartbeats else None
        return {
            "api": {"status": "online", "base_url": "http://127.0.0.1:8000", "debug": True},
            "supabase": {"status": "healthy", "ok": True, "failing_checks": []},
            "worker": {
                "status": latest_heartbeat.get("status") if latest_heartbeat else "offline",
                "last_heartbeat_at": latest_heartbeat.get("created_at") if latest_heartbeat else None,
                "last_heartbeat_status": latest_heartbeat.get("status") if latest_heartbeat else None,
                "details": latest_heartbeat.get("details") if latest_heartbeat else {},
            },
            "queue": {
                "pending_requests": len([row for row in self.requests.values() if row.get("status") in {"NEW", "RECEIVED", "PENDING_QUOTE"}]),
                "processing_requests": len([row for row in self.requests.values() if row.get("status") in {"PROCESSING", "QUOTING"}]),
                "quotes_done_today": len([row for row in self.request_quotes.values() if row.get("status") == "DONE"]),
                "quotes_error_today": len([row for row in self.request_quotes.values() if row.get("status") == "ERROR"]),
                "average_quote_minutes_today": None,
            },
            "recent": {
                "request": latest_request,
                "quote": latest_quote,
            },
        }


class InMemorySearchService:
    def quote_item(self, item_name: str) -> tuple[list[dict[str, Any]], str]:
        return (
            [
                {
                    "title": f"{item_name} premium",
                    "price": 10.0,
                    "supplier": "Local Supplier",
                    "link": "https://example.test/item",
                    "source": "catalog",
                    "delivery_label": "2 dia(s)",
                    "best_hint": True,
                },
                {
                    "title": f"{item_name} alternativa",
                    "price": 12.5,
                    "supplier": "Fornecedor Alternativo",
                    "link": "https://example.test/item-2",
                    "source": "catalog",
                    "delivery_label": "4 dia(s)",
                }
            ],
            "catalog",
        )

    def suggest_search_term(self, item_name: str) -> str:
        return item_name


class InMemoryAIService:
    def extract_items(self, text: str) -> tuple[list[dict[str, Any]], str]:
        return (
            [
                {"name": "cimento cp2 50kg", "normalized_name": "cimento cp2 50kg", "quantity": 20.0, "unit": "saco", "raw": "20 saco cimento cp2 50kg"},
                {"name": "areia fina", "normalized_name": "areia fina", "quantity": 3.0, "unit": "m3", "raw": "3 m3 areia fina"},
            ],
            "local",
        )

    def build_confirmation_message(self, items: list[dict[str, Any]]) -> tuple[str, str]:
        return ("Entendi seu pedido. Confirma estes itens?", "local")

    def summarize_quote(self, request_code: str, results: list[dict[str, Any]]) -> tuple[str, str]:
        return f"Resumo local para {request_code} com {len(results)} item(ns).", "local"
