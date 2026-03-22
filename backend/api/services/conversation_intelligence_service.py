from __future__ import annotations

import re
from typing import Any


class ConversationIntelligenceService:
    FIELD_LABELS = {
        "area_m2": "area",
        "project_type": "tipo de obra",
        "building_standard": "padrao",
        "floors": "pavimentos",
        "roof_type": "cobertura",
        "foundation_type": "fundacao",
        "location": "local",
        "bedrooms": "quartos",
        "bathrooms": "banheiros",
    }

    PHASE_KEYWORDS = {
        "foundation": ("fundacao", "fundação", "baldrame", "alicerce"),
        "structure": ("estrutura", "pilares", "vigas"),
        "masonry": ("alvenaria", "bloco", "blocos", "vedacao", "vedação"),
        "roof": ("cobertura", "telhado", "telha", "laje"),
        "hydraulic": ("hidraulica", "hidráulica", "agua", "água", "esgoto"),
        "electrical": ("eletrica", "elétrica", "fios", "quadro", "tomadas"),
        "finishing": ("acabamento", "acabamentos", "piso", "pintura", "revestimento"),
        "demolition": ("demolicao", "demolição", "quebra", "remocao"),
        "wall_foundation": ("fundacao do muro", "base do muro"),
        "wall_masonry": ("muro", "elevacao do muro"),
        "wall_finish": ("acabamento do muro", "reboco do muro"),
        "pavement_base": ("base da calcada", "base da calçada"),
        "pavement_finish": ("concretagem", "calcada", "calçada"),
        "screed_base": ("base do contrapiso",),
        "screed_finish": ("contrapiso",),
    }

    def classify_intent(
        self,
        *,
        message: str,
        metadata: dict[str, Any] | None = None,
        parsed_items: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        text = str(message or "").strip().lower()
        metadata = metadata or {}
        parsed_items = parsed_items or []
        has_construction_context = bool(metadata.get("construction_context"))
        selected_phase = self.detect_selected_phase(text)

        procurement_tokens = (
            "lista de compra",
            "comprar",
            "compra",
            "cotar",
            "cotacao",
            "cotação",
            "materiais",
            "insumos",
            "pacote",
            "fase",
        )
        refinement_tokens = (
            "campinas",
            "rio preto",
            "cidade",
            "regiao",
            "região",
            "fundacao",
            "fundação",
            "sapata",
            "radier",
            "estaca",
            "bloco",
            "telha",
            "laje",
            "fibrocimento",
            "metalica",
            "metálica",
            "ceramica",
            "cerâmica",
            "economico",
            "econômico",
            "medio",
            "médio",
            "alto",
            "quarto",
            "banheiro",
            "pavimento",
        )
        guidance_tokens = (
            "como",
            "comec",
            "iniciar",
            "fazer",
            "construir",
            "executar",
            "planejar",
            "organizar",
            "etapa",
            "fases",
        )
        project_tokens = (
            "casa",
            "sobrado",
            "predio",
            "prédio",
            "edificio",
            "edifício",
            "torre",
            "residencia",
            "residência",
            "residencial",
            "obra",
            "reforma",
            "muro",
            "calcada",
            "calçada",
            "contrapiso",
            "galpao",
            "galpão",
            "comercial",
        )

        has_project_signal = any(token in text for token in project_tokens)
        has_scope_signal = bool(re.search(r"\b\d+\s*(?:m2|andares|andar|pavimentos|pavimento)\b", text))
        looks_like_construction = has_project_signal or has_scope_signal
        asks_procurement = any(token in text for token in procurement_tokens)
        asks_guidance = any(token in text for token in guidance_tokens)
        looks_like_refinement = has_construction_context and any(token in text for token in refinement_tokens)
        looks_like_project_statement = (has_project_signal or has_scope_signal) and (
            asks_guidance
            or any(token in text for token in ("quero", "preciso", "pretendo", "vou", "desejo"))
        )

        if has_construction_context and asks_procurement:
            return {"mode": "construction_procurement", "selected_phase": selected_phase}
        if looks_like_project_statement:
            return {"mode": "construction_guidance", "selected_phase": None}
        if looks_like_refinement:
            return {"mode": "construction_refinement", "selected_phase": None}
        if parsed_items:
            return {"mode": "material_quote", "selected_phase": None}
        if looks_like_construction and asks_procurement:
            return {"mode": "construction_procurement", "selected_phase": selected_phase}
        if looks_like_construction or (has_construction_context and asks_guidance):
            return {"mode": "construction_guidance", "selected_phase": None}
        return {"mode": "general_guidance", "selected_phase": None}

    def build_construction_memory(
        self,
        *,
        previous_context: dict[str, Any] | None,
        analysis: dict[str, Any],
        intent_mode: str,
        message: str,
    ) -> dict[str, Any]:
        previous_context = previous_context or {}
        conversation = analysis.get("conversation") or {}
        current_context = conversation.get("context") or analysis.get("project") or {}
        learned_facts = self._collect_learned_facts(previous_context, current_context)
        conflicts = self._collect_conflicts(previous_context, current_context, message)
        confidence = self._build_confidence(analysis)
        next_action = self._infer_next_action(intent_mode=intent_mode, analysis=analysis)
        return {
            "last_intent": intent_mode,
            "confidence": confidence,
            "conflicts": conflicts,
            "learned_facts": learned_facts,
            "next_action": next_action,
            "last_message": message,
            "context": current_context,
        }

    def build_notifications(
        self,
        *,
        memory: dict[str, Any] | None,
    ) -> list[dict[str, str]]:
        if not memory:
            return []
        notifications: list[dict[str, str]] = []
        confidence = memory.get("confidence") or {}
        if confidence.get("score") is not None:
            tone = "warning" if float(confidence.get("score") or 0) < 70 else "info"
            notifications.append(
                {
                    "tone": tone,
                    "message": f"Leitura da obra com confianca {confidence.get('label', 'media')} ({int(float(confidence.get('score') or 0))}%).",
                }
            )
        for conflict in memory.get("conflicts") or []:
            notifications.append(
                {
                    "tone": "warning",
                    "message": f"{conflict.get('label')}: antes '{conflict.get('previous')}', agora '{conflict.get('current')}'.",
                }
            )
        next_action = memory.get("next_action") or {}
        if next_action.get("label"):
            notifications.append({"tone": "info", "message": f"Proximo passo sugerido: {next_action['label']}."})
        return notifications[:4]

    def build_procurement_draft_items(self, procurement: dict[str, Any]) -> list[dict[str, Any]]:
        selected_phase_key = procurement.get("selected_phase_key")
        phase_packages = list(procurement.get("phase_packages") or [])
        selected_phase = next((phase for phase in phase_packages if phase.get("key") == selected_phase_key), None)
        source_items = list((selected_phase or {}).get("items") or [])
        if not source_items:
            source_items = list(procurement.get("purchase_list") or [])
        rows: list[dict[str, Any]] = []
        for item in source_items[:12]:
            name = str(item.get("material") or "").strip()
            if not name:
                continue
            quantity = item.get("quantity")
            try:
                quantity = float(quantity) if quantity is not None else None
            except (TypeError, ValueError):
                quantity = None
            rows.append(
                {
                    "name": name,
                    "normalized_name": name,
                    "quantity": quantity,
                    "unit": str(item.get("unit") or "un").strip(),
                    "raw": self._build_raw_item_line(name, quantity, str(item.get("unit") or "un").strip()),
                }
            )
        return rows

    def detect_selected_phase(self, text: str) -> str | None:
        lowered = str(text or "").lower()
        for phase_key, keywords in self.PHASE_KEYWORDS.items():
            if any(keyword in lowered for keyword in keywords):
                return phase_key
        return None

    def _collect_learned_facts(self, previous_context: dict[str, Any], current_context: dict[str, Any]) -> list[dict[str, str]]:
        facts: list[dict[str, str]] = []
        for field, label in self.FIELD_LABELS.items():
            previous_value = self._stringify_value(previous_context.get(field))
            current_value = self._stringify_value(current_context.get(field))
            if not current_value or previous_value == current_value:
                continue
            if previous_value:
                continue
            facts.append({"field": field, "label": label, "value": current_value})
        return facts[:6]

    def _collect_conflicts(self, previous_context: dict[str, Any], current_context: dict[str, Any], message: str) -> list[dict[str, str]]:
        conflicts: list[dict[str, str]] = []
        lowered = str(message or "").lower()
        for field, label in self.FIELD_LABELS.items():
            previous_value = self._stringify_value(previous_context.get(field))
            current_value = self._stringify_value(current_context.get(field))
            if not previous_value or not current_value or previous_value == current_value:
                continue
            if field == "area_m2" and not re.search(r"\d+(?:[.,]\d+)?\s*m2\b", lowered):
                continue
            conflicts.append(
                {
                    "field": field,
                    "label": label,
                    "previous": previous_value,
                    "current": current_value,
                }
            )
        return conflicts[:4]

    def _build_confidence(self, analysis: dict[str, Any]) -> dict[str, Any]:
        conversation = analysis.get("conversation") or {}
        answered = len(conversation.get("answered_fields") or [])
        pending = len(conversation.get("pending_fields") or [])
        total = answered + pending
        base_score = round((answered / total) * 100, 1) if total else 0.0

        summary = analysis.get("summary") or {}
        pricing_strength = str(summary.get("pricing_strength") or "unavailable")
        if pricing_strength == "strong":
            base_score = min(100.0, base_score + 10)
        elif pricing_strength == "moderate":
            base_score = min(100.0, base_score + 5)

        label = "baixa"
        if base_score >= 85:
            label = "alta"
        elif base_score >= 60:
            label = "media"

        return {
            "score": base_score,
            "label": label,
            "pricing_strength": pricing_strength,
        }

    def _infer_next_action(self, *, intent_mode: str, analysis: dict[str, Any]) -> dict[str, str]:
        next_questions = [str(item).strip() for item in analysis.get("next_questions") or [] if str(item).strip()]
        if intent_mode == "construction_procurement":
            return {"key": "confirm_procurement", "label": "revisar a lista inicial de compra e confirmar a fase"}
        if next_questions:
            return {"key": "answer_questions", "label": next_questions[0]}
        return {"key": "advance_procurement", "label": "transformar a obra em lista de compra ou cotacao por fase"}

    def _build_raw_item_line(self, name: str, quantity: float | None, unit: str) -> str:
        if quantity is None:
            return name
        quantity_display = int(quantity) if float(quantity).is_integer() else round(float(quantity), 2)
        return f"{quantity_display} {unit} {name}".strip()

    def _stringify_value(self, value: Any) -> str:
        if value in (None, ""):
            return ""
        if isinstance(value, float):
            if value.is_integer():
                return str(int(value))
            return str(round(value, 2))
        return str(value).strip()
