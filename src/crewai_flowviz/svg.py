"""SVG renderer for FlowGraph objects."""

from __future__ import annotations

from collections import defaultdict
from html import escape
from math import ceil

from crewai_flowviz.layout import GraphLayout, LayoutNode, layout_graph
from crewai_flowviz.models import Edge, FlowGraph, RenderConfig, Theme
from crewai_flowviz.themes import get_theme


def render_svg(
    graph: FlowGraph,
    config: RenderConfig | None = None,
    theme: Theme | None = None,
    theme_overrides: dict[str, object] | None = None,
) -> str:
    config = config or RenderConfig()
    theme = theme or get_theme(config.theme, theme_overrides)
    layout = layout_graph(graph, config)
    width, height = _viewport_size(layout, config)

    parts: list[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        _svg_open(width, height, layout, config),
        _defs(theme),
    ]
    if config.export_background:
        parts.append(f'<rect width="100%" height="100%" fill="{theme.background}"/>')
    if config.show_grid:
        parts.append(_grid(layout, theme))
    if config.title:
        parts.append(_title(config.title, config, theme))
    parts.append(_node_shadows(graph, layout, config, theme))
    parts.append(_edges(graph, layout, config, theme, labels_only=False))
    parts.append(_nodes(graph, layout, config, theme))
    parts.append(_edges(graph, layout, config, theme, labels_only=True))
    parts.append("</svg>")
    return "\n".join(parts)


def _viewport_size(layout: GraphLayout, config: RenderConfig) -> tuple[str, str]:
    natural_w = int(ceil(layout.width))
    natural_h = int(ceil(layout.height))
    if config.width and config.height:
        return str(config.width), str(config.height)
    if config.width:
        scaled_h = max(1, round(config.width * natural_h / natural_w))
        return str(config.width), str(scaled_h)
    if config.height:
        scaled_w = max(1, round(config.height * natural_w / natural_h))
        return str(scaled_w), str(config.height)
    return str(natural_w), str(natural_h)


def _svg_open(width: str, height: str, layout: GraphLayout, config: RenderConfig) -> str:
    view_box = f'0 0 {ceil(layout.width)} {ceil(layout.height)}'
    preserve = "xMidYMid meet" if config.fit else "xMinYMin meet"
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="{view_box}" preserveAspectRatio="{preserve}" role="img">'
    )


def _defs(theme: Theme) -> str:
    markers = []
    for name, color in {
        "edge": theme.edge,
        "and": theme.edge_and,
        "router": theme.edge_router,
        "back": theme.edge_back,
    }.items():
        markers.append(
            f'<marker id="arrow-{name}" viewBox="0 0 12 12" refX="10" refY="6" '
            f'markerWidth="8" markerHeight="8" orient="auto-start-reverse">'
            f'<path d="M 1 1 L 11 6 L 1 11 z" fill="{color}"/></marker>'
        )
    return (
        "<defs>"
        '<filter id="node-shadow" x="-20%" y="-20%" width="140%" height="140%">'
        f'<feDropShadow dx="4" dy="5" stdDeviation="0" flood-color="{theme.shadow}" flood-opacity="0.9"/>'
        "</filter>"
        + "".join(markers)
        + "</defs>"
    )


def _grid(layout: GraphLayout, theme: Theme) -> str:
    step = 24
    lines = [f'<g stroke="{theme.grid}" stroke-width="1">']
    for x in range(0, int(layout.width) + step, step):
        lines.append(f'<line x1="{x}" y1="0" x2="{x}" y2="{ceil(layout.height)}"/>')
    for y in range(0, int(layout.height) + step, step):
        lines.append(f'<line x1="0" y1="{y}" x2="{ceil(layout.width)}" y2="{y}"/>')
    lines.append("</g>")
    return "\n".join(lines)


def _title(title: str, config: RenderConfig, theme: Theme) -> str:
    return (
        f'<text x="{config.margin}" y="34" font-family="{escape(config.font_family)}" '
        f'font-size="22" font-weight="750" fill="{theme.text}">{escape(title)}</text>'
    )


