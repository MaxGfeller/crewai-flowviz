"""Tiny local configuration UI for Flow rendering."""

from __future__ import annotations

from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
import webbrowser

from crewai_flowviz.exporters import render_png_bytes
from crewai_flowviz.models import FlowGraph, RenderConfig
from crewai_flowviz.svg import render_svg
from crewai_flowviz.themes import get_theme, list_themes


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
            if parsed.path == "/download.png":
                cfg = _config_from_query(config, parse_qs(parsed.query))
                theme = get_theme(cfg.theme, theme_overrides)
                png = render_png_bytes(graph, cfg, theme)
                self._send(
                    "image/png",
                    png,
                    headers={"Content-Disposition": f'attachment; filename="{graph.name}.png"'},
                )
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
    values["export_background"] = query.get("background", ["1"])[0] == "1"
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
      --ink: #171b1e;
      --panel: #f5f2eb;
      --panel-2: #ebe6dc;
      --line: #d3ccc0;
      --muted: #736d63;
      --text: #201f1b;
      --field: #fffcf5;
      --accent: #ef5b4e;
      --accent-2: #1e8f84;
      --dark: #222a2a;
      --dark-2: #182020;
      --dark-line: #354141;
      --canvas: #242927;
      font-family: "Avenir Next", Avenir, "Segoe UI", ui-sans-serif, system-ui, sans-serif;
      background: var(--ink);
      color: var(--text);
    }}
    html, body {{ height: 100%; }}
    body {{
      margin: 0;
      height: 100vh;
      overflow: hidden;
      display: grid;
      grid-template-columns: 360px minmax(0, 1fr);
      background:
        radial-gradient(circle at 0 0, rgba(239,91,78,.18), transparent 30%),
        linear-gradient(120deg, var(--dark), var(--dark-2));
    }}
    aside {{
      height: 100vh;
      box-sizing: border-box;
      display: grid;
      grid-template-rows: auto 1fr auto;
      border-right: 1px solid var(--line);
      background: var(--panel);
      box-shadow: 18px 0 50px rgba(0,0,0,.18);
      min-width: 0;
    }}
    main {{
      height: 100vh;
      min-width: 0;
      min-height: 0;
      overflow: hidden;
      display: grid;
      grid-template-rows: auto minmax(0, 1fr);
      background: var(--canvas);
    }}
    h1 {{
      font-size: 20px;
      line-height: 1.16;
      letter-spacing: 0;
      margin: 0;
      color: var(--text);
    }}
    label {{ margin: 0; }}
    input, select {{
      width: 100%;
      box-sizing: border-box;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--field);
      color: var(--text);
      padding: 8px 9px;
      font: inherit;
      min-height: 36px;
    }}
    select {{
      appearance: none;
      background-image: linear-gradient(45deg, transparent 50%, var(--muted) 50%), linear-gradient(135deg, var(--muted) 50%, transparent 50%);
      background-position: calc(100% - 16px) 15px, calc(100% - 11px) 15px;
      background-size: 5px 5px, 5px 5px;
      background-repeat: no-repeat;
      padding-right: 32px;
    }}
    input:focus, select:focus, button:focus-visible, a.button:focus-visible {{
      outline: 2px solid rgba(239,91,78,.35);
      outline-offset: 2px;
    }}
    input[type="checkbox"] {{
      appearance: none;
      width: 34px;
      min-width: 34px;
      height: 20px;
      min-height: 20px;
      border-radius: 999px;
      padding: 0;
      background: #d8d1c6;
      position: relative;
      cursor: pointer;
      transition: background .16s ease;
    }}
    input[type="checkbox"]::after {{
      content: "";
      position: absolute;
      width: 14px;
      height: 14px;
      left: 2px;
      top: 2px;
      border-radius: 999px;
      background: #fffaf1;
      box-shadow: 0 1px 2px rgba(0,0,0,.22);
      transition: transform .16s ease;
    }}
    input[type="checkbox"]:checked {{ background: var(--accent-2); }}
    input[type="checkbox"]:checked::after {{ transform: translateX(14px); }}
    input[type="range"] {{
      padding: 0;
      border: 0;
      min-height: 20px;
      accent-color: var(--accent);
      background: transparent;
    }}
    .sidebar-head {{
      padding: 22px 20px 18px;
      border-bottom: 1px solid var(--line);
      background: linear-gradient(180deg, #fffaf1, var(--panel));
    }}
    .meta {{
      display: flex;
      gap: 8px;
      color: var(--muted);
      font-size: 12px;
      margin-top: 10px;
      font-family: "SFMono-Regular", Menlo, Consolas, monospace;
    }}
    .meta span {{
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 4px 7px;
      background: rgba(255,255,255,.36);
    }}
    .controls {{
      overflow: auto;
      padding: 4px 20px 22px;
    }}
    .section {{
      padding: 18px 0;
      border-bottom: 1px solid var(--line);
    }}
    .section:last-child {{ border-bottom: 0; }}
    .section-title {{
      margin: 0 0 12px;
      font-size: 11px;
      line-height: 1;
      text-transform: uppercase;
      letter-spacing: 0;
      color: var(--muted);
      font-weight: 800;
    }}
    .control {{
      display: grid;
      gap: 7px;
      margin-bottom: 14px;
      font-size: 12px;
      color: var(--muted);
      font-weight: 700;
    }}
    .section > .control:last-child {{ margin-bottom: 0; }}
    .row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; align-items: start; }}
    .row .control {{ margin-bottom: 0; align-self: start; }}
    .range-head {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
    }}
    .value-pill {{
      font-family: "SFMono-Regular", Menlo, Consolas, monospace;
      color: var(--text);
      border: 1px solid var(--line);
      background: rgba(255,255,255,.42);
      border-radius: 999px;
      padding: 3px 7px;
      min-width: 34px;
      text-align: center;
    }}
    .check {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 7px 0;
      color: var(--text);
      font-size: 13px;
      font-weight: 700;
    }}
    .actions {{
      border-top: 1px solid var(--line);
      padding: 14px 20px 18px;
      background: rgba(235,230,220,.92);
      backdrop-filter: blur(10px);
    }}
    .buttons {{ display: grid; grid-template-columns: 1fr 1fr; gap: 9px; }}
    button, a.button {{
      border: 1px solid transparent;
      border-radius: 6px;
      background: var(--accent);
      color: white;
      padding: 10px 11px;
      text-decoration: none;
      font-weight: 800;
      cursor: pointer;
      text-align: center;
      font-size: 13px;
      line-height: 1.1;
    }}
    a.button.secondary {{
      background: var(--dark);
      border-color: rgba(255,255,255,.08);
    }}
    button:hover, a.button:hover {{ filter: brightness(1.06); }}
    .stagebar {{
      min-width: 0;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 18px;
      padding: 13px 18px;
      border-bottom: 1px solid var(--dark-line);
      background: rgba(24,32,32,.93);
      color: #f4eee5;
    }}
    .stage-title {{
      font-weight: 800;
      font-size: 14px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    #status {{
      font-family: "SFMono-Regular", Menlo, Consolas, monospace;
      color: #b8c9c7;
      font-size: 12px;
      white-space: nowrap;
    }}
    .viewport {{
      min-width: 0;
      min-height: 0;
      overflow: auto;
      background:
        linear-gradient(rgba(255,255,255,.035) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,.035) 1px, transparent 1px),
        var(--canvas);
      background-size: 28px 28px;
    }}
    #canvas {{
      width: max-content;
      min-width: 100%;
      min-height: 100%;
      display: grid;
      place-items: start center;
      padding: 32px;
      box-sizing: border-box;
    }}
    #canvas svg {{
      max-width: none;
      background-color: white;
      background-image:
        linear-gradient(45deg, rgba(0,0,0,.08) 25%, transparent 25%),
        linear-gradient(-45deg, rgba(0,0,0,.08) 25%, transparent 25%),
        linear-gradient(45deg, transparent 75%, rgba(0,0,0,.08) 75%),
        linear-gradient(-45deg, transparent 75%, rgba(0,0,0,.08) 75%);
      background-position: 0 0, 0 8px, 8px -8px, -8px 0;
      background-size: 16px 16px;
      box-shadow: 0 18px 56px rgba(0,0,0,.42);
      border-radius: 2px;
    }}
    @media (max-width: 840px) {{
      body {{ grid-template-columns: 1fr; grid-template-rows: minmax(280px, 42vh) minmax(0, 1fr); }}
      aside {{ height: auto; min-height: 0; border-right: 0; border-bottom: 1px solid var(--line); }}
      main {{ height: auto; min-height: 0; }}
      .buttons {{ grid-template-columns: 1fr 1fr; }}
    }}
  </style>
