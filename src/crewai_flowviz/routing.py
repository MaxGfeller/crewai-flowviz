"""Shared orthogonal edge routing helpers."""

from __future__ import annotations

from crewai_flowviz.layout import GraphLayout, LayoutNode
from crewai_flowviz.models import RenderConfig

Point = tuple[float, float]
Rect = tuple[float, float, float, float]
BackEdgeSide = str


def regular_edge_points(
    source: LayoutNode,
    target: LayoutNode,
    layout: GraphLayout,
    config: RenderConfig,
    *,
    avoid_collisions: bool = True,
) -> list[Point]:
    if config.direction == "horizontal":
        start = _right(source)
        end = _left(target)
        mid_x = (start[0] + end[0]) / 2
        if target.rank <= source.rank:
            mid_x = max(source.x, target.x) + source.width / 2 + config.node_gap
        return [start, (mid_x, start[1]), (mid_x, end[1]), end]

    start = _bottom(source)
    end = _top(target)
    mid_y = (start[1] + end[1]) / 2
    if target.rank <= source.rank:
        mid_y = max(source.y, target.y) + source.height / 2 + config.node_gap
    points = [start, (start[0], mid_y), (end[0], mid_y), end]
    if target.rank <= source.rank or not avoid_collisions:
        return points

    blockers = [node for node in layout.nodes.values() if node.id not in {source.id, target.id}]
    hit_nodes = _hit_nodes(points, blockers)
    if not hit_nodes:
        return points

    detour = _vertical_detour(source, target, hit_nodes, config, prefer_left=target.x < source.x)
    if not _hit_nodes(detour, blockers):
        return detour

    alternate = _vertical_detour(source, target, hit_nodes, config, prefer_left=target.x >= source.x)
    if not _hit_nodes(alternate, blockers):
        return alternate

    return detour


def back_edge_side(source: LayoutNode, target: LayoutNode, config: RenderConfig, *, lane: int = 0) -> BackEdgeSide:
    if config.direction == "horizontal":
        return "bottom"
    if target.x < source.x - 1:
        return "left"
    if target.x > source.x + 1:
        return "right"
    return "right" if lane % 2 == 0 else "left"


def back_edge_route(
    source: LayoutNode,
    target: LayoutNode,
    layout: GraphLayout,
    config: RenderConfig,
    *,
    lane: int,
    label_size: tuple[float, float],
    side: BackEdgeSide | None = None,
) -> tuple[list[Point], Point]:
    side = side or back_edge_side(source, target, config, lane=lane)
    if config.direction == "horizontal":
        points = _horizontal_back_edge_points(source, target, layout, config, lane)
        return points, _horizontal_back_label(target, layout, config, lane, label_size)
    points = _vertical_back_edge_points(source, target, layout, config, lane, side)
    return points, _vertical_back_label(points[-1], side, target, layout, config, label_size)


def _vertical_back_edge_points(
    source: LayoutNode,
    target: LayoutNode,
    layout: GraphLayout,
    config: RenderConfig,
    lane: int,
    side: BackEdgeSide,
) -> list[Point]:
    lane_gap = max(28.0, config.node_gap * 0.65)
    lane_step = max(24.0, config.edge_font_size + 10.0)
    y_offset = _fanout_offset(lane, source.height)
    if side == "left":
        outer = min(source.x - source.width / 2, target.x - target.width / 2)
        side_x = max(8.0, outer - lane_gap - lane * lane_step)
        start = (source.x - source.width / 2, source.y + y_offset)
        end = _left(target)
    else:
        outer = max(source.x + source.width / 2, target.x + target.width / 2)
        side_x = min(layout.width - 8.0, outer + lane_gap + lane * lane_step)
        start = (source.x + source.width / 2, source.y + y_offset)
        end = _right(target)
    return [start, (side_x, start[1]), (side_x, end[1]), end]


def _vertical_back_label(
    end: Point,
    side: BackEdgeSide,
    target: LayoutNode,
    layout: GraphLayout,
    config: RenderConfig,
    label_size: tuple[float, float],
) -> Point:
    label_w, label_h = label_size
    gap = max(8.0, config.edge_font_size * 0.65)
    if side == "left":
        x = end[0] - label_w / 2 - gap
        x = max(label_w / 2 + 4, x)
    else:
        x = end[0] + label_w / 2 + gap
        x = min(layout.width - label_w / 2 - 4, x)
    below_target = (x, target.y + target.height / 2 + label_h / 2 + gap)
    above_target = (x, target.y - target.height / 2 - label_h / 2 - gap)
    candidates = [
        below_target,
        (x, end[1]),
        above_target,
    ]
    for center in candidates:
        if not _label_hits_nodes(center, label_size, layout, ignored_id=target.id):
            return _clamp_label(center, label_size, layout)
    return _clamp_label(candidates[0], label_size, layout)