def _edges(
    graph: FlowGraph,
    layout: GraphLayout,
    config: RenderConfig,
    theme: Theme,
    *,
    labels_only: bool,
) -> str:
    parts: list[str] = ['<g fill="none">']
    and_groups: dict[str, list[Edge]] = defaultdict(list)
    grouped_and_ids: set[tuple[str, str, str]] = set()
    for edge in graph.edges:
        if edge.kind == "and" and not edge.back:
            and_groups[edge.target].append(edge)

    for target, edges in and_groups.items():
        if len(edges) > 1:
            parts.append(_and_group(target, edges, layout, config, theme, labels_only=labels_only))
            for edge in edges:
                grouped_and_ids.add((edge.source, edge.target, edge.label))

    back_lane = 0
    for edge in graph.edges:
        if (edge.source, edge.target, edge.label) in grouped_and_ids:
            continue
        if edge.back:
            parts.append(_back_edge(edge, layout, config, theme, back_lane, labels_only=labels_only))
            back_lane += 1
        else:
            parts.append(_regular_edge(edge, layout, config, theme, labels_only=labels_only))
    parts.append("</g>")
    return "\n".join(parts)


def _and_group(
    target: str,
    edges: list[Edge],
    layout: GraphLayout,
    config: RenderConfig,
    theme: Theme,
    *,
    labels_only: bool,
) -> str:
    if target not in layout.nodes:
        return ""
    target_node = layout.nodes[target]
    source_nodes = [layout.nodes[edge.source] for edge in edges if edge.source in layout.nodes]
    if not source_nodes:
        return ""

    parts: list[str] = []
    if not labels_only:
        parts.append(f'<g stroke="{theme.edge_and}" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">')
    if config.direction == "horizontal":
        join_x = target_node.x - target_node.width / 2 - config.rank_gap * 0.34
        if not labels_only:
            for source in source_nodes:
                start = _right(source)
                path = f"M {start[0]:.1f} {start[1]:.1f} L {join_x:.1f} {start[1]:.1f} L {join_x:.1f} {target_node.y:.1f}"
                parts.append(f'<path d="{path}"/>')
        end = _left(target_node)
        if not labels_only:
            parts.append(
                f'<path d="M {join_x:.1f} {target_node.y:.1f} L {end[0]:.1f} {end[1]:.1f}" marker-end="url(#arrow-and)"/>'
            )
        label_at = (join_x, target_node.y)
    else:
        join_y = target_node.y - target_node.height / 2 - config.rank_gap * 0.34
        if not labels_only:
            for source in source_nodes:
                start = _bottom(source)
                path = f"M {start[0]:.1f} {start[1]:.1f} L {start[0]:.1f} {join_y:.1f} L {target_node.x:.1f} {join_y:.1f}"
                parts.append(f'<path d="{path}"/>')
        end = _top(target_node)
        if not labels_only:
            parts.append(
                f'<path d="M {target_node.x:.1f} {join_y:.1f} L {end[0]:.1f} {end[1]:.1f}" marker-end="url(#arrow-and)"/>'
            )
        label_at = (target_node.x, join_y)
    if not labels_only:
        parts.append("</g>")
    if labels_only and config.show_edge_labels:
        parts.append(_edge_label("AND", label_at[0], label_at[1], config, theme))
    return "\n".join(parts)


def _regular_edge(
    edge: Edge,
    layout: GraphLayout,
    config: RenderConfig,
    theme: Theme,
    *,
    labels_only: bool,
) -> str:
    if edge.source not in layout.nodes or edge.target not in layout.nodes:
        return ""
    source = layout.nodes[edge.source]
    target = layout.nodes[edge.target]
    color, marker, dash, width = _edge_style(edge, theme)
    if config.direction == "horizontal":
        start = _right(source)
        end = _left(target)
        mid_x = (start[0] + end[0]) / 2
        if target.rank <= source.rank:
            mid_x = max(source.x, target.x) + source.width / 2 + config.node_gap
        points = [start, (mid_x, start[1]), (mid_x, end[1]), end]
    else:
        start = _bottom(source)
        end = _top(target)
        mid_y = (start[1] + end[1]) / 2
        if target.rank <= source.rank:
            mid_y = max(source.y, target.y) + source.height / 2 + config.node_gap
        points = [start, (start[0], mid_y), (end[0], mid_y), end]
    label_at = _router_label_position(edge, target, points, config) if edge.kind == "router" else _midpoint(points)
    path = _path(points)
    parts = []
    if not labels_only:
        parts.append(
            f'<path d="{path}" stroke="{color}" stroke-width="{width}" stroke-linecap="round" '
            f'stroke-linejoin="round" marker-end="url(#{marker})"{dash}/>'
        )
    if labels_only and config.show_edge_labels and edge.label:
        parts.append(_edge_label(edge.label, label_at[0], label_at[1], config, theme))
    return "\n".join(parts)