</head>
<body>
  <aside>
    <div class="sidebar-head">
      <h1>{graph.name}</h1>
      <div class="meta"><span>{len(graph.nodes)} nodes</span><span>{len(graph.edges)} edges</span></div>
    </div>
    <div class="controls">
      <section class="section">
        <h2 class="section-title">Appearance</h2>
        <label class="control">Theme<select id="theme">{theme_options}</select></label>
        <label class="control">Direction<select id="direction">{direction_options}</select></label>
      </section>
      <section class="section">
        <h2 class="section-title">Frame</h2>
        <div class="row">
          <label class="control">Width<input id="width" type="number" min="320" value="{config.width or ""}" placeholder="auto"></label>
          <label class="control">Height<input id="height" type="number" min="240" value="{config.height or ""}" placeholder="auto"></label>
        </div>
      </section>
      <section class="section">
        <h2 class="section-title">Spacing</h2>
        <label class="control"><span class="range-head">Node width<span class="value-pill" id="node_width_value"></span></span><input id="node_width" type="range" min="180" max="420" value="{config.node_width}"></label>
        <label class="control"><span class="range-head">Rank gap<span class="value-pill" id="rank_gap_value"></span></span><input id="rank_gap" type="range" min="70" max="240" value="{config.rank_gap}"></label>
        <label class="control"><span class="range-head">Node gap<span class="value-pill" id="node_gap_value"></span></span><input id="node_gap" type="range" min="24" max="160" value="{config.node_gap}"></label>
        <label class="control"><span class="range-head">Margin<span class="value-pill" id="margin_value"></span></span><input id="margin" type="range" min="20" max="120" value="{config.margin}"></label>
      </section>
      <section class="section">
        <h2 class="section-title">Layers</h2>
        <label class="check"><span>Grid</span><input id="grid" type="checkbox" checked></label>
        <label class="check"><span>Edge labels</span><input id="labels" type="checkbox" checked></label>
        <label class="check"><span>Source refs</span><input id="sources" type="checkbox"></label>
        <label class="check"><span>Export background color</span><input id="background" type="checkbox" checked></label>
      </section>
    </div>
    <div class="actions">
      <div class="buttons">
      <a class="button secondary" id="download" href="/download.svg">Download SVG</a>
      <a class="button secondary" id="download-png" href="/download.png">Download PNG</a>
      </div>
    </div>
  </aside>
  <main>
    <header class="stagebar">
      <div class="stage-title">{graph.name}</div>
      <div id="status">Rendering</div>
    </header>
    <section class="viewport"><div id="canvas"></div></section>
  </main>
  <script>
    const ids = ["theme","direction","width","height","node_width","rank_gap","node_gap","margin","grid","labels","sources","background"];
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
      const svgText = await res.text();
      document.getElementById("canvas").innerHTML = svgText;
      const svg = document.querySelector("#canvas svg");
      if (svg) document.getElementById("status").textContent = `${{svg.getAttribute("width")}} x ${{svg.getAttribute("height")}}`;
      document.getElementById("download").href = "/download.svg?" + q;
      document.getElementById("download-png").href = "/download.png?" + q;
    }}
    for (const id of ids) document.getElementById(id).addEventListener("input", refresh);
    refresh();
  </script>
</body>
</html>"""
