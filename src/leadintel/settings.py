"""Project paths and YAML config loading."""

from __future__ import annotations

import os
from functools import cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(os.environ.get("LEADINTEL_ROOT", Path(__file__).resolve().parents[2]))
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
SEEDS_DIR = DATA_DIR / "seeds"
CACHE_DIR = DATA_DIR / "cache" / "html"
DB_PATH = Path(os.environ.get("LEADINTEL_DB", DATA_DIR / "leadintel.duckdb"))
EXPORTS_DIR = ROOT / "exports"


@cache
def load_config(name: str) -> dict[str, Any]:
    """Load config/<name>.yaml as a dict."""
    with open(CONFIG_DIR / f"{name}.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}
