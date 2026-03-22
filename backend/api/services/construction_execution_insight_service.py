from __future__ import annotations

from statistics import mean
from typing import Any


class ConstructionExecutionInsightService:
    def build_snapshot(self, *, request_payload: dict[str, Any] | None) -> dict[str, Any]:
        request_payload = request_payload or {}
        request_row = request_payload.get("request") or {}
        comparison = request_payload.get("comparison") or {}
        project_materials = list(request_payload.get("project_materials") or [])
        price_history = list(request_payload.get("price_history") or [])
        project_events = list(request_payload.get("project_events") or [])
        request_items = list(request_payload.get("items") or [])

        tracked_materials = len(project_materials)
        pending_materials = sum(
            1
            for item in project_materials
            if str(item.get("status") or "").lower() in {"pending", "pending_quote", "draft", "quoted"}
        )
        quoted_materials = sum(
            1
            for item in project_materials
            if str(item.get("status") or "").lower() in {"quoted", "done", "purchased"}
        )
        quantity_tracked = sum(self._to_float(item.get("estimated_qty")) for item in project_materials)

        unit_prices = [self._to_float(row.get("unit_price") or row.get("price")) for row in price_history]
        unit_prices = [value for value in unit_prices if value > 0]
        avg_unit_price = mean(unit_prices) if unit_prices else None
        latest_unit_price = unit_prices[-1] if unit_prices else None
        price_variation_pct = None
        if avg_unit_price and latest_unit_price:
            price_variation_pct = round(((latest_unit_price - avg_unit_price) / avg_unit_price) * 100, 1)

        best_supplier = comparison.get("best_supplier") or {}
        best_price_supplier = comparison.get("best_price_supplier") or {}
        best_delivery_supplier = comparison.get("best_delivery_supplier") or {}
        delayed_events = [
            event for event in project_events if str(event.get("event_type") or "").lower() == "supplier_delay"
        ]
        completed_stages = [
            event for event in project_events if str(event.get("event_type") or "").lower() == "stage_completed"
        ]
        latest_event = project_events[0] if project_events else {}

        return {
            "tracked_materials": tracked_materials,
            "pending_materials": pending_materials,
            "quoted_materials": quoted_materials,
            "quantity_tracked": round(quantity_tracked, 2) if quantity_tracked else 0,
            "request_status": request_row.get("status") or "DRAFT",
            "request_items_count": len(request_items),
            "supplier_count": comparison.get("supplier_count") or 0,
            "best_supplier_label": best_supplier.get("supplier"),
            "best_price_label": best_price_supplier.get("supplier"),
            "best_delivery_label": best_delivery_supplier.get("supplier"),
            "potential_savings": comparison.get("potential_savings") or 0,
            "avg_unit_price": avg_unit_price,
            "latest_unit_price": latest_unit_price,
            "price_variation_pct": price_variation_pct,
            "price_history_points": len(price_history),
            "project_events_count": len(project_events),
            "supplier_delay_count": len(delayed_events),
            "completed_stage_count": len(completed_stages),
            "latest_event_type": latest_event.get("event_type"),
            "latest_event_note": latest_event.get("note"),
            "latest_stage_label": latest_event.get("stage_label"),
        }

    def _to_float(self, value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
