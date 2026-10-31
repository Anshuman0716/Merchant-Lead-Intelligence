"""Load seed CSVs -> raw_companies."""

from __future__ import annotations

from pathlib import Path

import duckdb
import polars as pl

from leadintel.db import write_table
from leadintel.schemas import RawCompanies
from leadintel.settings import SEEDS_DIR

COLUMNS = [
    "name",
    "url",
    "vertical",
    "sub_category",
    "city",
    "source",
    "funding_stage",
    "last_funding_date",
]


def load_seeds(seeds_dir: Path = SEEDS_DIR) -> pl.DataFrame:
    frames = []
    for path in sorted(seeds_dir.glob("*.csv")):
        df = pl.read_csv(path, infer_schema=False)  # read all as strings; schema coerces
        missing = set(COLUMNS) - set(df.columns)
        if missing:
            raise ValueError(f"{path.name} is missing columns: {sorted(missing)}")
        frames.append(df.select(COLUMNS).with_columns(source_file=pl.lit(path.name)))
    if not frames:
        raise FileNotFoundError(f"No seed CSVs found in {seeds_dir}")

    df = pl.concat(frames)
    # Trim whitespace and turn empty strings into nulls
    df = df.with_columns(
        [pl.col(c).str.strip_chars().replace("", None) for c in COLUMNS]
    ).with_columns(
        vertical=pl.col("vertical").str.to_lowercase(),
        last_funding_date=pl.col("last_funding_date").str.to_date("%Y-%m-%d", strict=False),
    )
    return RawCompanies.validate(df)


def run(conn: duckdb.DuckDBPyConnection, **kwargs) -> str:
    df = load_seeds()
    write_table(df, "raw_companies", conn)
    counts = df.group_by("vertical").len().sort("vertical")
    by_vertical = ", ".join(f"{v}={n}" for v, n in counts.iter_rows())
    return f"raw_companies: {df.height} rows ({by_vertical})"
