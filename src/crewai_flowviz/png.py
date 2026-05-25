"""Native Pillow PNG renderer for FlowGraph objects."""

from __future__ import annotations

from collections import defaultdict
from io import BytesIO
import math
from pathlib import Path

from PIL import Image, ImageColor, ImageDraw, ImageFont

from crewai_flowviz.layout import GraphLayout, LayoutNode, layout_graph
from crewai_flowviz.models import Edge, FlowGraph, RenderConfig, Theme


def render_png_bytes(graph: FlowGraph, config: RenderConfig, theme: Theme) -> bytes:
    layout = layout_graph(graph, config)
    natural_w = max(1, math.ceil(layout.width))
    natural_h = max(1, math.ceil(layout.height))
    image = Image.new("RGBA", (natural_w, natural_h), _background(theme, config))
    draw = ImageDraw.Draw(image)
    fonts = _fonts(config)

    if config.show_grid:
        _draw_grid(draw, natural_w, natural_h, theme)
    if config.title:
        draw.text(
            (config.margin, 14),
            config.title,
            font=fonts["title"],
            fill=_color(theme.text),
        )

    _draw_edges(draw, graph, layout, config, theme, fonts, labels_only=False)
    _draw_nodes(draw, graph, layout, config, theme, fonts)
    _draw_edges(draw, graph, layout, config, theme, fonts, labels_only=True)

    final = _fit_image(image, config, theme)
    out = BytesIO()
    final.save(out, format="PNG")
    return out.getvalue()


def _background(theme: Theme, config: RenderConfig) -> tuple[int, int, int, int]:
    if config.export_background:
        return _color(theme.background)
    return (0, 0, 0, 0)


