from __future__ import annotations

from typing import Any

from .supabase_service import SupabaseService


class ProjectService:
    def __init__(self, supabase: SupabaseService) -> None:
        self.supabase = supabase

    def save_project_from_thread(self, *, actor: dict[str, Any], thread_id: str, name: str) -> dict[str, Any]:
        thread = self.supabase.get_chat_thread(thread_id, actor["user"]["id"])
        if not thread:
            raise RuntimeError("Thread nao encontrada.")

        metadata = thread.get("metadata") or {}
        construction_context = metadata.get("construction_context") or {}
        construction_brain = metadata.get("construction_brain") or {}
        conversation_memory = metadata.get("construction_memory") or {}
        if not construction_context:
            raise RuntimeError("Ainda nao ha contexto suficiente da obra para salvar um projeto.")

        project = self.supabase.create_project(
            company_id=actor["profile"]["company_id"],
            created_by_user_id=actor["user"]["id"],
            name=name,
            location=construction_context.get("location"),
            notes=metadata.get("construction_query") or metadata.get("last_user_message") or thread.get("title"),
        )
        if not project:
            raise RuntimeError("Nao foi possivel salvar o projeto.")

        project_payload = {
            "source_thread_id": thread_id,
            "project_type": construction_context.get("project_type"),
            "area_m2": construction_context.get("area_m2"),
            "floors": construction_context.get("floors"),
            "building_standard": construction_context.get("building_standard"),
            "foundation_type": construction_context.get("foundation_type"),
            "roof_type": construction_context.get("roof_type"),
            "location": construction_context.get("location"),
            "current_phase_key": ((construction_brain.get("operational") or {}).get("current_phase_key")),
            "current_phase_title": ((construction_brain.get("operational") or {}).get("current_phase_label")),
            "summary_estimated_total_cents": ((construction_brain.get("financial") or {}).get("estimated_total_cents")),
            "summary_estimated_total_display": ((construction_brain.get("financial") or {}).get("estimated_total_display")),
            "stage": ((construction_brain.get("operational") or {}).get("current_phase_label")) or project.get("stage") or "planning",
            "metadata": {
                "construction_context": construction_context,
                "construction_brain": construction_brain,
                "conversation_memory": conversation_memory,
                "saved_from": "chat_thread",
            },
        }
        project = self.supabase.update_project(project["id"], project_payload) or {**project, **project_payload}
        pending_items = metadata.get("pending_items") or []
        if pending_items:
            self.supabase.upsert_project_materials(
                project_id=project["id"],
                request_id=None,
                items=pending_items,
                status="planned",
            )

        updated_metadata = {
            **metadata,
            "project_id": project["id"],
            "project_name": project.get("name"),
        }
        self.supabase.update_chat_thread(thread_id, {"metadata": updated_metadata})
        self.supabase.insert_chat_message(
            thread_id,
            "assistant",
            f"Projeto {project.get('name')} salvo. Agora voce pode acompanhar fases, custos e materiais na aba Projetos.",
            {"kind": "project_saved", "project_id": project["id"], "project_name": project.get("name")},
        )
        return self.get_project(actor=actor, project_id=project["id"])

    def list_projects(self, *, actor: dict[str, Any]) -> dict[str, Any]:
        rows = self.supabase.list_projects(actor["profile"]["company_id"])
        projects = [self._build_project_list_item(row) for row in rows]
        return {"projects": projects}

    def get_project(self, *, actor: dict[str, Any], project_id: str) -> dict[str, Any]:
        project = self.supabase.get_project(project_id)
        if not project or project.get("company_id") != actor["profile"]["company_id"]:
            raise RuntimeError("Projeto nao encontrado.")
        requests = self.supabase.list_requests_for_project(project_id)
        materials = self.supabase.get_project_materials(project_id)
        events = self.supabase.get_project_events(project_id)
        return {
            "project": self._build_project_list_item(project, requests=requests, materials=materials, events=events),
            "materials": materials,
            "events": events,
            "requests": requests,
        }

    def _build_project_list_item(
        self,
        row: dict[str, Any],
        *,
        requests: list[dict[str, Any]] | None = None,
        materials: list[dict[str, Any]] | None = None,
        events: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        request_rows = list(requests) if requests is not None else self.supabase.list_requests_for_project(row.get("id"), limit=20)
        material_rows = list(materials) if materials is not None else self.supabase.get_project_materials(row.get("id"))
        event_rows = list(events) if events is not None else self.supabase.get_project_events(row.get("id"), limit=20)
        metadata = row.get("metadata") or {}
        construction_context = metadata.get("construction_context") or {}

        priced_materials = [item for item in material_rows if item.get("estimated_qty") is not None]
        total_estimated_qty = sum(float(item.get("estimated_qty") or 0) for item in priced_materials)
        latest_request = request_rows[0] if request_rows else None

        return {
            **row,
            "request_count": len(request_rows),
            "material_count": len(material_rows),
            "event_count": len(event_rows),
            "latest_request_code": latest_request.get("request_code") if latest_request else None,
            "latest_request_status": latest_request.get("status") if latest_request else None,
            "source_thread_id": row.get("source_thread_id"),
            "project_label": construction_context.get("project_label") or row.get("project_type") or "obra",
            "location_label": row.get("location") or construction_context.get("location") or "-",
            "area_label": f"{construction_context.get('area_m2') or row.get('area_m2')} m2" if (construction_context.get("area_m2") or row.get("area_m2")) else "Pendente",
            "estimated_total_display": row.get("summary_estimated_total_display") or ((metadata.get("construction_brain") or {}).get("financial") or {}).get("estimated_total_display"),
            "current_phase_label": row.get("current_phase_title") or row.get("stage") or "Planejamento",
            "total_estimated_qty": round(total_estimated_qty, 2),
        }
