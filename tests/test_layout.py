from crewai_flowviz.models import Edge, FlowGraph, Node, RenderConfig
from crewai_flowviz.extractor import _ordered_nodes
from crewai_flowviz.layout import layout_graph
from crewai_flowviz.routing import back_edge_route
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


def test_vertical_layout_can_wrap_wide_ranks():
    graph = FlowGraph(
        name="Wide branches",
        nodes=[
            Node("start", "start", "start"),
            Node("route", "route", "router"),
            Node("a", "a"),
            Node("b", "b"),
            Node("c", "c"),
            Node("d", "d"),
        ],
        edges=[
            Edge("start", "route"),
            Edge("route", "a", "router", "a"),
            Edge("route", "b", "router", "b"),
            Edge("route", "c", "router", "c"),
            Edge("route", "d", "router", "d"),
        ],
        start_nodes=["start"],
        router_nodes=["route"],
    )

    unwrapped = layout_graph(graph, RenderConfig(node_width=200, node_gap=40, margin=40))
    wrapped = layout_graph(
        graph,
        RenderConfig(node_width=200, node_gap=40, margin=40, max_rank_nodes_per_row=2),
    )

    assert wrapped.width < unwrapped.width
    assert wrapped.height > unwrapped.height
    assert wrapped.nodes["a"].y == wrapped.nodes["b"].y
    assert wrapped.nodes["c"].y == wrapped.nodes["d"].y
    assert wrapped.nodes["c"].y > wrapped.nodes["a"].y


def test_back_edge_routes_fan_out_by_side():
    graph = FlowGraph(
        name="Retry routes",
        nodes=[
            Node("start", "start", "start"),
            Node("left", "left"),
            Node("same", "same"),
            Node("right", "right"),
            Node("outcome", "outcome", "router"),
        ],
        edges=[
            Edge("start", "left"),
            Edge("start", "same"),
            Edge("start", "right"),
            Edge("left", "outcome"),
            Edge("same", "outcome"),
            Edge("right", "outcome"),
        ],
        start_nodes=["start"],
        router_nodes=["outcome"],
    )
    layout = layout_graph(graph, RenderConfig(node_width=180, node_gap=50, margin=50))
    source = layout.nodes["outcome"]
    left = layout.nodes["left"]
    same = layout.nodes["same"]
    right = layout.nodes["right"]

    left_points, left_label = back_edge_route(source, left, layout, RenderConfig(), lane=0, label_size=(64, 24), side="left")
    same_points, same_label = back_edge_route(source, same, layout, RenderConfig(), lane=0, label_size=(88, 24), side="right")
    right_points, right_label = back_edge_route(source, right, layout, RenderConfig(), lane=1, label_size=(120, 24), side="right")

    assert left_points[1][0] < min(source.x - source.width / 2, left.x - left.width / 2)
    assert same_points[1][0] > source.x + source.width / 2
    assert right_points[1][0] > same_points[1][0]
    assert abs(left_label[0] - left_points[-1][0]) < 80
    assert abs(same_label[0] - same_points[-1][0]) < 120
    assert abs(right_label[0] - right_points[-1][0]) < 150
    assert left_label[1] > left.y + left.height / 2
    assert same_label[1] > same.y + same.height / 2
    assert right_label[1] > right.y + right.height / 2
