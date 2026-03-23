from __future__ import annotations

from copy import deepcopy

from .design_brain import enrich_project
from .layout_engine import layout_project
from .models import ProjectSpec
from .quality_engine import score_project


VARIANT_LIBRARY = [
    {
        "id": "compacto",
        "label": "Layout Compacto",
        "strategy_suffix": "compacto",
        "constraints": {
            "variant_mode": "compact",
            "social_spacing": 0.22,
            "wet_stack_bias": "tight",
            "private_distribution": "dense",
        },
    },
    {
        "id": "integrado",
        "label": "Ambientes Integrados",
        "strategy_suffix": "integrado",
        "constraints": {
            "variant_mode": "integrated",
            "social_spacing": 0.42,
            "wet_stack_bias": "balanced",
            "private_distribution": "suite_clusters",
        },
    },
    {
        "id": "classico",
        "label": "Distribuicao Classica",
        "strategy_suffix": "classico",
        "constraints": {
            "variant_mode": "classic",
            "social_spacing": 0.32,
            "wet_stack_bias": "stacked",
            "private_distribution": "symmetrical",
        },
    },
]


def _prepare_variant(project: ProjectSpec, variant: dict[str, object]) -> ProjectSpec:
    cloned = deepcopy(project)
    merged_constraints = dict(cloned.constraints or {})
    merged_constraints.update(variant["constraints"])
    cloned.constraints = merged_constraints
    cloned.design_strategy = (
        f"{cloned.design_strategy}_{variant['strategy_suffix']}"
        if cloned.design_strategy
        else str(variant["strategy_suffix"])
    )
    cloned.processing_notes = list(cloned.processing_notes or []) + [
        f"Variant mode: {variant['id']}."
    ]
    return layout_project(enrich_project(cloned))


def generate_project_variants(project: ProjectSpec) -> list[dict[str, object]]:
    variants: list[dict[str, object]] = []
    for variant in VARIANT_LIBRARY:
        solved = _prepare_variant(project, variant)
        score = score_project(solved)
        variants.append(
            {
                "id": str(variant["id"]),
                "label": str(variant["label"]),
                "project": solved,
                "quality_score": score,
            }
        )

    variants.sort(key=lambda item: item["quality_score"]["overall_score"], reverse=True)
    return variants
