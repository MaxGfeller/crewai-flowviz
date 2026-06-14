"""Deterministic layered layout for CrewAI Flow graphs."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from statistics import mean

from crewai_flowviz.models import FlowGraph, RenderConfig


@dataclass(frozen=True)
class LayoutNode:
    id: str
    rank: int
    x: float
    y: float
    width: float
    height: float
    label_lines: list[str]
    source_ref: str | None = None


@dataclass(frozen=True)
class GraphLayout:
    nodes: dict[str, LayoutNode]
    ranks: dict[int, list[str]]
    width: float
    height: float
    title_height: float = 0


def layout_graph(graph: FlowGraph, config: RenderConfig) -> GraphLayout:
    ranks = _assign_ranks(graph)
    rank_groups = _order_within_ranks(graph, ranks)
    measured = _measure_nodes(graph, config)
    back_edge_count = sum(1 for edge in graph.edges if edge.back)

    if config.direction == "horizontal":
        return _place_horizontal(rank_groups, measured, config, back_edge_count)
    return _place_vertical(graph, rank_groups, measured, config, back_edge_count)


def _assign_ranks(graph: FlowGraph) -> dict[str, int]:
    node_ids = [node.id for node in graph.nodes]
    starts = [node_id for node_id in graph.start_nodes if node_id in node_ids]
    if not starts and node_ids:
        starts = [node_ids[0]]

    outgoing: dict[str, list[str]] = defaultdict(list)
    for edge in graph.edges:
        if edge.back:
            continue
        outgoing[edge.source].append(edge.target)

    ranks: dict[str, int] = {start: 0 for start in starts}
    queue = list(starts)
    guard = max(1, len(node_ids) * len(node_ids) * 2)
    steps = 0
    while queue and steps < guard:
        steps += 1
        source = queue.pop(0)
        source_rank = ranks[source]
        for target in outgoing.get(source, []):
            next_rank = source_rank + 1
            if ranks.get(target, -1) < next_rank:
                ranks[target] = next_rank
                queue.append(target)

    fallback_rank = max(ranks.values(), default=-1) + 1
    for node_id in node_ids:
        if node_id not in ranks:
            ranks[node_id] = fallback_rank
            fallback_rank += 1
    return ranks


def _order_within_ranks(graph: FlowGraph, ranks: dict[str, int]) -> dict[int, list[str]]:
    original = {node.id: index for index, node in enumerate(graph.nodes)}
    groups: dict[int, list[str]] = defaultdict(list)
    for node in graph.nodes:
        groups[ranks[node.id]].append(node.id)
    for rank in groups:
        groups[rank].sort(key=lambda node_id: original[node_id])

    incoming: dict[str, list[str]] = defaultdict(list)
    outgoing: dict[str, list[str]] = defaultdict(list)
    for edge in graph.edges:
        if edge.back:
            continue
        incoming[edge.target].append(edge.source)
        outgoing[edge.source].append(edge.target)

    for _ in range(4):
        for rank in sorted(groups):
            if rank == min(groups):
                continue
            prior_order = _rank_order(groups)
            groups[rank].sort(
                key=lambda node_id: (
                    _avg_order_key(incoming[node_id], prior_order, original[node_id]),
                    original[node_id],
                )
            )
        for rank in sorted(groups, reverse=True):
            if rank == max(groups):
                continue
            next_order = _rank_order(groups)
            groups[rank].sort(
                key=lambda node_id: (
                    _avg_order_key(outgoing[node_id], next_order, original[node_id]),
                    original[node_id],
                )
            )

    return dict(sorted(groups.items()))


def _rank_order(groups: dict[int, list[str]]) -> dict[str, int]:
    order: dict[str, int] = {}
    for nodes in groups.values():
        for index, node_id in enumerate(nodes):
            order[node_id] = index
    return order


def _avg_order_key(
    node_ids: list[str],
    order: dict[str, int],
    fallback: int,
) -> tuple[int, float]:
    values = [order[node_id] for node_id in node_ids if node_id in order]
    if not values:
        return 1, float(fallback)
    return 0, mean(values)


def _measure_nodes(
    graph: FlowGraph,
    config: RenderConfig,
) -> dict[str, tuple[float, float, list[str], str | None]]:
    result: dict[str, tuple[float, float, list[str], str | None]] = {}
    max_chars = max(8, int((config.node_width - 40) / (config.font_size * 0.58)))
    for node in graph.nodes:
        lines = _wrap_label(node.label, max_chars)
        line_height = config.font_size + 5
        height = 24 + len(lines) * line_height + 26
        if config.show_kinds:
            height += 8
        source_ref = None
        if config.show_source_refs and node.source_file:
            file_name = node.source_file.rsplit("/", 1)[-1]
            source_ref = f"{file_name}:{node.source_line}" if node.source_line else file_name
            height += config.small_font_size + 10
        result[node.id] = (
            float(config.node_width),
            float(max(config.min_node_height, height)),
            lines,
            source_ref,
        )
    return result


def _wrap_label(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]

    tokens: list[str] = []
    current = ""
    for char in text:
        current += char
        if char in {"_", "-", "."}:
            tokens.append(current)
            current = ""
    if current:
        tokens.append(current)

    lines: list[str] = []
    current = ""
    for token in tokens:
        candidate = current + token
        if current and len(candidate) > max_chars:
            lines.append(current.rstrip("_-."))
            current = token
        else:
            current = candidate
    if current:
        lines.append(current.rstrip("_-."))

    balanced: list[str] = []
    for line in lines:
        if len(line) <= max_chars + 4:
            balanced.append(line)
            continue
        for index in range(0, len(line), max_chars):
            balanced.append(line[index : index + max_chars])
    return balanced or [text]


def _place_vertical(
    graph: FlowGraph,
    groups: dict[int, list[str]],
    measured: dict[str, tuple[float, float, list[str], str | None]],
    config: RenderConfig,
    back_edge_count: int,
) -> GraphLayout:
    title_height = 48 if config.title else 0
    rank_widths = []
    rank_heights = []
    rank_rows: dict[int, list[list[str]]] = {}
    rank_row_heights: dict[int, list[float]] = {}
    for rank in groups:
        rows = _split_vertical_rank(groups[rank], config.max_rank_nodes_per_row)
        rank_rows[rank] = rows
        row_widths = []
        row_heights = []
        for nodes in rows:
            row_width = sum(measured[node_id][0] for node_id in nodes)
            row_width += max(0, len(nodes) - 1) * config.node_gap
            row_widths.append(row_width)
            row_heights.append(max(measured[node_id][1] for node_id in nodes))
        rank_width = max(row_widths, default=0)
        rank_height = sum(row_heights)
        rank_height += max(0, len(row_heights) - 1) * _vertical_rank_row_gap(config)
        rank_widths.append(rank_width)
        rank_heights.append(rank_height)
        rank_row_heights[rank] = row_heights

    back_edge_pad = 0 if back_edge_count == 0 else 90 + min(back_edge_count, 8) * 22
    width = max(rank_widths, default=0) + config.margin * 2 + back_edge_pad
    height = sum(rank_heights) + max(0, len(rank_heights) - 1) * config.rank_gap
    height += config.margin * 2 + title_height

    rank_by_node = {node_id: rank for rank, node_ids in groups.items() for node_id in node_ids}
    incoming: dict[str, list[str]] = defaultdict(list)
    for edge in graph.edges:
        if not edge.back:
            incoming[edge.target].append(edge.source)

    nodes_out: dict[str, LayoutNode] = {}
    y = config.margin + title_height
    for rank_index, rank in enumerate(groups):
        row_y = y
        rows = rank_rows[rank]
        for row_index, (nodes, row_height) in enumerate(zip(rows, rank_row_heights[rank])):
            if len(rows) > 1:
                centers = _vertical_wrapped_row_centers(
                    nodes,
                    measured,
                    width,
                    back_edge_pad,
                    rank_widths[rank_index],
                    row_index,
                    len(rows),
                    config,
                )
            else:
                centers = _vertical_row_centers(
                    nodes,
                    measured,
                    nodes_out,
                    incoming,
                    rank_by_node,
                    rank,
                    width,
                    back_edge_pad,
                    config,
                )
            for node_id, center_x in zip(nodes, centers):
                node_width, node_height, lines, source_ref = measured[node_id]
                nodes_out[node_id] = LayoutNode(
                    id=node_id,
                    rank=rank,
                    x=center_x,
                    y=row_y + row_height / 2,
                    width=node_width,
                    height=node_height,
                    label_lines=lines,
                    source_ref=source_ref,
                )
            row_y += row_height + _vertical_rank_row_gap(config)
        y += rank_heights[rank_index] + config.rank_gap

    return GraphLayout(nodes=nodes_out, ranks=groups, width=width, height=height, title_height=title_height)


def _split_vertical_rank(node_ids: list[str], max_nodes_per_row: int | None) -> list[list[str]]:
    if not max_nodes_per_row or max_nodes_per_row < 1 or len(node_ids) <= max_nodes_per_row:
        return [node_ids]

    return [node_ids[index : index + max_nodes_per_row] for index in range(0, len(node_ids), max_nodes_per_row)]


def _vertical_rank_row_gap(config: RenderConfig) -> float:
    return float(max(config.node_gap, config.edge_font_size * 3 + 12))


def _vertical_wrapped_row_centers(
    node_ids: list[str],
    measured: dict[str, tuple[float, float, list[str], str | None]],
    width: float,
    back_edge_pad: float,
    rank_width: float,
    row_index: int,
    row_count: int,
    config: RenderConfig,
) -> list[float]:
    widths = [measured[node_id][0] for node_id in node_ids]
    row_width = sum(widths) + max(0, len(widths) - 1) * config.node_gap
    usable_left = float(config.margin)
    usable_right = float(width - config.margin - back_edge_pad)
    usable_center = (usable_left + usable_right) / 2
    frame_width = min(rank_width, usable_right - usable_left)
    frame_left = usable_center - frame_width / 2
    spare = max(0.0, frame_width - row_width)
    if row_count == 1:
        offset = spare / 2
    elif row_index == 0:
        offset = 0.0
    elif row_index == row_count - 1:
        offset = spare
    else:
        offset = spare / 2
    centers = _regular_centers(frame_left + offset, widths, config.node_gap)
    return _fit_centers(centers, widths, usable_left, usable_right)


def _vertical_row_centers(
    node_ids: list[str],
    measured: dict[str, tuple[float, float, list[str], str | None]],
    placed: dict[str, LayoutNode],
    incoming: dict[str, list[str]],
    rank_by_node: dict[str, int],
    rank: int,
    width: float,
    back_edge_pad: float,
    config: RenderConfig,
) -> list[float]:
    widths = [measured[node_id][0] for node_id in node_ids]
    row_width = sum(widths) + max(0, len(widths) - 1) * config.node_gap
    usable_left = float(config.margin)
    usable_right = float(width - config.margin - back_edge_pad)
    usable_center = (usable_left + usable_right) / 2

    desired: list[float | None] = []
    for node_id in node_ids:
        source_x = [
            placed[source].x
            for source in incoming.get(node_id, [])
            if source in placed and rank_by_node.get(source, rank) < rank
        ]
        desired.append(mean(source_x) if source_x else None)

    known = [value for value in desired if value is not None]
    if known and max(known) - min(known) > row_width * 0.55:
        fallback = _regular_centers(usable_center - row_width / 2, widths, config.node_gap)
        targets = [value if value is not None else fallback[index] for index, value in enumerate(desired)]
        return _spread_centers(targets, widths, config.node_gap, usable_left, usable_right)

    center = mean(known) if known else usable_center
    centers = _regular_centers(center - row_width / 2, widths, config.node_gap)
    return _fit_centers(centers, widths, usable_left, usable_right)


def _regular_centers(left: float, widths: list[float], gap: float) -> list[float]:
    centers: list[float] = []
    x = left
    for width in widths:
        centers.append(x + width / 2)
        x += width + gap
    return centers


def _spread_centers(
    desired: list[float],
    widths: list[float],
    gap: float,
    left: float,
    right: float,
) -> list[float]:
    centers = [
        min(max(center, left + width / 2), right - width / 2)
        for center, width in zip(desired, widths)
    ]
    for index in range(1, len(centers)):
        min_center = centers[index - 1] + widths[index - 1] / 2 + gap + widths[index] / 2
        centers[index] = max(centers[index], min_center)
    for index in range(len(centers) - 2, -1, -1):
        max_center = centers[index + 1] - widths[index + 1] / 2 - gap - widths[index] / 2
        centers[index] = min(centers[index], max_center)
    return _fit_centers(centers, widths, left, right)


def _fit_centers(
    centers: list[float],
    widths: list[float],
    left: float,
    right: float,
) -> list[float]:
    if not centers:
        return centers
    left_overflow = left - (centers[0] - widths[0] / 2)
    if left_overflow > 0:
        centers = [center + left_overflow for center in centers]
    right_overflow = centers[-1] + widths[-1] / 2 - right
    if right_overflow > 0:
        centers = [center - right_overflow for center in centers]
    return centers


def _place_horizontal(
    groups: dict[int, list[str]],
    measured: dict[str, tuple[float, float, list[str], str | None]],
    config: RenderConfig,
    back_edge_count: int,
) -> GraphLayout:
    title_height = 48 if config.title else 0
    rank_widths = []
    rank_heights = []
    for rank in groups:
        nodes = groups[rank]
        rank_widths.append(max(measured[node_id][0] for node_id in nodes))
        rank_height = sum(measured[node_id][1] for node_id in nodes)
        rank_height += max(0, len(nodes) - 1) * config.node_gap
        rank_heights.append(rank_height)

    width = sum(rank_widths) + max(0, len(rank_widths) - 1) * config.rank_gap
    width += config.margin * 2
    back_edge_pad = 0 if back_edge_count == 0 else 90 + min(back_edge_count, 8) * 22
    height = max(rank_heights, default=0) + config.margin * 2 + title_height + back_edge_pad

    nodes_out: dict[str, LayoutNode] = {}
    x = config.margin
    for rank_index, rank in enumerate(groups):
        nodes = groups[rank]
        column_height = sum(measured[node_id][1] for node_id in nodes)
        column_height += max(0, len(nodes) - 1) * config.node_gap
        y = title_height + (height - title_height - column_height) / 2
        column_width = rank_widths[rank_index]
        for node_id in nodes:
            node_width, node_height, lines, source_ref = measured[node_id]
            nodes_out[node_id] = LayoutNode(
                id=node_id,
                rank=rank,
                x=x + column_width / 2,
                y=y + node_height / 2,
                width=node_width,
                height=node_height,
                label_lines=lines,
                source_ref=source_ref,
            )
            y += node_height + config.node_gap
        x += column_width + config.rank_gap

    return GraphLayout(nodes=nodes_out, ranks=groups, width=width, height=height, title_height=title_height)
