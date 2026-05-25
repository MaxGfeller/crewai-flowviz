"""Config file loading for render settings."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from crewai_flowviz.models import RenderConfig


def load_config(path: str | Path | None) -> tuple[RenderConfig, dict[str, Any]]:
    if path is None:
        return RenderConfig(), {}

    file_path = Path(path)
    raw = file_path.read_text(encoding="utf-8")
    suffix = file_path.suffix.lower()
    if suffix == ".json":
        values = json.loads(raw)
    elif suffix == ".toml":
        import tomllib

        values = tomllib.loads(raw)
    else:
        raise ValueError("config files must be .json or .toml")

    if not isinstance(values, dict):
        raise ValueError("config root must be an object")

    render_values = values.get("render", values)
    if not isinstance(render_values, dict):
        raise ValueError("render config must be an object")
    theme_values = values.get("theme", {})
    if theme_values is None:
        theme_values = {}
    if not isinstance(theme_values, dict):
        raise ValueError("theme config must be an object")

    return RenderConfig().merged(render_values), theme_values
