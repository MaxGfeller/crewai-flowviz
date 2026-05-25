"""Built-in and user-overridable render themes."""

from __future__ import annotations

from crewai_flowviz.models import Theme


THEMES: dict[str, Theme] = {
    "crew": Theme(
        name="crew",
        background="#fbfbfa",
        grid="#ececea",
        text="#202124",
        muted_text="#6d6f75",
        node_fill="#ffffff",
        node_border="#3c4043",
        start_fill="#ff6b63",
        start_border="#bf3f37",
        start_text="#ffffff",
        router_fill="#fff8f7",
        router_border="#ff5a50",
        edge="#202124",
        edge_and="#ff5a50",
        edge_router="#ff5a50",
        edge_back="#a54be8",
        badge_fill="#f0f0ee",
        badge_text="#686a70",
        label_fill="#ffffff",
        label_border="#d9d9d6",
        shadow="#d8d8d4",
    ),
    "slate": Theme(
        name="slate",
        background="#101418",
        grid="#1c2329",
        text="#eff3f7",
        muted_text="#a7b1bc",
        node_fill="#172027",
        node_border="#61707e",
        start_fill="#f9735f",
        start_border="#ffad9c",
        start_text="#fff7f4",
        router_fill="#20191a",
        router_border="#ff866f",
        edge="#c6d0d9",
        edge_and="#ff866f",
        edge_router="#ff866f",
        edge_back="#a78bfa",
        badge_fill="#26313a",
        badge_text="#c5ced6",
        label_fill="#172027",
        label_border="#42505c",
        shadow="#07090b",
    ),
    "mono": Theme(
        name="mono",
        background="#ffffff",
        grid="#eeeeee",
        text="#111111",
        muted_text="#666666",
        node_fill="#ffffff",
        node_border="#111111",
        start_fill="#111111",
        start_border="#111111",
        start_text="#ffffff",
        router_fill="#ffffff",
        router_border="#111111",
        edge="#111111",
        edge_and="#111111",
        edge_router="#111111",
        edge_back="#555555",
        badge_fill="#eeeeee",
        badge_text="#333333",
        label_fill="#ffffff",
        label_border="#cccccc",
        shadow="#d0d0d0",
    ),
    "mint": Theme(
        name="mint",
        background="#f7fbf8",
        grid="#e5eee8",
        text="#16201a",
        muted_text="#64706a",
        node_fill="#ffffff",
        node_border="#2f4638",
        start_fill="#1f9d76",
        start_border="#15765a",
        start_text="#ffffff",
        router_fill="#f1fff8",
        router_border="#1f9d76",
        edge="#26322c",
        edge_and="#1f9d76",
        edge_router="#1f9d76",
        edge_back="#7c3aed",
        badge_fill="#e6f3ed",
        badge_text="#4f665c",
        label_fill="#ffffff",
        label_border="#cbded4",
        shadow="#cfdbd4",
    ),
}


def get_theme(name: str, overrides: dict[str, object] | None = None) -> Theme:
    try:
        theme = THEMES[name]
    except KeyError as exc:
        available = ", ".join(sorted(THEMES))
        raise ValueError(f"unknown theme '{name}'. Available themes: {available}") from exc
    if overrides:
        return theme.merged(overrides)
    return theme


def list_themes() -> list[str]:
    return sorted(THEMES)
