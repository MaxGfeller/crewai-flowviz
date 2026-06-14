from crewai_flowviz.models import Edge, FlowGraph, Node, RenderConfig
from crewai_flowviz.extractor import _ordered_nodes
from crewai_flowviz.layout import layout_graph
from crewai_flowviz.svg import render_svg


def test_svg_renders_router_and_back_edge():
    graph = FlowGraph(
        name="Demo",
        nodes=[
            Node("start", "start", "start"),
            Node("work", "work", "listen"),
            Node("decide", "decide", "router"),
        ],
        edges=[
            Edge("start", "work", "or"),
            Edge("work", "decide", "or"),
            Edge("decide", "work", "back", "retry", back=True),
        ],
        start_nodes=["start"],
        router_nodes=["decide"],
    )

    svg = render_svg(graph, RenderConfig(width=900, theme="mono"))

    assert "<svg" in svg
    assert "retry" in svg
    assert "arrow-back" in svg


def test_horizontal_layout_sets_requested_dimension():
    graph = FlowGraph(
        name="Demo",
        nodes=[Node("a", "a", "start"), Node("b", "b", "listen")],
        edges=[Edge("a", "b", "or")],
        start_nodes=["a"],
    )

    svg = render_svg(graph, RenderConfig(direction="horizontal", width=1200))

    assert 'width="1200"' in svg
    assert 'viewBox="' in svg


def test_svg_can_omit_background_for_transparent_exports():
    graph = FlowGraph(
        name="Transparent",
        nodes=[Node("a", "a", "start")],
        edges=[],
        start_nodes=["a"],
    )

    svg = render_svg(graph, RenderConfig(export_background=False, show_grid=False))

    assert '<rect width="100%" height="100%"' not in svg


def test_node_order_prefers_source_lines_over_method_dict_order():
    class FlowLike:
        _methods = {"second": object(), "first": object()}

    nodes = [
        Node("second", "second", source_file="/tmp/flow.py", source_line=20),
        Node("first", "first", source_file="/tmp/flow.py", source_line=10),
    ]

    ordered = _ordered_nodes(nodes, FlowLike())

    assert [node.id for node in ordered] == ["first", "second"]


def test_terminal_nodes_do_not_pull_branches_to_front():
    graph = FlowGraph(
        name="Branches",
        nodes=[
            Node("start", "start", "start"),
            Node("route", "route", "router"),
            Node("billing", "billing"),
            Node("technical", "technical"),
            Node("spam", "spam"),
            Node("outcome", "outcome", "router"),
            Node("finalize_spam", "finalize_spam"),
            Node("converge", "converge"),
        ],
        edges=[
            Edge("start", "route"),
            Edge("route", "billing", "router", "billing"),
            Edge("route", "technical", "router", "technical"),
            Edge("route", "spam", "router", "spam"),
            Edge("billing", "outcome"),
            Edge("technical", "outcome"),
            Edge("spam", "finalize_spam"),
            Edge("outcome", "converge", "router", "drafted"),
        ],
        start_nodes=["start"],
        router_nodes=["route", "outcome"],
    )

    layout = layout_graph(graph, RenderConfig())

    assert layout.ranks[2] == ["billing", "technical", "spam"]
    assert layout.nodes["finalize_spam"].x > layout.nodes["outcome"].x
    assert abs(layout.nodes["finalize_spam"].x - layout.nodes["spam"].x) < abs(
        layout.nodes["finalize_spam"].x - layout.nodes["technical"].x
    )
