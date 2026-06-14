"""CrewAI Flow import and graph extraction."""

from __future__ import annotations

import importlib
import inspect
from collections.abc import Iterable
from typing import Any

from crewai_flowviz.models import Edge, FlowGraph, Node


def import_flow(spec: str) -> Any:
    """Import a Flow class, instance, or factory from ``module:object``."""
    if ":" not in spec:
        raise ValueError("flow spec must look like 'module.path:FlowClass'")

    module_name, object_path = spec.split(":", 1)
    module = importlib.import_module(module_name)
    obj: Any = module
    for part in object_path.split("."):
        obj = getattr(obj, part)

    if inspect.isclass(obj):
        return obj()
    if callable(obj) and not _looks_like_flow(obj):
        produced = obj()
        if _looks_like_flow(produced):
            return produced
    return obj


def extract_flow_graph(flow: Any) -> FlowGraph:
    """Extract a stable graph model from a CrewAI Flow instance."""
    if not _looks_like_flow(flow):
        raise TypeError(f"object does not look like a CrewAI Flow: {type(flow).__name__}")

    try:
        return _extract_with_crewai_builder(flow)
    except Exception:
        return _extract_from_private_metadata(flow)


def _looks_like_flow(obj: Any) -> bool:
    return hasattr(obj, "_listeners") and hasattr(obj, "_start_methods")


def _extract_with_crewai_builder(flow: Any) -> FlowGraph:
    from crewai.flow.visualization import build_flow_structure

    structure = build_flow_structure(flow)
    nodes: list[Node] = []
    for node_id, metadata in structure["nodes"].items():
        kind = str(metadata.get("type", "listen"))
        source_file, source_line = _source_info(
            flow,
            str(node_id),
            metadata.get("source_file"),
            metadata.get("source_start_line"),
        )
        nodes.append(
            Node(
                id=str(node_id),
                label=str(node_id),
                kind=kind if kind in {"start", "listen", "router", "start_router"} else "unknown",
                source_file=source_file,
                source_line=source_line,
                signature=dict(metadata.get("method_signature", {})),
                metadata=dict(metadata),
            )
        )

    edges: list[Edge] = []
    for edge in structure["edges"]:
        condition = edge.get("condition_type")
        is_router = bool(edge.get("is_router_path"))
        kind = "router" if is_router else _condition_to_kind(condition)
        label = ""
        if is_router:
            label = str(edge.get("router_path_label", ""))
        elif condition == "AND":
            label = "AND"
        elif condition == "OR":
            label = ""
        edges.append(
            Edge(
                source=str(edge["source"]),
                target=str(edge["target"]),
                kind=kind,
                label=label,
                metadata=dict(edge),
            )
        )

    graph = FlowGraph(
        name=getattr(flow, "name", None) or flow.__class__.__name__,
        description=inspect.getdoc(flow.__class__),
        nodes=_ordered_nodes(nodes, flow),
        edges=_dedupe_edges(edges),
        start_nodes=[str(item) for item in structure.get("start_methods", [])],
        router_nodes=[str(item) for item in structure.get("router_methods", [])],
        metadata={"source": "crewai.flow.visualization.build_flow_structure"},
    )
    return _with_back_edges(graph)


def _extract_from_private_metadata(flow: Any) -> FlowGraph:
    listeners: dict[str, Any] = dict(getattr(flow, "_listeners", {}))
    routers = {str(item) for item in getattr(flow, "_routers", set())}
    router_paths: dict[str, Iterable[str]] = dict(getattr(flow, "_router_paths", {}))
    start_methods = [str(item) for item in getattr(flow, "_start_methods", [])]

    node_ids: list[str] = []

    def add_node(node_id: str) -> None:
        if node_id and node_id not in node_ids:
            node_ids.append(node_id)

    for method in start_methods:
        add_node(method)
    for method in listeners:
        add_node(str(method))
    for method in routers:
        add_node(method)

    method_names = set(node_ids)
    edges: list[Edge] = []

    for target, condition in listeners.items():
        condition_type, sources = _condition_sources(condition)
        for source in sources:
            if source in method_names:
                edges.append(
                    Edge(
                        source=source,
                        target=str(target),
                        kind=_condition_to_kind(condition_type),
                        label="AND" if condition_type == "AND" else "",
                    )
                )

    for router, paths in router_paths.items():
        add_node(str(router))
        for path in paths:
            for target, condition in listeners.items():
                _, sources = _condition_sources(condition)
                if str(path) in sources:
                    edges.append(
                        Edge(
                            source=str(router),
                            target=str(target),
                            kind="router",
                            label=str(path),
                        )
                    )

    nodes = [
        Node(
            id=node_id,
            label=node_id,
            kind="start" if node_id in start_methods else "router" if node_id in routers else "listen",
            source_file=_source_info(flow, node_id)[0],
            source_line=_source_info(flow, node_id)[1],
        )
        for node_id in node_ids
    ]
    graph = FlowGraph(
        name=getattr(flow, "name", None) or flow.__class__.__name__,
        description=inspect.getdoc(flow.__class__),
        nodes=nodes,
        edges=_dedupe_edges(edges),
        start_nodes=start_methods,
        router_nodes=sorted(routers),
        metadata={"source": "private CrewAI Flow metadata"},
    )
    return _with_back_edges(graph)


