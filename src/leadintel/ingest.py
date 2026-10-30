"""Load seed CSVs -> raw_companies."""

from __future__ import annotations

import duckdb


def run(conn: duckdb.DuckDBPyConnection, **kwargs) -> str:
    """Stage entry point. Returns a one-line summary."""
    return "not implemented yet"
