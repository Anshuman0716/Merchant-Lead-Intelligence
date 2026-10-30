"""DuckDB helpers. Every stage reads from and writes to one DuckDB file."""

from __future__ import annotations

from pathlib import Path

import duckdb
import polars as pl

from leadintel.settings import DB_PATH


def get_conn(path: Path | str | None = None) -> duckdb.DuckDBPyConnection:
    path = Path(path or DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(path))


def write_table(df: pl.DataFrame, name: str, conn: duckdb.DuckDBPyConnection | None = None) -> int:
    """Replace table `name` with the contents of `df`. Returns row count."""
    own = conn is None
    conn = conn or get_conn()
    try:
        conn.register("_df", df.to_arrow())
        conn.execute(f'CREATE OR REPLACE TABLE "{name}" AS SELECT * FROM _df')
        conn.unregister("_df")
        return df.height
    finally:
        if own:
            conn.close()


def read_table(name: str, conn: duckdb.DuckDBPyConnection | None = None) -> pl.DataFrame:
    own = conn is None
    conn = conn or get_conn()
    try:
        return conn.execute(f'SELECT * FROM "{name}"').pl()
    finally:
        if own:
            conn.close()


def table_exists(name: str, conn: duckdb.DuckDBPyConnection | None = None) -> bool:
    own = conn is None
    conn = conn or get_conn()
    try:
        row = conn.execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_name = ?", [name]
        ).fetchone()
        return bool(row and row[0])
    finally:
        if own:
            conn.close()
