"""Alternate graph export formats."""

from __future__ import annotations

import json
import re
from pathlib import Path

from crewai_flowviz.models import FlowGraph, RenderConfig, Theme
from crewai_flowviz.png import render_png_bytes
from crewai_flowviz.svg import render_svg


def render_json(graph: FlowGraph, *, indent: int = 2) -> str:
    return json.dumps(graph.to_dict(), indent=indent)


def render_dot(graph: FlowGraph) -> str:
    lines = ["digraph Flow {", "  graph [rankdir=TB, splines=ortho];", "  node [shape=box];"]
    for node in graph.nodes:
        attrs = {"label": node.label, "class": node.kind}
        lines.append(f"  {_dot_id(node.id)} [{_dot_attrs(attrs)}];")
    for edge in graph.edges:
        attrs = {"label": edge.label}
        if edge.kind == "router":
            attrs["style"] = "dashed"
            attrs["color"] = "#ff5a50"
        elif edge.kind == "and":
            attrs["color"] = "#ff5a50"
        elif edge.back:
            attrs["style"] = "dashed"
            attrs["color"] = "#7c3aed"
        lines.append(f"  {_dot_id(edge.source)} -> {_dot_id(edge.target)} [{_dot_attrs(attrs)}];")
    lines.append("}")
    return "\n".join(lines)


def write_output(
    graph: FlowGraph,
    output: Path,
    fmt: str,
    config: RenderConfig,
    theme: Theme,
) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "svg":
        output.write_text(render_svg(graph, config, theme), encoding="utf-8")
    elif fmt == "json":
        output.write_text(render_json(graph), encoding="utf-8")
    elif fmt == "dot":
        output.write_text(render_dot(graph), encoding="utf-8")
    elif fmt == "png":
        output.write_bytes(render_png_bytes(graph, config, theme))
    else:
        raise ValueError(f"unsupported format: {fmt}")
    return output


def infer_format(output: Path, explicit: str | None = None) -> str:
    if explicit:
        return explicit.lower()
    suffix = output.suffix.lower().lstrip(".")
    if suffix in {"svg", "png", "json", "dot"}:
        return suffix
    return "svg"


def _dot_id(value: str) -> str:
    if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", value):
        return value
    return json.dumps(value)


def _dot_attrs(attrs: dict[str, str]) -> str:
    pairs = []
    for key, value in attrs.items():
        if not value:
            continue
        pairs.append(f"{key}={json.dumps(value)}")
    return ", ".join(pairs)
