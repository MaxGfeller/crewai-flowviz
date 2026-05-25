from crewai_flowviz.models import Edge, FlowGraph, Node, RenderConfig
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