def _fit_image(image: Image.Image, config: RenderConfig, theme: Theme) -> Image.Image:
    natural_w, natural_h = image.size
    if config.width and config.height:
        out_w, out_h = config.width, config.height
        scale = min(out_w / natural_w, out_h / natural_h) if config.fit else 1
    elif config.width:
        out_w = config.width
        scale = out_w / natural_w
        out_h = max(1, round(natural_h * scale))
    elif config.height:
        out_h = config.height
        scale = out_h / natural_h
        out_w = max(1, round(natural_w * scale))
    else:
        return image

    resized = image.resize((max(1, round(natural_w * scale)), max(1, round(natural_h * scale))), Image.Resampling.LANCZOS)
    final = Image.new("RGBA", (out_w, out_h), _background(theme, config))
    final.alpha_composite(resized, ((out_w - resized.width) // 2, (out_h - resized.height) // 2))
    return final


def _fonts(config: RenderConfig) -> dict[str, ImageFont.ImageFont]:
    def load(size: int, *, bold: bool = False) -> ImageFont.ImageFont:
        candidates = [
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/Library/Fonts/Arial Bold.ttf" if bold else "/Library/Fonts/Arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
        for path in candidates:
            if path and Path(path).exists():
                try:
                    return ImageFont.truetype(path, size)
                except OSError:
                    continue
        return ImageFont.load_default()

    return {
        "title": load(22, bold=True),
        "label": load(config.font_size, bold=True),
        "small": load(config.small_font_size, bold=True),
        "source": load(config.small_font_size),
        "edge": load(config.edge_font_size),
    }


def _draw_grid(draw: ImageDraw.ImageDraw, width: int, height: int, theme: Theme) -> None:
    step = 24
    color = _color(theme.grid)
    for x in range(0, width + step, step):
        draw.line([(x, 0), (x, height)], fill=color, width=1)
    for y in range(0, height + step, step):
        draw.line([(0, y), (width, y)], fill=color, width=1)


def _draw_edges(
    draw: ImageDraw.ImageDraw,
    graph: FlowGraph,
    layout: GraphLayout,
    config: RenderConfig,
    theme: Theme,
    fonts: dict[str, ImageFont.ImageFont],
    *,
    labels_only: bool,
) -> None:
    and_groups: dict[str, list[Edge]] = defaultdict(list)
    grouped_and_ids: set[tuple[str, str, str]] = set()
    for edge in graph.edges:
        if edge.kind == "and" and not edge.back:
            and_groups[edge.target].append(edge)

    for target, edges in and_groups.items():
        if len(edges) <= 1:
            continue
        _draw_and_group(draw, target, edges, layout, config, theme, fonts, labels_only=labels_only)
        for edge in edges:
            grouped_and_ids.add((edge.source, edge.target, edge.label))

    back_lane = 0
    for edge in graph.edges:
        if (edge.source, edge.target, edge.label) in grouped_and_ids:
            continue
        if edge.back:
            _draw_back_edge(draw, edge, layout, config, theme, fonts, back_lane, labels_only=labels_only)
            back_lane += 1
        else:
            _draw_regular_edge(draw, edge, layout, config, theme, fonts, labels_only=labels_only)


def _draw_and_group(
    draw: ImageDraw.ImageDraw,
    target: str,
    edges: list[Edge],
    layout: GraphLayout,
    config: RenderConfig,
    theme: Theme,
    fonts: dict[str, ImageFont.ImageFont],
    *,
    labels_only: bool,
) -> None:
    if target not in layout.nodes:
        return
    target_node = layout.nodes[target]
    source_nodes = [layout.nodes[edge.source] for edge in edges if edge.source in layout.nodes]
    if not source_nodes:
        return

    color = _color(theme.edge_and)
    if config.direction == "horizontal":
        join_x = target_node.x - target_node.width / 2 - config.rank_gap * 0.34
        label_at = (join_x, target_node.y)
        if not labels_only:
            for source in source_nodes:
                start = _right(source)
                _draw_polyline(draw, [start, (join_x, start[1]), (join_x, target_node.y)], color, 2)
            _draw_arrow_line(draw, [(join_x, target_node.y), _left(target_node)], color, 2)
    else:
        join_y = target_node.y - target_node.height / 2 - config.rank_gap * 0.34
        label_at = (target_node.x, join_y)
        if not labels_only:
            for source in source_nodes:
                start = _bottom(source)
                _draw_polyline(draw, [start, (start[0], join_y), (target_node.x, join_y)], color, 2)
            _draw_arrow_line(draw, [(target_node.x, join_y), _top(target_node)], color, 2)

    if labels_only and config.show_edge_labels:
        _draw_edge_label(draw, "AND", label_at, config, theme, fonts)


def _draw_regular_edge(
    draw: ImageDraw.ImageDraw,
    edge: Edge,
    layout: GraphLayout,
    config: RenderConfig,
    theme: Theme,
    fonts: dict[str, ImageFont.ImageFont],
    *,
    labels_only: bool,
) -> None:
    if edge.source not in layout.nodes or edge.target not in layout.nodes:
        return
    source = layout.nodes[edge.source]
    target = layout.nodes[edge.target]
    color = _edge_color(edge, theme)
    dashed = edge.kind == "router"
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

    if not labels_only:
        _draw_arrow_line(draw, points, color, 2, dashed=dashed)
    elif config.show_edge_labels and edge.label:
        label_at = _router_label_position(edge, target, points, config) if edge.kind == "router" else _midpoint(points)
        _draw_edge_label(draw, edge.label, label_at, config, theme, fonts)


def _draw_back_edge(
    draw: ImageDraw.ImageDraw,
    edge: Edge,
    layout: GraphLayout,
    config: RenderConfig,
    theme: Theme,
    fonts: dict[str, ImageFont.ImageFont],
    lane: int,
    *,
    labels_only: bool,
) -> None:
    if edge.source not in layout.nodes or edge.target not in layout.nodes:
        return
    source = layout.nodes[edge.source]
    target = layout.nodes[edge.target]
    color = _color(theme.edge_back)
    if config.direction == "horizontal":
        max_bottom = max(source.y + source.height / 2, target.y + target.height / 2)
        side_y = max(layout.height - config.margin * 0.55 - lane * 22, max_bottom + 28)
        points = [_bottom(source), (source.x, side_y), (target.x, side_y), _bottom(target)]
        label_at = (target.x, target.y + target.height / 2 + 28)
    else:
        max_right = max(source.x + source.width / 2, target.x + target.width / 2)
        side_x = max(layout.width - config.margin * 0.55 - lane * 22, max_right + 28)
        points = [_right(source), (side_x, source.y), (side_x, target.y), _right(target)]
        label_at = (target.x + target.width / 2 + 48, target.y - 8)

    if not labels_only:
        _draw_arrow_line(draw, points, color, 2, dashed=True)
    elif config.show_edge_labels and edge.label:
        _draw_edge_label(draw, edge.label, label_at, config, theme, fonts)


def _draw_nodes(
    draw: ImageDraw.ImageDraw,
    graph: FlowGraph,
    layout: GraphLayout,
    config: RenderConfig,
    theme: Theme,
    fonts: dict[str, ImageFont.ImageFont],
) -> None:
    node_by_id = graph.node_map()
    for node_id, item in layout.nodes.items():
        node = node_by_id[node_id]
        fill, border, text = _node_colors(node.kind, theme)
        x0 = item.x - item.width / 2
        y0 = item.y - item.height / 2
        rect = [x0, y0, x0 + item.width, y0 + item.height]
        shadow = [rect[0] + 4, rect[1] + 5, rect[2] + 4, rect[3] + 5]
        draw.rounded_rectangle(shadow, radius=config.corner_radius, fill=_color(theme.shadow))
        draw.rounded_rectangle(rect, radius=config.corner_radius, fill=_color(fill), outline=_color(border), width=3)

        if config.show_kinds:
            _draw_badge(draw, node.kind.replace("_", " "), x0 + 14, y0 + 13, config, theme, fonts, start=node.kind == "start")

        line_height = config.font_size + 5
        label_total = len(item.label_lines) * line_height
        text_y = item.y - label_total / 2 - 2 + (8 if config.show_kinds else 0)
        for line in item.label_lines:
            _center_text(draw, line, (item.x, text_y), fonts["label"], _color(text))
            text_y += line_height
        if item.source_ref:
            _center_text(draw, item.source_ref, (item.x, y0 + item.height - 21), fonts["source"], _color(theme.muted_text))


def _draw_polyline(
    draw: ImageDraw.ImageDraw,
    points: list[tuple[float, float]],
    color: tuple[int, int, int, int],
    width: int,
    *,
    dashed: bool = False,
) -> None:
    for start, end in zip(points, points[1:]):
        if dashed:
            _draw_dashed_segment(draw, start, end, color, width)
        else:
            draw.line([start, end], fill=color, width=width)


def _draw_arrow_line(
    draw: ImageDraw.ImageDraw,
    points: list[tuple[float, float]],
    color: tuple[int, int, int, int],
    width: int,
    *,
    dashed: bool = False,
) -> None:
    _draw_polyline(draw, points, color, width, dashed=dashed)
    if len(points) >= 2:
        _draw_arrowhead(draw, points[-2], points[-1], color)


def _draw_dashed_segment(
    draw: ImageDraw.ImageDraw,
    start: tuple[float, float],
    end: tuple[float, float],
    color: tuple[int, int, int, int],
    width: int,
) -> None:
    x1, y1 = start
    x2, y2 = end
    length = math.hypot(x2 - x1, y2 - y1)
    if length == 0:
        return
    dash, gap = 10, 7
    distance = 0.0
    while distance < length:
        segment_end = min(distance + dash, length)
        p1 = (x1 + (x2 - x1) * distance / length, y1 + (y2 - y1) * distance / length)
        p2 = (x1 + (x2 - x1) * segment_end / length, y1 + (y2 - y1) * segment_end / length)
        draw.line([p1, p2], fill=color, width=width)
        distance += dash + gap


def _draw_arrowhead(
    draw: ImageDraw.ImageDraw,
    start: tuple[float, float],
    end: tuple[float, float],
    color: tuple[int, int, int, int],
) -> None:
    angle = math.atan2(end[1] - start[1], end[0] - start[0])
    size = 11
    spread = math.radians(28)
    p1 = (
        end[0] - size * math.cos(angle - spread),
        end[1] - size * math.sin(angle - spread),
    )
    p2 = (
        end[0] - size * math.cos(angle + spread),
        end[1] - size * math.sin(angle + spread),
    )
    draw.polygon([end, p1, p2], fill=color)


def _draw_edge_label(
    draw: ImageDraw.ImageDraw,
    label: str,
    center: tuple[float, float],
    config: RenderConfig,
    theme: Theme,
    fonts: dict[str, ImageFont.ImageFont],
) -> None:
    font = fonts["edge"]
    bbox = draw.textbbox((0, 0), label, font=font)
    width = max(30, bbox[2] - bbox[0] + 16)
    height = config.edge_font_size + 10
    rect = [
        center[0] - width / 2,
        center[1] - height / 2,
        center[0] + width / 2,
        center[1] + height / 2,
    ]
    draw.rounded_rectangle(rect, radius=6, fill=_color(theme.label_fill), outline=_color(theme.label_border), width=1)
    _center_text(draw, label, (center[0], center[1] - config.edge_font_size / 2 + 2), font, _color(theme.text))


def _draw_badge(
    draw: ImageDraw.ImageDraw,
    kind: str,
    x: float,
    y: float,
    config: RenderConfig,
    theme: Theme,
    fonts: dict[str, ImageFont.ImageFont],
    *,
    start: bool,
) -> None:
    label = kind.upper()
    font = fonts["small"]
    bbox = draw.textbbox((0, 0), label, font=font)
    width = max(42, bbox[2] - bbox[0] + 14)
    height = config.small_font_size + 8
    fill = (255, 255, 255, 62) if start else _color(theme.badge_fill)
    text = _color(theme.start_text if start else theme.badge_text)
    draw.rounded_rectangle([x, y, x + width, y + height], radius=5, fill=fill)
    _center_text(draw, label, (x + width / 2, y + height / 2 - config.small_font_size / 2 + 2), font, text)


def _center_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    point: tuple[float, float],
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int, int],
) -> None:
    bbox = draw.textbbox((0, 0), text, font=font)
    width = bbox[2] - bbox[0]
    draw.text((point[0] - width / 2, point[1]), text, font=font, fill=fill)


def _edge_color(edge: Edge, theme: Theme) -> tuple[int, int, int, int]:
    if edge.kind == "router":
        return _color(theme.edge_router)
    if edge.kind == "and":
        return _color(theme.edge_and)
    return _color(theme.edge)


def _node_colors(kind: str, theme: Theme) -> tuple[str, str, str]:
    if kind == "start":
        return theme.start_fill, theme.start_border, theme.start_text
    if kind in {"router", "start_router"}:
        return theme.router_fill, theme.router_border, theme.text
    return theme.node_fill, theme.node_border, theme.text


def _router_label_position(
    edge: Edge,
    target: LayoutNode,
    points: list[tuple[float, float]],
    config: RenderConfig,
) -> tuple[float, float]:
    end = points[-1]
    prev = points[-2] if len(points) > 1 else points[0]
    if config.direction == "horizontal":
        x = end[0] - 34 if prev[0] < end[0] else end[0] + 34
        return x, target.y - target.height / 2 - 10
    y = end[1] - 22 if prev[1] < end[1] else end[1] + 22
    return target.x, y


def _path_point(node: LayoutNode, side: str) -> tuple[float, float]:
    if side == "top":
        return node.x, node.y - node.height / 2
    if side == "bottom":
        return node.x, node.y + node.height / 2
    if side == "left":
        return node.x - node.width / 2, node.y
    return node.x + node.width / 2, node.y


def _top(node: LayoutNode) -> tuple[float, float]:
    return _path_point(node, "top")


def _bottom(node: LayoutNode) -> tuple[float, float]:
    return _path_point(node, "bottom")


def _left(node: LayoutNode) -> tuple[float, float]:
    return _path_point(node, "left")


def _right(node: LayoutNode) -> tuple[float, float]:
    return _path_point(node, "right")


def _midpoint(points: list[tuple[float, float]]) -> tuple[float, float]:
    if not points:
        return 0, 0
    middle = len(points) // 2
    if len(points) % 2 == 1:
        return points[middle]
    a = points[middle - 1]
    b = points[middle]
    return (a[0] + b[0]) / 2, (a[1] + b[1]) / 2


def _color(value: str) -> tuple[int, int, int, int]:
    return ImageColor.getcolor(value, "RGBA")
