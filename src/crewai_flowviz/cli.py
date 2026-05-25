"""Command line interface for crewai-flowviz."""

from __future__ import annotations

import argparse
from dataclasses import replace
import os
from pathlib import Path
import sys

from crewai_flowviz.config import load_config
from crewai_flowviz.exporters import infer_format, render_json, write_output
from crewai_flowviz.extractor import extract_flow_graph, import_flow
from crewai_flowviz.models import RenderConfig
from crewai_flowviz.studio import serve_studio
from crewai_flowviz.themes import get_theme, list_themes


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 2
    try:
        args.func(args)
    except Exception as exc:
        print(f"crewai-flowviz: error: {exc}", file=sys.stderr)
        return 1
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="crewai-flowviz")
    sub = parser.add_subparsers(dest="command")

    render = sub.add_parser("render", help="Render a CrewAI Flow to SVG, PNG, JSON, or DOT")
    _flow_args(render)
    _render_args(render)
    render.set_defaults(func=_render)

    inspect_cmd = sub.add_parser("inspect", help="Print extracted graph JSON")
    _flow_args(inspect_cmd)
    inspect_cmd.set_defaults(func=_inspect)

    themes = sub.add_parser("themes", help="List built-in themes")
    themes.set_defaults(func=_themes)

    studio = sub.add_parser("studio", help="Open a local interactive configuration UI")
    _flow_args(studio)
    _render_args(studio, output=False)
    studio.add_argument("--host", default="127.0.0.1")
    studio.add_argument("--port", type=int, default=8765)
    studio.add_argument("--no-open", action="store_true")
    studio.set_defaults(func=_studio)
    return parser


def _flow_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("flow", help="Flow import spec, e.g. package.module:MyFlow")
    parser.add_argument("--cwd", default=None, help="Change working directory before importing")
    parser.add_argument("--pythonpath", action="append", default=[], help="Add a path to sys.path before importing")


def _render_args(parser: argparse.ArgumentParser, *, output: bool = True) -> None:
    if output:
        parser.add_argument("--out", default="flow.svg", help="Output file path")
        parser.add_argument("--format", choices=["svg", "png", "json", "dot"], default=None)
    parser.add_argument("--config", default=None, help="JSON or TOML config file")
    parser.add_argument("--theme", choices=list_themes(), default=None)
    parser.add_argument("--direction", choices=["vertical", "horizontal"], default=None)
    parser.add_argument("--width", type=int, default=None)
    parser.add_argument("--height", type=int, default=None)
    parser.add_argument("--node-width", type=int, default=None)
    parser.add_argument("--rank-gap", type=int, default=None)
    parser.add_argument("--node-gap", type=int, default=None)
    parser.add_argument("--margin", type=int, default=None)
    parser.add_argument("--title", default=None)
    parser.add_argument("--no-grid", action="store_true")
    parser.add_argument("--no-edge-labels", action="store_true")
    parser.add_argument("--source-refs", action="store_true")
    parser.add_argument("--transparent", action="store_true", help="Export without the theme background color")


def _prepare_import(args: argparse.Namespace) -> None:
    if args.cwd:
        os.chdir(args.cwd)
        sys.path.insert(0, args.cwd)
    for path in reversed(args.pythonpath):
        sys.path.insert(0, path)


def _load_graph(args: argparse.Namespace):
    _prepare_import(args)
    flow = import_flow(args.flow)
    return extract_flow_graph(flow)


def _config(args: argparse.Namespace) -> tuple[RenderConfig, dict[str, object]]:
    config, theme_overrides = load_config(args.config)
    values: dict[str, object] = {}
    for attr, arg_name in [
        ("theme", "theme"),
        ("direction", "direction"),
        ("width", "width"),
        ("height", "height"),
        ("node_width", "node_width"),
        ("rank_gap", "rank_gap"),
        ("node_gap", "node_gap"),
        ("margin", "margin"),
        ("title", "title"),
    ]:
        value = getattr(args, arg_name, None)
        if value is not None:
            values[attr] = value
    if getattr(args, "no_grid", False):
        values["show_grid"] = False
    if getattr(args, "no_edge_labels", False):
        values["show_edge_labels"] = False
    if getattr(args, "source_refs", False):
        values["show_source_refs"] = True
    if getattr(args, "transparent", False):
        values["export_background"] = False
    return replace(config, **values), theme_overrides


def _render(args: argparse.Namespace) -> None:
    graph = _load_graph(args)
    config, theme_overrides = _config(args)
    output = Path(args.out)
    fmt = infer_format(output, args.format)
    theme = get_theme(config.theme, theme_overrides)
    write_output(graph, output, fmt, config, theme)
    print(f"[render] wrote {output}")


def _inspect(args: argparse.Namespace) -> None:
    graph = _load_graph(args)
    print(render_json(graph))


def _themes(args: argparse.Namespace) -> None:
    for theme in list_themes():
        print(theme)


def _studio(args: argparse.Namespace) -> None:
    graph = _load_graph(args)
    config, theme_overrides = _config(args)
    serve_studio(
        graph,
        config,
        theme_overrides,
        host=args.host,
        port=args.port,
        open_browser=not args.no_open,
    )


if __name__ == "__main__":
    raise SystemExit(main())
