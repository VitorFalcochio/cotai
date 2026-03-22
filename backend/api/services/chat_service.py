from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from .construction_brain_service import ConstructionBrainService
from .construction_execution_insight_service import ConstructionExecutionInsightService
from .conversation_intelligence_service import ConversationIntelligenceService
from .construction_mode_service import ConstructionModeService
from .request_parser import RequestParserService
from .supabase_service import SupabaseService


class ChatService:
    def __init__(
        self,
        supabase: SupabaseService,
        parser: RequestParserService,
        construction_service: ConstructionModeService | None = None,
        intelligence_service: ConversationIntelligenceService | None = None,
        brain_service: ConstructionBrainService | None = None,
        execution_insight_service: ConstructionExecutionInsightService | None = None,
    ) -> None:
        self.supabase = supabase
        self.parser = parser
        self.construction_service = construction_service
        self.intelligence_service = intelligence_service or ConversationIntelligenceService()
        self.brain_service = brain_service or ConstructionBrainService()
        self.execution_insight_service = execution_insight_service or ConstructionExecutionInsightService()

    def handle_message(self, *, actor: dict[str, Any], thread_id: str | None, message: str) -> dict[str, Any]:
        profile = actor["profile"]
        company_id = profile.get("company_id")
        if not company_id:
            raise RuntimeError("Seu perfil ainda nao esta vinculado a uma empresa.")

        thread = self._load_or_create_thread(actor, thread_id, message)
        thread = self._reset_thread_for_new_quote_cycle(thread)
        metadata = thread.get("metadata") or {}
        self.supabase.insert_chat_message(thread["id"], "user", message, {"kind": "prompt"})
        parsed = self.parser.parse_user_message(message)
        intent = self.intelligence_service.classify_intent(
            message=message,
            metadata=metadata,
            parsed_items=parsed["items"],
        )

        if intent["mode"] in {"construction_guidance", "construction_refinement", "construction_procurement"}:
            return self._handle_construction_intent_message(
                actor=actor,
                thread=thread,
                metadata=metadata,
                message=message,
                intent=intent,
            )

        if not parsed["items"]:
            assistant_text = self._build_general_guidance_message(metadata)
            updated_metadata = {
                **metadata,
                "draft_saved_at": datetime.now(UTC).isoformat(),
                "last_user_message": message,
                "timeline": self._append_timeline(metadata, "Rascunho salvo automaticamente."),
            }
            self.supabase.insert_chat_message(thread["id"], "assistant", assistant_text, {"status": "DRAFT"})
            self.supabase.update_chat_thread(
                thread["id"],
                {
                    "status": "DRAFT",
                    "metadata": {**updated_metadata, "pending_items": metadata.get("pending_items") or []},
                },
            )
            return self.get_thread_payload(actor, thread["id"])

        items = self._merge_items(metadata.get("pending_items") or [], parsed["items"])
        confirmation = self.parser.build_confirmation(items)
        updated_metadata = {
            **metadata,
            "pending_items": items,
            "parse_provider": parsed["provider"],
            "confirmation_provider": confirmation["provider"],
            "last_user_message": message,
            "draft_saved_at": datetime.now(UTC).isoformat(),
            "timeline": self._append_timeline(metadata, f"{len(items)} item(ns) preparados para confirmacao."),
        }
        self.supabase.insert_chat_message(
            thread["id"],
            "assistant",
            confirmation["message"],
            {"status": "AWAITING_CONFIRMATION", "preview": confirmation["preview"]},
        )
        self.supabase.update_chat_thread(thread["id"], {"status": "AWAITING_CONFIRMATION", "metadata": updated_metadata})
        return self.get_thread_payload(actor, thread["id"])

    def update_draft(self, *, actor: dict[str, Any], thread_id: str, draft_data: dict[str, Any]) -> dict[str, Any]:
        thread = self.supabase.get_chat_thread(thread_id, actor["user"]["id"])
        if not thread:
            raise RuntimeError("Thread nao encontrada.")

        metadata = thread.get("metadata") or {}
        items = [self.parser._normalize_item(item) for item in draft_data.get("items") or []]  # noqa: SLF001
        normalized_items = [item for item in items if item]
        next_status = "AWAITING_CONFIRMATION" if normalized_items else "DRAFT"
        merged_metadata = {
            **metadata,
            "pending_items": normalized_items,
            "delivery_mode": draft_data.get("delivery_mode") or metadata.get("delivery_mode"),
            "delivery_location": draft_data.get("delivery_location") or metadata.get("delivery_location"),
            "draft_notes": draft_data.get("notes") or metadata.get("draft_notes"),
            "priority": draft_data.get("priority") or metadata.get("priority"),
            "draft_saved_at": datetime.now(UTC).isoformat(),
            "timeline": self._append_timeline(metadata, "Rascunho atualizado manualmente."),
        }
        self.supabase.update_chat_thread(
            thread_id,
            {
                "title": draft_data.get("title") or thread.get("title"),
                "status": next_status,
                "metadata": merged_metadata,
            },
        )
        self.supabase.insert_chat_message(
            thread_id,
            "system",
            "Rascunho atualizado antes da confirmacao.",
            {"status": next_status, "kind": "draft_update"},
        )
        return self.get_thread_payload(actor, thread_id)

    def _handle_construction_intent_message(
        self,
        *,
        actor: dict[str, Any],
        thread: dict[str, Any],
        metadata: dict[str, Any],
        message: str,
        intent: dict[str, Any],
    ) -> dict[str, Any]:
        if not self.construction_service:
            return self.get_thread_payload(actor, thread["id"])

        context = (metadata.get("construction_memory") or {}).get("context") or metadata.get("construction_context") or {}
        analysis = self.construction_service.analyze_project(message, context=context)
        intent_mode = str(intent.get("mode") or "construction_guidance")
        procurement = None
        pending_items = metadata.get("pending_items") or []
        next_status = "DRAFT"
        if intent_mode == "construction_procurement" and str(analysis.get("status") or "").lower() == "ok":
            procurement = self.construction_service.build_procurement_plan(
                analysis,
                selected_phase=intent.get("selected_phase"),
            )
            pending_items = self.intelligence_service.build_procurement_draft_items(procurement)
            next_status = "AWAITING_CONFIRMATION" if pending_items else "DRAFT"
        memory = self.intelligence_service.build_construction_memory(
            previous_context=context,
            analysis=analysis,
            intent_mode=intent_mode,
            message=message,
        )
        brain = self.brain_service.build_snapshot(
            analysis=analysis,
            procurement=procurement,
            memory=memory,
            metadata=metadata,
            latest_message=message,
            execution_data=None,
        )
        assistant_text = self._build_construction_guidance_message(analysis, memory=memory, procurement=procurement)
        conversation = analysis.get("conversation") or {}
        project = analysis.get("project") or {}
        preview_payload = {**(procurement or analysis), "brain": brain}
        updated_metadata = {
            **metadata,
            "construction_context": conversation.get("context") or project,
            "construction_memory": memory,
            "construction_brain": brain,
            "construction_query": project.get("raw_text") or message,
            "construction_mode": analysis.get("mode"),
            "construction_status": analysis.get("status"),
            "pending_items": pending_items,
            "draft_saved_at": datetime.now(UTC).isoformat(),
            "last_user_message": message,
            "timeline": self._append_timeline(
                metadata,
                "Consulta tecnica de obra transformada em lista de compra."
                if procurement
                else "Consulta tecnica de obra analisada pela Cota.",
            ),
        }
        self.supabase.insert_chat_message(
            thread["id"],
            "assistant",
            assistant_text,
            {
                "status": next_status,
                "kind": "construction_procurement" if procurement else "construction_guidance",
                "construction_mode": analysis.get("mode"),
                "construction_status": analysis.get("status"),
                "intent_mode": intent_mode,
                "selected_phase": intent.get("selected_phase"),
                "construction_preview": preview_payload,
            },
        )
        self.supabase.update_chat_thread(
            thread["id"],
            {
                "status": next_status,
                "metadata": updated_metadata,
            },
        )
        return self.get_thread_payload(actor, thread["id"])

    def _build_construction_guidance_message(
        self,
        analysis: dict[str, Any],
        *,
        memory: dict[str, Any] | None = None,
        procurement: dict[str, Any] | None = None,
    ) -> str:
        status = str(analysis.get("status") or "").lower()
        project = analysis.get("project") or {}
        summary = analysis.get("summary") or {}
        next_questions = [str(item).strip() for item in analysis.get("next_questions") or [] if str(item).strip()]
        assumptions = [str(item).strip() for item in analysis.get("assumptions") or [] if str(item).strip()]
        phases = [str(item.get("title") or "").strip() for item in analysis.get("phases") or [] if str(item.get("title") or "").strip()]
        learned_facts = list((memory or {}).get("learned_facts") or [])
        conflicts = list((memory or {}).get("conflicts") or [])
        confidence = (memory or {}).get("confidence") or {}
        area_m2 = project.get("area_m2")
        project_label = project.get("project_label") or project.get("project_type") or "obra"

        if status == "needs_clarification":
            prompt = analysis.get("message") or "Preciso fechar melhor o escopo da obra."
            lines = [
                "Aqui e a Cota, sua IA de construcao civil.",
                str(prompt),
            ]
            if next_questions:
                lines.append("Para eu te orientar melhor agora:")
                lines.extend(f"- {question}" for question in next_questions[:3])
            return "\n".join(lines)

        if procurement:
            purchase_list = list(procurement.get("purchase_list") or [])
            selected_phase = procurement.get("summary", {}).get("selected_phase_title") or procurement.get("selected_phase_key")
            lines = [
                "Aqui e a Cota, sua IA de construcao civil.",
                "Transformei a leitura da obra em lista inicial de compra.",
            ]
            if selected_phase:
                lines.append(f"Fase priorizada: {selected_phase}.")
            if purchase_list:
                preview_items = ", ".join(
                    f"{item.get('quantity')} {item.get('unit')} {item.get('material')}"
                    for item in purchase_list[:4]
                )
                lines.append(f"Itens puxados para revisao: {preview_items}.")
            if confidence.get("score") is not None:
                lines.append(
                    f"Confianca atual da leitura: {confidence.get('label', 'media')} ({int(float(confidence.get('score') or 0))}%)."
                )
            if conflicts:
                lines.append("Ajustes detectados na conversa:")
                lines.extend(
                    f"- {conflict.get('label')}: antes {conflict.get('previous')}, agora {conflict.get('current')}"
                    for conflict in conflicts[:2]
                )
            lines.append("Revise os itens no rascunho e confirme quando quiser que eu siga para cotacao.")
            return "\n".join(lines)

        title = f"Montei a leitura inicial para {project_label}"
        if area_m2:
            title += f" de {area_m2} m2."
        else:
            title += "."

        lines = [
            "Aqui e a Cota, sua IA de construcao civil.",
            title,
        ]
        if phases:
            lines.append(f"Eu comecaria por estas frentes: {', '.join(phases[:4])}.")
        if learned_facts:
            lines.append(
                "Contexto aprendido nesta conversa: "
                + " | ".join(f"{fact.get('label')}: {fact.get('value')}" for fact in learned_facts[:3])
                + "."
            )
        context_bits = []
        if project.get("location"):
            context_bits.append(f"local em {project['location']}")
        if project.get("foundation_type"):
            context_bits.append(f"fundacao {project['foundation_type']}")
        if project.get("building_standard"):
            context_bits.append(f"padrao {project['building_standard']}")
        if context_bits:
            lines.append(f"Contexto considerado: {', '.join(context_bits)}.")
        if confidence.get("score") is not None:
            lines.append(
                f"Leitura atual da obra com confianca {confidence.get('label', 'media')} ({int(float(confidence.get('score') or 0))}%)."
            )
        if summary.get("estimated_total_cost_display"):
            cost_line = f"Custo preliminar de materiais: {summary['estimated_total_cost_display']}"
            min_cost = summary.get("estimated_total_cost_range_min_display")
            max_cost = summary.get("estimated_total_cost_range_max_display")
            if min_cost and max_cost:
                cost_line += f" (faixa {min_cost} a {max_cost})."
            else:
                cost_line += "."
            lines.append(cost_line)
        if assumptions:
            lines.append(f"Premissas usadas: {' | '.join(assumptions[:3])}.")
        if conflicts:
            lines.append("Pontos de conflito que eu atualizei:")
            lines.extend(
                f"- {conflict.get('label')}: antes {conflict.get('previous')}, agora {conflict.get('current')}"
                for conflict in conflicts[:2]
            )
        if next_questions:
            lines.append("Antes de virar compra real, eu refinaria estes pontos:")
            lines.extend(f"- {question}" for question in next_questions[:3])
        else:
            lines.append("O escopo principal ja esta bem fechado para seguir para lista de compra por fase.")
        lines.append("Se quiser, eu continuo daqui e transformo a obra em etapas e lista inicial de materiais.")
        return "\n".join(lines)

    def _build_general_guidance_message(self, metadata: dict[str, Any]) -> str:
        construction_context = (metadata.get("construction_memory") or {}).get("context") or metadata.get("construction_context") or {}
        if construction_context:
            next_action = ((metadata.get("construction_memory") or {}).get("next_action") or {}).get("label")
            lines = [
                "Aqui e a Cota, sua IA de construcao civil.",
                "Ainda nao encontrei itens de compra claros nessa mensagem, mas continuo acompanhando o contexto da obra.",
            ]
            if next_action:
                lines.append(f"Meu proximo passo sugerido: {next_action}.")
            lines.append("Se quiser, responda com dados da obra ou me peca a lista inicial de compra por fase.")
            return "\n".join(lines)
        return (
            "Aqui e a Cota, sua IA de construcao civil. "
            "Posso te ajudar a planejar a obra, transformar etapas em lista de compra ou cotar materiais. "
            "Se quiser cotacao direta, me passe os itens com quantidade e especificacao. "
            "Se quiser planejamento, descreva a obra, a area e o tipo, por exemplo: casa de 120 m2."
        )

    def confirm_thread(self, *, actor: dict[str, Any], thread_id: str, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
        thread = self.supabase.get_chat_thread(thread_id, actor["user"]["id"])
        if not thread:
            raise RuntimeError("Thread nao encontrada.")

        metadata = thread.get("metadata") or {}
        items = self._resolve_items(overrides.get("items") if overrides else None, metadata.get("pending_items") or [])
        if not items:
            raise RuntimeError("Nao ha itens pendentes para confirmar nesta conversa.")
        if thread.get("request_id"):
            return self.get_thread_payload(actor, thread_id)

        profile = actor["profile"]
        customer_name = profile.get("company_name") or profile.get("full_name") or actor["user"].get("email") or "Cliente Cotai"
        notes = str((overrides or {}).get("notes") or metadata.get("draft_notes") or metadata.get("last_user_message") or "Pedido criado pelo chatbot interno.")
        request_defaults = self.supabase.infer_request_defaults(
            notes=notes,
            items=items,
            priority=(overrides or {}).get("priority") or metadata.get("priority"),
        )
        duplicate_candidate = self.supabase.find_duplicate_request(company_id=profile["company_id"], items=items)
        request_row = self.supabase.create_internal_request(
            company_id=profile["company_id"],
            user_id=actor["user"]["id"],
            thread_id=thread_id,
            customer_name=customer_name,
            notes=notes,
            items=items,
            delivery_mode=(overrides or {}).get("delivery_mode") or metadata.get("delivery_mode"),
            delivery_location=(overrides or {}).get("delivery_location") or metadata.get("delivery_location"),
            project_name=(overrides or {}).get("project_name") or thread.get("title"),
            priority=request_defaults["priority"],
            sla_due_at=request_defaults["sla_due_at"],
            approval_required=request_defaults["approval_required"],
            approval_status=request_defaults["approval_status"],
            status=request_defaults["status"],
            duplicate_of_request_id=duplicate_candidate.get("request_id") if duplicate_candidate else None,
            duplicate_score=duplicate_candidate.get("score") if duplicate_candidate else None,
        )

        if request_defaults["approval_required"]:
            assistant_text = (
                f"Aqui e a Cota. Pedido {request_row['request_code']} registrado com prioridade {request_defaults['priority']}. "
                "Antes de eu tocar a cotacao, ele entrou em fila de aprovacao."
            )
        else:
            assistant_text = f"Aqui e a Cota. Pedido {request_row['request_code']} confirmado. Vou puxar a cotacao agora."

        if duplicate_candidate:
            assistant_text += (
                f" Encontrei um pedido parecido ({duplicate_candidate['request_code']}) "
                f"com similaridade de {int(float(duplicate_candidate['score']) * 100)}%."
            )

        self.supabase.insert_chat_message(
            thread_id,
            "assistant",
            assistant_text,
            {
                "status": request_row.get("status"),
                "request_id": request_row["id"],
                "request_code": request_row["request_code"],
                "duplicate_candidate": duplicate_candidate,
                "approval_required": request_defaults["approval_required"],
            },
        )
        self.supabase.update_chat_thread(
            thread_id,
            {
                "request_id": request_row["id"],
                "status": "PROCESSING" if request_row.get("status") != "AWAITING_APPROVAL" else "AWAITING_APPROVAL",
                "metadata": {
                    **metadata,
                    "request_code": request_row["request_code"],
                    "pending_items": items,
                    "delivery_mode": (overrides or {}).get("delivery_mode") or metadata.get("delivery_mode"),
                    "delivery_location": (overrides or {}).get("delivery_location") or metadata.get("delivery_location"),
                    "draft_notes": notes,
                    "priority": request_defaults["priority"],
                    "duplicate_candidate": duplicate_candidate,
                    "approval_required": request_defaults["approval_required"],
                    "timeline": self._append_timeline(
                        metadata,
                        "Pedido confirmado e enviado para cotacao."
                        if not request_defaults["approval_required"]
                        else "Pedido confirmado e aguardando aprovacao.",
                    ),
                },
            },
        )
        return self.get_thread_payload(actor, thread_id)

    def get_thread_payload(self, actor: dict[str, Any], thread_id: str) -> dict[str, Any]:
        thread = self.supabase.get_chat_thread(thread_id, actor["user"]["id"])
        if not thread:
            raise RuntimeError("Thread nao encontrada.")
        messages = self.supabase.list_chat_messages(thread_id)
        metadata = thread.get("metadata") or {}
        request_payload = None
        plan_usage = self.supabase.get_company_plan_context(actor["profile"]["company_id"], profile=actor["profile"])
        if thread.get("request_id"):
            request_payload = self.supabase.get_request_status_payload(thread["request_id"])
        live_construction_brain = self._build_live_construction_brain(metadata, request_payload)
        return {
            "thread": thread,
            "messages": messages,
            "request": request_payload["request"] if request_payload else None,
            "latest_quote": request_payload["latest_quote"] if request_payload else None,
            "results": request_payload["results"] if request_payload else [],
            "comparison": request_payload["comparison"] if request_payload else {"supplier_count": 0, "best_supplier": None, "suppliers": []},
            "request_items": request_payload["items"] if request_payload else [],
            "detected_items": metadata.get("pending_items") or [],
            "draft": {
                "title": thread.get("title"),
                "items": metadata.get("pending_items") or [],
                "delivery_mode": metadata.get("delivery_mode") or "",
                "delivery_location": metadata.get("delivery_location") or "",
                "notes": metadata.get("draft_notes") or metadata.get("last_user_message") or "",
                "priority": metadata.get("priority") or "MEDIUM",
                "saved_at": metadata.get("draft_saved_at"),
            },
            "timeline": metadata.get("timeline") or [],
            "notifications": self._build_notifications(metadata, request_payload["request"] if request_payload else None),
            "duplicate_candidate": metadata.get("duplicate_candidate"),
            "construction_context": metadata.get("construction_context") or {},
            "conversation_memory": metadata.get("construction_memory") or {},
            "construction_brain": live_construction_brain or metadata.get("construction_brain") or {},
            "plan_usage": plan_usage,
        }

    def _build_notifications(self, metadata: dict[str, Any], request_row: dict[str, Any] | None) -> list[dict[str, str]]:
        notifications: list[dict[str, str]] = []
        duplicate_candidate = metadata.get("duplicate_candidate")
        if duplicate_candidate:
            notifications.append(
                {
                    "tone": "warning",
                    "message": f"Pedido parecido detectado: {duplicate_candidate.get('request_code')}.",
                }
            )
        if request_row and request_row.get("approval_required") and str(request_row.get("approval_status") or "").upper() != "APPROVED":
            notifications.append({"tone": "warning", "message": "Pedido aguardando aprovacao administrativa."})
        if metadata.get("draft_saved_at"):
            notifications.append({"tone": "muted", "message": f"Rascunho salvo em {metadata.get('draft_saved_at')}"})
        notifications.extend(
            self.intelligence_service.build_notifications(memory=metadata.get("construction_memory"))
        )
        return notifications[:6]

    def _load_or_create_thread(self, actor: dict[str, Any], thread_id: str | None, first_message: str) -> dict[str, Any]:
        if thread_id:
            thread = self.supabase.get_chat_thread(thread_id, actor["user"]["id"])
            if not thread:
                raise RuntimeError("Thread nao encontrada.")
            return thread

        title = first_message[:72].strip() or "Nova cotacao"
        return self.supabase.create_chat_thread(
            user_id=actor["user"]["id"],
            company_id=actor["profile"]["company_id"],
            title=title,
            status="DRAFT",
            metadata={"timeline": [{"at": datetime.now(UTC).isoformat(), "label": "Rascunho iniciado."}]},
        )

    def _reset_thread_for_new_quote_cycle(self, thread: dict[str, Any]) -> dict[str, Any]:
        request_id = thread.get("request_id")
        if not request_id:
            return thread

        request_row = self.supabase.get_request_by_id(request_id)
        request_status = str((request_row or {}).get("status") or "").upper()
        if request_status not in {"DONE", "ERROR"}:
            return thread

        metadata = dict(thread.get("metadata") or {})
        cleaned_metadata = {
            **metadata,
            "pending_items": [],
            "duplicate_candidate": None,
            "request_code": None,
            "timeline": self._append_timeline(metadata, "Nova cotacao iniciada apos conclusao do ciclo anterior."),
        }
        updated = self.supabase.update_chat_thread(
            thread["id"],
            {
                "request_id": None,
                "status": "DRAFT",
                "metadata": cleaned_metadata,
            },
        )
        return updated or {**thread, "request_id": None, "status": "DRAFT", "metadata": cleaned_metadata}

    def _merge_items(self, existing: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in [*existing, *incoming]:
            key = str(item.get("normalized_name") or item.get("name") or item.get("raw") or "").strip().casefold()
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(item)
        return merged

    def _resolve_items(self, override_items: list[str | dict[str, Any]] | None, fallback_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not override_items:
            return fallback_items
        normalized = [self.parser._normalize_item(item) for item in override_items]  # noqa: SLF001
        return [item for item in normalized if item]

    def _append_timeline(self, metadata: dict[str, Any], label: str) -> list[dict[str, str]]:
        timeline = list(metadata.get("timeline") or [])
        timeline.append({"at": datetime.now(UTC).isoformat(), "label": label})
        return timeline[-8:]

    def _build_live_construction_brain(
        self,
        metadata: dict[str, Any],
        request_payload: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if not metadata.get("construction_context"):
            return metadata.get("construction_brain") or None

        base_brain = metadata.get("construction_brain") or {}
        execution_data = self.execution_insight_service.build_snapshot(request_payload=request_payload)
        if not base_brain:
            return {"execution": execution_data}

        financial = {**(base_brain.get("financial") or {})}
        operational = {**(base_brain.get("operational") or {})}
        predictive = {**(base_brain.get("predictive") or {})}

        if execution_data.get("tracked_materials"):
            operational["tracked_materials"] = execution_data["tracked_materials"]
        if execution_data.get("pending_materials") is not None:
            operational["pending_materials"] = execution_data["pending_materials"]
        if execution_data.get("completed_stage_count") is not None:
            operational["completed_stage_count"] = execution_data["completed_stage_count"]
        if execution_data.get("potential_savings"):
            financial["potential_savings_display"] = self.brain_service._format_brl_from_number(  # noqa: SLF001
                execution_data.get("potential_savings")
            )
        if execution_data.get("price_variation_pct") is not None:
            financial["price_variation_label"] = self.brain_service._format_variation(execution_data.get("price_variation_pct"))  # noqa: SLF001
        if execution_data.get("best_supplier_label"):
            predictive["best_supplier_label"] = execution_data["best_supplier_label"]
        if execution_data.get("supplier_delay_count"):
            predictive["supplier_delay_count"] = execution_data["supplier_delay_count"]
        if execution_data.get("latest_event_note"):
            predictive["latest_event_note"] = execution_data["latest_event_note"]
        if execution_data.get("latest_stage_label"):
            predictive["latest_stage_label"] = execution_data["latest_stage_label"]

        return {
            **base_brain,
            "operational": operational,
            "financial": financial,
            "predictive": predictive,
            "execution": execution_data,
        }
