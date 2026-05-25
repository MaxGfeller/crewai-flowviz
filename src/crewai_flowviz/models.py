"""Core graph, theme, and render configuration models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import Any, Literal


NodeKind = Literal["start", "listen", "router", "start_router", "unknown"]
EdgeKind = Literal["listen", "and", "or", "router", "back"]
Direction = Literal["vertical", "horizontal"]


@dataclass(frozen=True)
class Node:
    id: str
    label: str
    kind: NodeKind = "listen"
    source_file: str | None = None
    source_line: int | None = None
    signature: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    kind: EdgeKind = "or"
    label: str = ""
    back: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FlowGraph:
    name: str
    nodes: list[Node]
    edges: list[Edge]
    start_nodes: list[str] = field(default_factory=list)
    router_nodes: list[str] = field(default_factory=list)
    description: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def node_map(self) -> dict[str, Node]:
        return {node.id: node for node in self.nodes}

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
            "start_nodes": list(self.start_nodes),
            "router_nodes": list(self.router_nodes),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class Theme:
    name: str
    background: str
    grid: str
    text: str
    muted_text: str
    node_fill: str
    node_border: str
    start_fill: str
    start_border: str
    start_text: str
    router_fill: str
    router_border: str
    edge: str
    edge_and: str
    edge_router: str
    edge_back: str
    badge_fill: str
    badge_text: str
    label_fill: str
    label_border: str
    shadow: str

    def merged(self, values: dict[str, Any]) -> Theme:
        allowed = {key for key in asdict(self) if key != "name"}
        overrides = {key: value for key, value in values.items() if key in allowed}
        return replace(self, **overrides)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RenderConfig:
    direction: Direction = "vertical"
    width: int | None = None
    height: int | None = None
    margin: int = 56
    node_width: int = 260
    min_node_height: int = 74
    rank_gap: int = 124
    node_gap: int = 56
    font_family: str = "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    mono_family: str = "JetBrains Mono, SFMono-Regular, Consolas, Liberation Mono, monospace"
    font_size: int = 15
    small_font_size: int = 11
    edge_font_size: int = 12
    corner_radius: int = 12
    show_kinds: bool = True
    show_edge_labels: bool = True
    show_source_refs: bool = False
    show_grid: bool = True
    fit: bool = True
    title: str | None = None
    theme: str = "crew"

    def merged(self, values: dict[str, Any]) -> RenderConfig:
        allowed = set(asdict(self))
        overrides = {key: value for key, value in values.items() if key in allowed}
        return replace(self, **overrides)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
