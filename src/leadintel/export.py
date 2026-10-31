"""Write the app's Parquet file and CRM-ready CSVs -> exports/.

exports/leads.parquet          everything the Streamlit app needs (committed, so the deployed
                               app doesn't need the DuckDB file or the HTML cache)
exports/hubspot_companies.csv  HubSpot company import (custom properties: see README)
exports/leads_tier_A.csv       call list for SDRs
"""

from __future__ import annotations

import duckdb
import polars as pl

from leadintel.db import read_table
from leadintel.openers import GATEWAY_NAMES, LAYER_NAMES
from leadintel.settings import EXPORTS_DIR

# HubSpot's Industry property only accepts its own labels
HUBSPOT_INDUSTRY = {"d2c": "Consumer Goods", "edtech": "E-Learning", "saas": "Computer Software"}
VERTICAL_LABEL = {"d2c": "D2C", "edtech": "Edtech", "saas": "SaaS"}
PLATFORM_LABEL = {"shopify": "Shopify", "woocommerce": "WooCommerce", "magento": "Magento",
                  "custom": "Custom", "unknown": "Unknown"}  # fmt: skip


def build_leads(conn: duckdb.DuckDBPyConnection) -> pl.DataFrame:
    companies = read_table("companies", conn)
    signals = read_table("signals", conn)
    scores = read_table("lead_scores", conn)
    df = scores.join(companies, on="domain", how="left").join(signals, on="domain", how="left")

    return df.with_columns(
        vertical_label=pl.col("vertical").replace_strict(VERTICAL_LABEL, default=None),
        platform_label=pl.col("platform").replace_strict(PLATFORM_LABEL, default="Not crawled"),
        gateway_names=pl.col("gateways_detected")
        .fill_null([])
        .list.eval(pl.element().replace_strict(GATEWAY_NAMES, default=pl.element())),
        checkout_layer_name=pl.col("checkout_layer").replace_strict(LAYER_NAMES, default=None),
        is_funded=pl.col("funding_stage").is_not_null(),
    ).sort(["score", "name"], descending=[True, False])


def hubspot_frame(leads: pl.DataFrame) -> pl.DataFrame:
    join = lambda col: pl.col(col).list.join("; ")  # noqa: E731
    return leads.select(
        pl.col("name").alias("Company name"),
        pl.col("domain").alias("Company Domain Name"),
        pl.col("vertical").replace_strict(HUBSPOT_INDUSTRY).alias("Industry"),
        pl.col("city").alias("City"),
        pl.lit("India").alias("Country/Region"),
        pl.col("vertical_label").alias("Vertical"),
        pl.col("tier").alias("Lead tier"),
        pl.col("score").alias("ICP score"),
        join("gateway_names").alias("Current gateway"),
        pl.col("checkout_layer_name").alias("Checkout layer"),
        join("suggested_products").alias("Suggested products"),
        join("reasons").alias("Top reasons"),
        pl.col("opener").alias("Opener"),
    )


def tier_a_frame(leads: pl.DataFrame) -> pl.DataFrame:
    return leads.filter(pl.col("tier") == "A").select(
        "name", "domain", "vertical_label", "city", "score",
        pl.col("reasons").list.join(" | ").alias("top_reasons"),
        pl.col("suggested_products").list.join("; ").alias("suggested_products"),
        "opener", "contact_email",
    )  # fmt: skip


def run(conn: duckdb.DuckDBPyConnection, **kwargs) -> str:
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    leads = build_leads(conn)
    leads.write_parquet(EXPORTS_DIR / "leads.parquet")
    hubspot_frame(leads).write_csv(EXPORTS_DIR / "hubspot_companies.csv")
    tier_a = tier_a_frame(leads)
    tier_a.write_csv(EXPORTS_DIR / "leads_tier_A.csv")
    return (f"exports: leads.parquet ({leads.height} rows), hubspot_companies.csv, "
            f"leads_tier_A.csv ({tier_a.height} rows)")  # fmt: skip
