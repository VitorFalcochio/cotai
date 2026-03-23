from __future__ import annotations

import argparse
import json
from pathlib import Path

from autocad_ia.models import ProjectSpec
from autocad_ia.service import build_project_from_text, export_project_to_dxf


def load_project_from_json(path: Path) -> ProjectSpec:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return ProjectSpec.from_dict(payload)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Beta da AUTOCAD IA para gerar plantas 2D em DXF."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    from_json = subparsers.add_parser("from-json", help="Gera um DXF a partir de um JSON estruturado.")
    from_json.add_argument("input_path", type=Path)
    from_json.add_argument("output_path", type=Path)

    from_text = subparsers.add_parser("from-text", help="Gera um DXF a partir de uma descricao em texto.")
    from_text.add_argument("description", type=str)
    from_text.add_argument("output_path", type=Path)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "from-json":
      project = load_project_from_json(args.input_path)
      export_project_to_dxf(project, args.output_path)
      print(f"DXF gerado em: {args.output_path}")
      return 0

    if args.command == "from-text":
      project = build_project_from_text(args.description)
      export_project_to_dxf(project, args.output_path)
      print(f"DXF gerado em: {args.output_path}")
      return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
