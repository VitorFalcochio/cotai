from __future__ import annotations

from pathlib import Path

from .dxf_writer import write_project_dxf
from .layout_engine import layout_project
from .models import ProjectSpec
from .text_parser import parse_project_from_text


def build_project_from_text(description: str) -> ProjectSpec:
    project = parse_project_from_text(description)
    return layout_project(project)


def export_project_to_dxf(project: ProjectSpec, output_path: Path) -> Path:
    laid_out = layout_project(project)
    return write_project_dxf(laid_out, output_path)