def _back_edge(
    edge: Edge,
    layout: GraphLayout,
    config: RenderConfig,
    theme: Theme,
    lane: int,
    *,
    labels_only: bool,
) -> str:
    if edge.source not in layout.nodes or edge.target not in layout.nodes:
        return ""
    source = layout.nodes[edge.source]
    target = layout.nodes[edge.target]
    offset = 48 + lane * 24
    if config.direction == "horizontal":
        max_bottom = max(source.y + source.height / 2, target.y + target.height / 2)
        side_y = layout.height - config.margin * 0.55 - lane * 22
        side_y = max(side_y, max_bottom + 28)
        start = _bottom(source)
        end = _bottom(target)
        points = [start, (start[0], side_y), (end[0], side_y), end]
        label_at = (target.x, target.y + target.height / 2 + 28)
    else:
        max_right = max(source.x + source.width / 2, target.x + target.width / 2)
        side_x = layout.width - config.margin * 0.55 - lane * 22
        side_x = max(side_x, max_right + 28)
        start = _right(source)
        end = _right(target)
        points = [start, (side_x, start[1]), (side_x, end[1]), end]
        label_w, label_h = _edge_label_size(edge.label, config)
        label_at = (
            layout.width - config.margin * 0.65 - label_w / 2,
            target.y - target.height / 2 - 14 - lane * (label_h + 5),
        )
    parts = []
    if not labels_only:
        parts.append(
            f'<path d="{_path(points)}" stroke="{theme.edge_back}" stroke-width="2.4" '
            'stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="8 8" '
            'marker-end="url(#arrow-back)"/>'
        )
    if labels_only and config.show_edge_labels and edge.label:
        parts.append(_edge_label(edge.label, label_at[0], label_at[1], config, theme))
    return "\n".join(parts)


def _edge_style(edge: Edge, theme: Theme) -> tuple[str, str, str, str]:
    if edge.kind == "router":
        return theme.edge_router, "arrow-router", ' stroke-dasharray="10 7"', "2.6"
    if edge.kind == "and":
        return theme.edge_and, "arrow-and", "", "2.4"
    return theme.edge, "arrow-edge", "", "2.2"


def _router_label_position(
    edge: Edge,
    target: LayoutNode,
    points: list[tuple[float, float]],
    config: RenderConfig,
) -> tuple[float, float]:
    end = points[-1]
    prev = points[-2] if len(points) > 1 else points[0]
    label_w, label_h = _edge_label_size(edge.label, config)
    gap = max(26, config.edge_font_size * 1.4)
    if config.direction == "horizontal":
        x = end[0] - label_w / 2 - gap if prev[0] < end[0] else end[0] + label_w / 2 + gap
        return x, target.y - target.height / 2 - 10
    y = end[1] - label_h / 2 - gap if prev[1] < end[1] else end[1] + label_h / 2 + gap
    return target.x, y


def _node_shadows(graph: FlowGraph, layout: GraphLayout, config: RenderConfig, theme: Theme) -> str:
    parts = ['<g>']
    for node in graph.nodes:
        item = layout.nodes.get(node.id)
        if not item:
            continue
        x = item.x - item.width / 2 + 4
        y = item.y - item.height / 2 + 5
        parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{item.width:.1f}" height="{item.height:.1f}" '
            f'rx="{config.corner_radius}" fill="{theme.shadow}"/>'
        )
    parts.append("</g>")
    return "\n".join(parts)


