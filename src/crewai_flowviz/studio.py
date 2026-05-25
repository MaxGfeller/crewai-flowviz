"""Tiny local configuration UI for Flow rendering."""

from __future__ import annotations

from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
import webbrowser

from crewai_flowviz.models import FlowGraph, RenderConfig
from crewai_flowviz.svg import render_svg
from crewai_flowviz.themes import list_themes


def serve_studio(
    graph: FlowGraph,
    config: RenderConfig,
    theme_overrides: dict[str, object] | None = None,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    open_browser: bool = True,
) -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - stdlib API
            parsed = urlparse(self.path)
            if parsed.path == "/":
                self._send_html(_studio_html(graph, config))
                return
            if parsed.path in {"/svg", "/download.svg"}:
                cfg = _config_from_query(config, parse_qs(parsed.query))
                svg = render_svg(graph, cfg, theme_overrides=theme_overrides)
                headers = {}
                if parsed.path == "/download.svg":
                    headers["Content-Disposition"] = f'attachment; filename="{graph.name}.svg"'
                self._send("image/svg+xml; charset=utf-8", svg.encode("utf-8"), headers=headers)
                return
            self.send_error(404)

        def log_message(self, fmt: str, *args: object) -> None:
            return

        def _send_html(self, html: str) -> None:
            self._send("text/html; charset=utf-8", html.encode("utf-8"))

        def _send(self, content_type: str, body: bytes, headers: dict[str, str] | None = None) -> None:
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            for key, value in (headers or {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{server.server_port}/"
    if open_browser:
        webbrowser.open(url)
    print(f"[studio] serving {graph.name} at {url}")
    print("[studio] press Ctrl-C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[studio] stopped")
    finally:
        server.server_close()


def _config_from_query(config: RenderConfig, query: dict[str, list[str]]) -> RenderConfig:
    values: dict[str, object] = {}
    for key in [
        "theme",
        "direction",
        "width",
        "height",
        "node_width",
        "rank_gap",
        "node_gap",
        "margin",
    ]:
        if key not in query or not query[key]:
            continue
        raw = query[key][0]
        if key in {"width", "height"} and raw == "":
            values[key] = None
        elif key in {"width", "height", "node_width", "rank_gap", "node_gap", "margin"}:
            values[key] = int(raw)
        else:
            values[key] = raw
    values["show_grid"] = query.get("grid", ["1"])[0] == "1"
    values["show_edge_labels"] = query.get("labels", ["1"])[0] == "1"
    values["show_source_refs"] = query.get("sources", ["0"])[0] == "1"
    return replace(config, **values)


def _studio_html(graph: FlowGraph, config: RenderConfig) -> str:
    theme_options = "\n".join(
        f'<option value="{name}" {"selected" if name == config.theme else ""}>{name}</option>'
        for name in list_themes()
    )
    direction_options = "\n".join(
        f'<option value="{name}" {"selected" if name == config.direction else ""}>{name}</option>'
        for name in ["vertical", "horizontal"]
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{graph.name} | crewai-flowviz</title>
  <style>
    :root {{
      color-scheme: light dark;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #111418;
      color: #eef2f5;
    }}
    html, body {{ height: 100%; }}
    body {{ margin: 0; height: 100vh; overflow: hidden; display: grid; grid-template-columns: 320px minmax(0, 1fr); }}
    aside {{ height: 100vh; box-sizing: border-box; border-right: 1px solid #2a323a; padding: 18px; background: #151a20; overflow: auto; }}
    main {{ height: 100vh; min-width: 0; min-height: 0; overflow: auto; background: #20262c; }}
    h1 {{ font-size: 18px; line-height: 1.25; margin: 0 0 18px; }}
    label {{ display: grid; gap: 6px; font-size: 12px; color: #aeb8c2; margin: 0 0 14px; }}
    input, select {{ border: 1px solid #3a4650; border-radius: 6px; background: #0f1318; color: #eef2f5; padding: 8px 9px; font: inherit; }}
    input[type="checkbox"] {{ width: 18px; height: 18px; }}
    .check {{ display: flex; align-items: center; gap: 9px; margin-bottom: 12px; color: #d8e0e7; font-size: 13px; }}
    .row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }}
    .buttons {{ display: flex; gap: 8px; margin-top: 18px; }}
    button, a.button {{ border: 0; border-radius: 6px; background: #ff665c; color: white; padding: 9px 11px; text-decoration: none; font-weight: 700; cursor: pointer; }}
    a.button.secondary {{ background: #33404b; }}
    #canvas {{ width: max-content; min-width: 100%; min-height: 100%; display: grid; place-items: start center; padding: 24px; box-sizing: border-box; }}
    #canvas svg {{ max-width: none; background: white; box-shadow: 0 20px 70px rgba(0,0,0,.35); }}
    .meta {{ color: #7f8a94; font-size: 12px; margin-bottom: 18px; }}
  </style>
</head>
<body>
  <aside>
    <h1>{graph.name}</h1>
    <div class="meta">{len(graph.nodes)} nodes · {len(graph.edges)} edges</div>
    <label>Theme<select id="theme">{theme_options}</select></label>
    <label>Direction<select id="direction">{direction_options}</select></label>
    <div class="row">
      <label>Width<input id="width" type="number" min="320" value="{config.width or ""}" placeholder="auto"></label>
      <label>Height<input id="height" type="number" min="240" value="{config.height or ""}" placeholder="auto"></label>
    </div>
    <label>Node width<input id="node_width" type="range" min="180" max="420" value="{config.node_width}"><span id="node_width_value"></span></label>
    <label>Rank gap<input id="rank_gap" type="range" min="70" max="240" value="{config.rank_gap}"><span id="rank_gap_value"></span></label>
    <label>Node gap<input id="node_gap" type="range" min="24" max="160" value="{config.node_gap}"><span id="node_gap_value"></span></label>
    <label>Margin<input id="margin" type="range" min="20" max="120" value="{config.margin}"><span id="margin_value"></span></label>
    <label class="check"><input id="grid" type="checkbox" checked> Grid</label>
    <label class="check"><input id="labels" type="checkbox" checked> Edge labels</label>
    <label class="check"><input id="sources" type="checkbox"> Source refs</label>
    <div class="buttons">
      <button id="refresh">Refresh</button>
      <a class="button secondary" id="download" href="/download.svg">Download SVG</a>
    </div>
  </aside>
  <main><div id="canvas"></div></main>
  <script>
    const ids = ["theme","direction","width","height","node_width","rank_gap","node_gap","margin","grid","labels","sources"];
    const sliderIds = ["node_width","rank_gap","node_gap","margin"];
    function params() {{
      const q = new URLSearchParams();
      for (const id of ids) {{
        const el = document.getElementById(id);
        if (el.type === "checkbox") q.set(id, el.checked ? "1" : "0");
        else q.set(id, el.value);
      }}
      return q.toString();
    }}
    async function refresh() {{
      for (const id of sliderIds) document.getElementById(id + "_value").textContent = document.getElementById(id).value;
      const q = params();
      const res = await fetch("/svg?" + q);
      document.getElementById("canvas").innerHTML = await res.text();
      document.getElementById("download").href = "/download.svg?" + q;
    }}
    for (const id of ids) document.getElementById(id).addEventListener("input", refresh);
    document.getElementById("refresh").addEventListener("click", refresh);
    refresh();
  </script>
</body>
</html>"""