def _horizontal_back_edge_points(
    source: LayoutNode,
    target: LayoutNode,
    layout: GraphLayout,
    config: RenderConfig,
    lane: int,
) -> list[Point]:
    max_bottom = max(source.y + source.height / 2, target.y + target.height / 2)
    side_y = layout.height - config.margin * 0.55 - lane * max(22.0, config.edge_font_size + 8.0)
    side_y = max(side_y, max_bottom + 28)
    x_offset = _fanout_offset(lane, source.width)
    start = (source.x + x_offset, source.y + source.height / 2)
    end = _bottom(target)
    return [start, (start[0], side_y), (end[0], side_y), end]


def _horizontal_back_label(
    target: LayoutNode,
    layout: GraphLayout,
    config: RenderConfig,
    lane: int,
    label_size: tuple[float, float],
) -> Point:
    _label_w, label_h = label_size
    gap = max(8.0, config.edge_font_size * 0.65)
    y = target.y + target.height / 2 + label_h / 2 + gap + lane * 3
    return target.x, min(layout.height - label_h / 2 - 4, y)


def _fanout_offset(lane: int, span: float) -> float:
    if lane == 0:
        return 0.0
    direction = -1 if lane % 2 else 1
    step = (lane + 1) // 2
    return direction * min(span * 0.34, step * span * 0.18)


def _label_hits_nodes(
    center: Point,
    label_size: tuple[float, float],
    layout: GraphLayout,
    *,
    ignored_id: str,
) -> bool:
    rect = _label_rect(center, label_size)
    return any(node.id != ignored_id and _rects_overlap(rect, _rect(node, padding=4)) for node in layout.nodes.values())


def _label_rect(center: Point, size: tuple[float, float]) -> Rect:
    width, height = size
    return (
        center[0] - width / 2,
        center[1] - height / 2,
        center[0] + width / 2,
        center[1] + height / 2,
    )


def _rects_overlap(first: Rect, second: Rect) -> bool:
    return first[0] < second[2] and first[2] > second[0] and first[1] < second[3] and first[3] > second[1]


def _clamp_label(center: Point, label_size: tuple[float, float], layout: GraphLayout) -> Point:
    label_w, label_h = label_size
    x = min(max(center[0], label_w / 2 + 4), layout.width - label_w / 2 - 4)
    y = min(max(center[1], label_h / 2 + 4), layout.height - label_h / 2 - 4)
    return x, y


def _vertical_detour(
    source: LayoutNode,
    target: LayoutNode,
    hit_nodes: list[LayoutNode],
    config: RenderConfig,
    *,
    prefer_left: bool,
) -> list[Point]:
    start = _bottom(source)
    end = _top(target)
    available = max(1.0, end[1] - start[1])
    elbow = min(max(28.0, config.edge_font_size * 2.2), available / 3)
    upper_y = start[1] + elbow
    lower_y = end[1] - elbow
    if lower_y < upper_y:
        middle = (start[1] + end[1]) / 2
        upper_y = lower_y = middle

    lane_gap = max(28.0, config.node_gap * 0.6)
    if prefer_left:
        side_x = min(node.x - node.width / 2 for node in hit_nodes) - lane_gap
    else:
        side_x = max(node.x + node.width / 2 for node in hit_nodes) + lane_gap

    return [start, (start[0], upper_y), (side_x, upper_y), (side_x, lower_y), (end[0], lower_y), end]


def _hit_nodes(points: list[Point], nodes: list[LayoutNode]) -> list[LayoutNode]:
    hits: list[LayoutNode] = []
    for node in nodes:
        rect = _rect(node, padding=6)
        if any(_segment_hits_rect(start, end, rect) for start, end in zip(points, points[1:])):
            hits.append(node)
    return hits


def _segment_hits_rect(start: Point, end: Point, rect: Rect) -> bool:
    left, top, right, bottom = rect
    if start[0] == end[0]:
        x = start[0]
        y1, y2 = sorted((start[1], end[1]))
        return left <= x <= right and max(y1, top) <= min(y2, bottom)
    if start[1] == end[1]:
        y = start[1]
        x1, x2 = sorted((start[0], end[0]))
        return top <= y <= bottom and max(x1, left) <= min(x2, right)
    return False


def _rect(node: LayoutNode, *, padding: float = 0) -> Rect:
    return (
        node.x - node.width / 2 - padding,
        node.y - node.height / 2 - padding,
        node.x + node.width / 2 + padding,
        node.y + node.height / 2 + padding,
    )


def _top(node: LayoutNode) -> Point:
    return node.x, node.y - node.height / 2


def _bottom(node: LayoutNode) -> Point:
    return node.x, node.y + node.height / 2


def _left(node: LayoutNode) -> Point:
    return node.x - node.width / 2, node.y


def _right(node: LayoutNode) -> Point:
    return node.x + node.width / 2, node.y