def _nodes(graph: FlowGraph, layout: GraphLayout, config: RenderConfig, theme: Theme) -> str:
    node_by_id = graph.node_map()
    parts = ['<g font-family="' + escape(config.font_family) + '">']
    for node_id, item in layout.nodes.items():
        node = node_by_id[node_id]
        fill, border, text = _node_colors(node.kind, theme)
        x = item.x - item.width / 2
        y = item.y - item.height / 2
        parts.append(f'<g id="node-{escape(node.id)}">')
        if node.source_file:
            ref = f"{node.source_file}:{node.source_line}" if node.source_line else node.source_file
            parts.append(f"<title>{escape(node.id)} — {escape(ref)}</title>")
        parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{item.width:.1f}" height="{item.height:.1f}" '
            f'rx="{config.corner_radius}" fill="{fill}" stroke="{border}" stroke-width="2.6"/>'
        )
        if config.show_kinds:
            parts.append(_badge(node.kind.replace("_", " "), x + 14, y + 13, config, theme, start=node.kind == "start"))
        line_height = config.font_size + 5
        label_total = len(item.label_lines) * line_height
        text_y = item.y - label_total / 2 + config.font_size * 0.75 + (8 if config.show_kinds else 0)
        for line in item.label_lines:
            parts.append(
                f'<text x="{item.x:.1f}" y="{text_y:.1f}" text-anchor="middle" '
                f'font-size="{config.font_size}" font-weight="750" fill="{text}">{escape(line)}</text>'
            )
            text_y += line_height
        if item.source_ref:
            parts.append(
                f'<text x="{item.x:.1f}" y="{y + item.height - 14:.1f}" text-anchor="middle" '
                f'font-family="{escape(config.mono_family)}" font-size="{config.small_font_size}" fill="{theme.muted_text}">'
                f'{escape(item.source_ref)}</text>'
            )
        parts.append("</g>")
    parts.append("</g>")
    return "\n".join(parts)


def _node_colors(kind: str, theme: Theme) -> tuple[str, str, str]:
    if kind == "start":
        return theme.start_fill, theme.start_border, theme.start_text
    if kind in {"router", "start_router"}:
        return theme.router_fill, theme.router_border, theme.text
    return theme.node_fill, theme.node_border, theme.text


def _badge(kind: str, x: float, y: float, config: RenderConfig, theme: Theme, *, start: bool) -> str:
    label = kind.upper()
    width = max(42, len(label) * config.small_font_size * 0.62 + 14)
    height = config.small_font_size + 8
    fill = "rgba(255,255,255,0.88)" if start else theme.badge_fill
    text = theme.start_border if start else theme.badge_text
    return (
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" height="{height:.1f}" rx="5" fill="{fill}"/>'
        f'<text x="{x + width / 2:.1f}" y="{y + height - 7:.1f}" text-anchor="middle" '
        f'font-size="{config.small_font_size}" font-weight="750" fill="{text}">{escape(label)}</text>'
    )


def _edge_label(label: str, x: float, y: float, config: RenderConfig, theme: Theme) -> str:
    width, height = _edge_label_size(label, config)
    return (
        f'<g><rect x="{x - width / 2:.1f}" y="{y - height / 2:.1f}" width="{width:.1f}" height="{height:.1f}" '
        f'rx="6" fill="{theme.label_fill}" stroke="{theme.label_border}" stroke-width="1"/>'
        f'<text x="{x:.1f}" y="{y + config.edge_font_size / 2 - 2:.1f}" text-anchor="middle" '
        f'font-family="{escape(config.mono_family)}" font-size="{config.edge_font_size}" '
        f'font-weight="650" fill="{theme.text}">'
        f'{escape(label)}</text></g>'
    )


def _edge_label_size(label: str, config: RenderConfig) -> tuple[float, float]:
    return max(30, len(label) * config.edge_font_size * 0.58 + 18), config.edge_font_size + 12


def _path(points: list[tuple[float, float]]) -> str:
    first, *rest = points
    parts = [f"M {first[0]:.1f} {first[1]:.1f}"]
    parts.extend(f"L {x:.1f} {y:.1f}" for x, y in rest)
    return " ".join(parts)


def _midpoint(points: list[tuple[float, float]]) -> tuple[float, float]:
    if not points:
        return 0, 0
    middle = len(points) // 2
    if len(points) % 2 == 1:
        return points[middle]
    a = points[middle - 1]
    b = points[middle]
    return (a[0] + b[0]) / 2, (a[1] + b[1]) / 2


def _top(node: LayoutNode) -> tuple[float, float]:
    return node.x, node.y - node.height / 2


def _bottom(node: LayoutNode) -> tuple[float, float]:
    return node.x, node.y + node.height / 2


def _left(node: LayoutNode) -> tuple[float, float]:
    return node.x - node.width / 2, node.y


def _right(node: LayoutNode) -> tuple[float, float]:
    return node.x + node.width / 2, node.y
