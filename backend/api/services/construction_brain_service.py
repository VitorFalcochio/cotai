from __future__ import annotations

import re
from typing import Any


class ConstructionBrainService:
    def build_snapshot(
        self,
        *,
        analysis: dict[str, Any],
        procurement: dict[str, Any] | None,
        memory: dict[str, Any] | None,
        metadata: dict[str, Any] | None,
        latest_message: str,
        execution_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        memory = memory or {}
        metadata = metadata or {}
        execution_data = execution_data or {}
        project = analysis.get("project") or {}
        summary = analysis.get("summary") or {}
        conversation = analysis.get("conversation") or {}
        next_questions = [str(item).strip() for item in analysis.get("next_questions") or [] if str(item).strip()]
        conflicts = list(memory.get("conflicts") or [])
        learned_facts = list(memory.get("learned_facts") or [])
        budget_target_cents = self._extract_budget_target_cents(latest_message, metadata)
        estimated_total_cents = summary.get("estimated_total_cost_cents")

        technical = {
            "title": "Memoria tecnica",
            "project_label": project.get("project_label") or project.get("project_type") or "obra",
            "area_label": f"{project.get('area_m2')} m2" if project.get("area_m2") else "Pendente",
            "location_label": project.get("location") or "Pendente",
            "foundation_label": project.get("foundation_type") or "Pendente",
            "readiness_label": "Escopo fechado" if not next_questions else "Escopo em refinamento",
            "learned_facts": learned_facts[:4],
            "conflict_count": len(conflicts),
        }

        selected_phase_key = str((procurement or {}).get("selected_phase_key") or "")
        phase_packages = list((procurement or {}).get("phase_packages") or [])
        selected_phase = next((phase for phase in phase_packages if phase.get("key") == selected_phase_key), None)
        operational = {
            "title": "Decisao operacional",
            "current_stage": conversation.get("stage") or summary.get("workflow_stage") or "scope",
            "next_action_label": (memory.get("next_action") or {}).get("label") or "Refinar a obra",
            "selected_phase_label": selected_phase.get("title") if selected_phase else None,
            "draft_item_count": len(metadata.get("pending_items") or []),
            "blockers": next_questions[:3],
            "purchase_window_label": self._infer_purchase_window(procurement, memory),
            "tracked_materials": execution_data.get("tracked_materials") or 0,
            "pending_materials": execution_data.get("pending_materials") or 0,
        }

        variance_cents = None
        variance_label = None
        budget_health = "Sem meta definida"
        if isinstance(budget_target_cents, int) and isinstance(estimated_total_cents, int):
            variance_cents = estimated_total_cents - budget_target_cents
            variance_label = self._format_brl_from_cents(abs(variance_cents))
            if variance_cents > 0:
                budget_health = "Acima da meta"
            elif variance_cents < 0:
                budget_health = "Abaixo da meta"
            else:
                budget_health = "Na meta"

        financial = {
            "title": "Financeiro",
            "estimated_total_display": summary.get("estimated_total_cost_display") or "Sem custo fechado",
            "budget_target_display": self._format_brl_from_cents(budget_target_cents) if isinstance(budget_target_cents, int) else "Nao informado",
            "budget_health": budget_health,
            "variance_display": variance_label,
            "pricing_coverage_pct": summary.get("pricing_coverage_pct") or 0,
            "pricing_strength_label": summary.get("pricing_strength_label") or "Sem confianca de preco",
            "potential_savings_display": self._format_brl_from_number(execution_data.get("potential_savings")),
            "price_variation_label": self._format_variation(execution_data.get("price_variation_pct")),
        }

        predictive_risks = self._build_predictive_risks(
            next_questions=next_questions,
            conflicts=conflicts,
            summary=summary,
            procurement=procurement,
        )
        predictive = {
            "title": "Visao preditiva",
            "risk_level": self._classify_risk_level(predictive_risks),
            "risks": predictive_risks[:4],
            "next_7_days": self._build_next_7_days(procurement, analysis),
            "best_supplier_label": execution_data.get("best_supplier_label"),
        }

        return {
            "technical": technical,
            "operational": operational,
            "financial": financial,
            "predictive": predictive,
        }

    def _extract_budget_target_cents(self, message: str, metadata: dict[str, Any]) -> int | None:
        existing = metadata.get("budget_target_cents")
        if isinstance(existing, int) and existing > 0:
            return existing
        text = str(message or "").lower()
        match = re.search(r"orcamento(?: de)?\s*r?\$?\s*(\d+(?:[.,]\d+)?)\s*(mil|milhao|milhões|milhoes)?", text)
        if not match:
            return None
        raw_value = float(match.group(1).replace(".", "").replace(",", "."))
        scale = match.group(2) or ""
        if "milhao" in scale or "milh" in scale:
            raw_value *= 1_000_000
        elif "mil" in scale:
            raw_value *= 1_000
        return int(round(raw_value * 100))

    def _infer_purchase_window(self, procurement: dict[str, Any] | None, memory: dict[str, Any]) -> str:
        if procurement and procurement.get("purchase_list"):
            return "Comprar agora para destravar a fase"
        confidence = (memory.get("confidence") or {}).get("score")
        if confidence is not None and float(confidence) >= 85:
            return "Janela boa para avancar compra guiada"
        return "Refinar antes de comprar"

    def _build_predictive_risks(
        self,
        *,
        next_questions: list[str],
        conflicts: list[dict[str, Any]],
        summary: dict[str, Any],
        procurement: dict[str, Any] | None,
    ) -> list[str]:
        risks: list[str] = []
        if next_questions:
            risks.append("Escopo ainda aberto pode gerar retrabalho na compra.")
        if conflicts:
            risks.append("Mudancas recentes no escopo podem invalidar quantitativos anteriores.")
        if float(summary.get("pricing_coverage_pct") or 0) < 50:
            risks.append("Cobertura de precos ainda baixa para tomada de decisao financeira forte.")
        if procurement and not (procurement.get("purchase_list") or []):
            risks.append("Lista de compra ainda nao consolidada para a fase selecionada.")
        if str(summary.get("pricing_strength") or "") == "weak":
            risks.append("Base de preco fraca; valide antes de fechar fornecedor.")
        return risks or ["Sem risco critico identificado neste momento."]

    def _classify_risk_level(self, risks: list[str]) -> str:
        if not risks or risks == ["Sem risco critico identificado neste momento."]:
            return "baixo"
        if len(risks) >= 4:
            return "alto"
        if len(risks) >= 2:
            return "medio"
        return "baixo"

    def _build_next_7_days(self, procurement: dict[str, Any] | None, analysis: dict[str, Any]) -> list[str]:
        if procurement and procurement.get("purchase_list"):
            return [
                "Revisar a lista inicial da fase priorizada.",
                "Confirmar quantidades e especificacoes antes da cotacao.",
                "Acionar fornecedores principais da fase selecionada.",
            ]
        if analysis.get("next_questions"):
            return [
                "Fechar os dados pendentes da obra.",
                "Refinar fundacao, local e padrao onde faltar.",
                "So depois avancar para compra ou cotacao.",
            ]
        return [
            "Transformar a previsao em pacote de compra por fase.",
            "Comparar fornecedores com foco em prazo e risco.",
            "Conferir impacto da compra no custo total estimado.",
        ]

    def _format_brl_from_cents(self, value_cents: int | None) -> str:
        if value_cents is None:
            return "Nao informado"
        raw = f"{value_cents / 100:,.2f}"
        return "R$ " + raw.replace(",", "X").replace(".", ",").replace("X", ".")

    def _format_brl_from_number(self, value: Any) -> str | None:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return None
        raw = f"{numeric:,.2f}"
        return "R$ " + raw.replace(",", "X").replace(".", ",").replace("X", ".")

    def _format_variation(self, value: Any) -> str | None:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return None
        signal = "+" if numeric > 0 else ""
        return f"{signal}{numeric:.1f}%"
