# crewai-flowviz

Configurable static and interactive diagrams for CrewAI Flows.

This is a standalone package draft. It extracts a CrewAI Flow into a stable graph model, then renders SVG/PNG/JSON/DOT from that model. It also includes a tiny local studio for trying themes, orientation, spacing, and dimensions without changing code.

## CLI

For now, use Python 3.10-3.13. CrewAI's dependency stack currently fails under Python 3.14 in local `uv --with crewai` runs.

```bash
uv python pin 3.13
rm -rf .venv
```

```bash
crewai-flowviz render package.module:MyFlow --out flow.svg
crewai-flowviz render package.module:MyFlow --out flow.png --width 1800 --theme slate
crewai-flowviz render package.module:MyFlow --out flow.png --transparent
crewai-flowviz render package.module:MyFlow --out flow.svg --direction horizontal --height 900
crewai-flowviz studio package.module:MyFlow
```

If the Flow package is not installed, point the importer at it:

```bash
crewai-flowviz render examples.branching_flow:BranchingSupportFlow \
  --pythonpath examples \
  --out artifacts/branching.svg \
  --config examples/config.toml
```

PNG export is available from both the CLI and the studio. Use `--transparent`
or turn off "Export background color" in the studio to leave the SVG/PNG
background transparent.

## Configuration

JSON and TOML config files can contain `[render]` values and `[theme]` overrides. CLI flags override config file values.

```toml
[render]
theme = "mint"
direction = "vertical"
width = 1600
node_width = 300
rank_gap = 140
node_gap = 70
title = "Support Flow"
show_source_refs = true
export_background = false

[theme]
edge_back = "#e11d48"
```

Built-in themes: `crew`, `slate`, `mono`, `mint`.

## Design Notes

- Uses CrewAI's `build_flow_structure()` when available.
- Falls back to private Flow metadata for older CrewAI versions.
- Treats retry router paths as back edges, so forward execution remains readable.
- Does not require Graphviz.
- Static SVG is the canonical renderer. PNG is derived from SVG when `cairosvg` is installed.
