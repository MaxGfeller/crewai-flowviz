# crewai-flowviz

Configurable static and interactive diagrams for CrewAI Flows.

It extracts a CrewAI Flow into a stable graph model, then renders SVG/PNG/JSON/DOT from that model. It also includes a local studio for trying themes, orientation, spacing, and dimensions without changing code.

## Installation

For now, use Python 3.10-3.13. CrewAI's dependency stack currently fails under Python 3.14 in local `uv --with crewai` runs.

For a CrewAI project, install it as a dev dependency:

```bash
uv add --dev crewai-flowviz
```

Then run it inside that project environment:

```bash
uv run crewai-flowviz studio package.module:MyFlow
uv run crewai-flowviz render package.module:MyFlow --out artifacts/flow.svg
uv run crewai-flowviz render package.module:MyFlow --out artifacts/flow.png --transparent
```

For a one-off run without adding it to the project:

```bash
uvx --from crewai-flowviz --with-editable . crewai-flowviz studio package.module:MyFlow
```

For an unpackaged `src/` layout:

```bash
uvx --from crewai-flowviz --with crewai crewai-flowviz render \
  package.module:MyFlow \
  --pythonpath src \
  --out artifacts/flow.svg
```

## Local Development

Run the included example:

```bash
PYTHONPATH=src:examples uv run --with crewai python -m crewai_flowviz.cli studio \
  branching_flow:BranchingSupportFlow
```

## CLI

```bash
crewai-flowviz render package.module:MyFlow --out flow.svg
crewai-flowviz render package.module:MyFlow --out flow.png --width 1800 --theme slate
crewai-flowviz render package.module:MyFlow --out flow.png --transparent
crewai-flowviz render package.module:MyFlow --out flow.svg --direction horizontal --height 900
crewai-flowviz studio package.module:MyFlow
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
- Static SVG is the canonical vector renderer. PNG is rendered natively with Pillow.

## Publishing

The package name is `crewai-flowviz`.

```bash
rm -rf dist
uv build
uv publish
```

PyPI versions are immutable, so bump `version` in `pyproject.toml` before each release.
