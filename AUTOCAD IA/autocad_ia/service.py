from __future__ import annotations

from pathlib import Path

from .variant_solver import generate_project_variants
from .design_brain import enrich_project
from .dxf_writer import write_project_dxf
from .layout_engine import layout_project
from .models import ProjectSpec
from .text_parser import parse_project_from_text


def build_project_from_text(description: str) -> ProjectSpec:
    project = parse_project_from_text(description)
    project = enrich_project(project)
    return layout_project(project)


def export_project_to_dxf(project: ProjectSpec, output_path: Path) -> Path:
    prepared = enrich_project(project)
    laid_out = layout_project(prepared)
    return write_project_dxf(laid_out, output_path)


def build_project_variants_from_text(description: str) -> list[dict[str, object]]:
    project = parse_project_from_text(description)
    project = enrich_project(project)
    return generate_project_variants(project)
