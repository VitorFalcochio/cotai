from __future__ import annotations

from typing import Any

from .supabase_service import SupabaseService


class QuoteService:
    def __init__(self, supabase: SupabaseService) -> None:
        self.supabase = supabase

    def get_request_status(self, request_id: str) -> dict[str, Any]:
        payload = self.supabase.get_request_status_payload(request_id)
        request_row = payload["request"]
        latest_quote = payload["latest_quote"]
        return {
            "request_id": request_row["id"],
            "request_code": request_row.get("request_code"),
            "status": request_row.get("status"),
            "last_error": request_row.get("last_error"),
            "processed_at": request_row.get("processed_at"),
            "priority": request_row.get("priority"),
            "sla_due_at": request_row.get("sla_due_at"),
            "approval_required": request_row.get("approval_required"),
            "approval_status": request_row.get("approval_status"),
            "duplicate_of_request_id": request_row.get("duplicate_of_request_id"),
            "latest_quote": latest_quote,
            "project_materials": payload.get("project_materials", []),
            "price_history": payload.get("price_history", []),
            "project_events": payload.get("project_events", []),
            "comparison": payload.get("comparison", {}),
        }

    def get_request_results(self, request_id: str) -> dict[str, Any]:
        payload = self.supabase.get_request_status_payload(request_id)
        return {
            "request": payload["request"],
            "latest_quote": payload["latest_quote"],
            "results": payload["results"],
            "items": payload.get("items", []),
            "comparison": payload.get("comparison", {}),
            "project_materials": payload.get("project_materials", []),
            "price_history": payload.get("price_history", []),
            "project_events": payload.get("project_events", []),
        }

    def register_project_execution_event(self, request_id: str, actor: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        return self.supabase.apply_project_execution_event(
            request_id=request_id,
            actor=actor,
            event_type=payload["event_type"],
            material_name=payload.get("material_name"),
            quantity=payload.get("quantity"),
            stage_label=payload.get("stage_label"),
            supplier_name=payload.get("supplier_name"),
            note=payload.get("note"),
        )

    def submit_supplier_review(self, request_id: str, actor: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        request_row = self.supabase.get_request_by_id(request_id)
        if request_row is None:
            raise RuntimeError("Request not found.")
        review = self.supabase.create_supplier_review(
            supplier_id=payload["supplier_id"],
            request_id=request_id,
            company_id=request_row.get("company_id"),
            reviewer_user_id=actor.get("user", {}).get("id"),
            price_rating=payload.get("price_rating"),
            delivery_rating=payload.get("delivery_rating"),
            service_rating=payload.get("service_rating"),
            reliability_rating=payload.get("reliability_rating"),
            comment=payload.get("comment") or "",
        )
        self.supabase.safe_create_admin_audit_log(
            company_id=request_row.get("company_id"),
            actor_id=actor.get("user", {}).get("id"),
            actor_email=actor.get("user", {}).get("email"),
            event_type="supplier_review_created",
            description=f"Avaliacao registrada para o pedido {request_row.get('request_code') or request_id}.",
            metadata={"request_id": request_id, "supplier_id": payload["supplier_id"]},
        )
        return {"ok": True, "review": review}