def _condition_to_kind(condition: Any) -> str:
    condition_text = str(condition or "OR").upper()
    if condition_text == "AND":
        return "and"
    return "or"


def _condition_sources(condition: Any) -> tuple[str, list[str]]:
    if isinstance(condition, tuple) and len(condition) == 2:
        condition_type, raw_sources = condition
        return str(condition_type).upper(), list(_flatten_sources(raw_sources))
    if isinstance(condition, dict):
        condition_type = str(condition.get("type", "OR")).upper()
        return condition_type, list(_flatten_sources(condition.get("conditions", [])))
    return "OR", list(_flatten_sources(condition))


def _flatten_sources(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
        return
    if isinstance(value, dict):
        yield from _flatten_sources(value.get("conditions", []))
        return
    if isinstance(value, Iterable):
        for item in value:
            yield from _flatten_sources(item)


def _ordered_nodes(nodes: list[Node], flow: Any) -> list[Node]:
    methods = list(getattr(flow, "_methods", {}).keys())
    method_order = {str(name): index for index, name in enumerate(methods)}
    fallback_order = {node.id: index for index, node in enumerate(nodes)}

    source_files = [node.source_file for node in nodes if node.source_file]
    primary_source_file = max(set(source_files), key=source_files.count) if source_files else None

    def key(node: Node) -> tuple[int, str, int, int, int, str]:
        has_primary_source = bool(node.source_file and node.source_file == primary_source_file)
        has_source_line = node.source_line is not None
        return (
            0 if has_primary_source and has_source_line else 1,
            node.source_file or "",
            node.source_line if node.source_line is not None else 10**9,
            method_order.get(node.id, len(method_order)),
            fallback_order[node.id],
            node.id,
        )

    return sorted(nodes, key=key)


def _source_info(
    flow: Any,
    method_name: str,
    fallback_file: Any = None,
    fallback_line: Any = None,
) -> tuple[str | None, int | None]:
    try:
        raw = flow.__class__.__dict__.get(method_name) or getattr(flow.__class__, method_name)
        func = getattr(raw, "_meth", raw)
        if hasattr(func, "__wrapped__") and not inspect.isfunction(func):
            func = func.__wrapped__
        source_file = inspect.getsourcefile(func)
        _, source_line = inspect.getsourcelines(func)
        if source_file:
            return str(source_file), int(source_line)
    except Exception:
        pass

    source_file = str(fallback_file) if fallback_file else None
    source_line = int(fallback_line) if isinstance(fallback_line, int) else None
    return source_file, source_line


def _dedupe_edges(edges: list[Edge]) -> list[Edge]:
    seen: set[tuple[str, str, str, str]] = set()
    result: list[Edge] = []
    for edge in edges:
        key = (edge.source, edge.target, edge.kind, edge.label)
        if key in seen:
            continue
        seen.add(key)
        result.append(edge)
    return result


def _with_back_edges(graph: FlowGraph) -> FlowGraph:
    reachable = _reachability(graph)
    edges: list[Edge] = []
    for edge in graph.edges:
        is_back = edge.kind == "router" and edge.source in reachable.get(edge.target, set())
        if is_back:
            edges.append(
                Edge(
                    source=edge.source,
                    target=edge.target,
                    kind="back" if edge.kind == "router" else edge.kind,
                    label=edge.label,
                    back=True,
                    metadata=edge.metadata,
                )
            )
        else:
            edges.append(edge)
    return FlowGraph(
        name=graph.name,
        nodes=graph.nodes,
        edges=edges,
        start_nodes=graph.start_nodes,
        router_nodes=graph.router_nodes,
        description=graph.description,
        metadata=graph.metadata,
    )


def _reachability(graph: FlowGraph) -> dict[str, set[str]]:
    outgoing: dict[str, list[str]] = {node.id: [] for node in graph.nodes}
    for edge in graph.edges:
        outgoing.setdefault(edge.source, []).append(edge.target)

    result: dict[str, set[str]] = {}
    for node in outgoing:
        seen: set[str] = set()
        stack = list(outgoing[node])
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            stack.extend(outgoing.get(current, []))
        result[node] = seen
    return result
