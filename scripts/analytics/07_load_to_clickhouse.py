#!/usr/bin/env python3
"""Идемпотентная заливка СФВ-данных в ClickHouse: одна плоская таблица.

Подключение берётся из .env (CLICKHOUSE_*).
БД и таблица:  sfv.catering_items  (DROP + CREATE + bulk INSERT).

Источник данных:
  - data/sfv_processed/items.parquet     (детализация по позициям)
  - data/sfv_processed/shipments.parquet (агрегаты по накладной — джойнятся)
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pandas as pd
from clickhouse_driver import Client

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "sfv_processed"
ENV = ROOT / ".env"

DB_NAME = "sfv"
TABLE_NAME = "catering_items"

DDL = f"""
CREATE TABLE IF NOT EXISTS {DB_NAME}.{TABLE_NAME}
(
    -- идентификация накладной
    shipment_id           Int32,
    shipment_date         Date,
    flight_raw            LowCardinality(String),
    flight_out            Nullable(Int32),
    flight_ret            Nullable(Int32),

    -- агрегаты по накладной (продублированы в каждой позиции — для удобства фильтров)
    ship_loaded_total     Nullable(Int32),
    ship_sold_total       Nullable(Int32),
    ship_revenue_total    Nullable(Float64),
    ship_returned_total   Nullable(Int32),
    ship_return_pct_total Nullable(Float32),

    -- позиция номенклатуры
    item_name             String,
    item_sku              LowCardinality(String),    -- '' если не извлечён из имени
    item_category         LowCardinality(String),
    vat_rate_pct          Nullable(Float32),
    loaded_qty            Nullable(Int32),
    sold_qty              Nullable(Int32),
    price                 Nullable(Float32),
    revenue               Nullable(Float64),
    returned_qty          Nullable(Int32),
    return_pct            Nullable(Float32),
    unsold_qty            Nullable(Int32),
    sell_through          Nullable(Float32),

    -- метаданные периода/источника
    period_start          Date,
    period_end            Date,
    source_file           LowCardinality(String),

    -- производные временные
    dow                   UInt8,
    month                 LowCardinality(String),
    year                  UInt16,

    inserted_at           DateTime DEFAULT now()
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(shipment_date)
ORDER BY (shipment_date, shipment_id, item_sku)
SETTINGS index_granularity = 8192
"""

INSERT_COLS = [
    "shipment_id", "shipment_date", "flight_raw", "flight_out", "flight_ret",
    "ship_loaded_total", "ship_sold_total", "ship_revenue_total",
    "ship_returned_total", "ship_return_pct_total",
    "item_name", "item_sku", "item_category", "vat_rate_pct",
    "loaded_qty", "sold_qty", "price", "revenue",
    "returned_qty", "return_pct", "unsold_qty", "sell_through",
    "period_start", "period_end", "source_file",
    "dow", "month", "year",
]


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for raw in ENV.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()
    return env


def prepare_df() -> pd.DataFrame:
    items = pd.read_parquet(PROC / "items.parquet")
    ships = pd.read_parquet(PROC / "shipments.parquet")[
        ["shipment_id", "shipment_date",
         "loaded_total", "sold_total", "revenue_total",
         "returned_total", "return_pct_total"]
    ].rename(columns={
        "loaded_total":     "ship_loaded_total",
        "sold_total":       "ship_sold_total",
        "revenue_total":    "ship_revenue_total",
        "returned_total":   "ship_returned_total",
        "return_pct_total": "ship_return_pct_total",
    })
    df = items.merge(ships, on=["shipment_id", "shipment_date"], how="left")

    # Типизация под CH
    int32_cols = ["shipment_id", "flight_out", "flight_ret",
                  "ship_loaded_total", "ship_sold_total", "ship_returned_total",
                  "loaded_qty", "sold_qty", "returned_qty", "unsold_qty"]
    for c in int32_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")

    f32 = ["ship_return_pct_total", "vat_rate_pct", "price",
           "return_pct", "sell_through"]
    for c in f32:
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("Float64")

    f64 = ["ship_revenue_total", "revenue"]
    for c in f64:
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("Float64")

    df["dow"] = df["dow"].fillna(0).astype("uint8")
    df["year"] = df["year"].fillna(0).astype("uint16")
    df["month"] = df["month"].astype(str)
    df["flight_raw"] = df["flight_raw"].fillna("").astype(str)
    df["item_name"] = df["item_name"].fillna("").astype(str)
    df["item_sku"] = df["item_sku"].fillna("").astype(str)
    df["item_category"] = df["item_category"].fillna("").astype(str)
    df["source_file"] = df["source_file"].fillna("").astype(str)

    # Даты
    for c in ["shipment_date", "period_start", "period_end"]:
        df[c] = pd.to_datetime(df[c]).dt.date

    return df[INSERT_COLS]


def df_to_records(df: pd.DataFrame) -> list[tuple]:
    """Конвертирует df в список tuple, заменяя NaN/NaT на None."""
    out = []
    for row in df.itertuples(index=False, name=None):
        new = []
        for v in row:
            if v is None:
                new.append(None)
            elif isinstance(v, float) and pd.isna(v):
                new.append(None)
            elif pd.isna(v):
                new.append(None)
            elif hasattr(v, "item"):
                new.append(v.item())
            else:
                new.append(v)
        out.append(tuple(new))
    return out


def main() -> int:
    env = load_env()
    host = env["CLICKHOUSE_HOST"]
    port = int(env.get("CLICKHOUSE_PORT", 9000))
    user = env["CLICKHOUSE_USER"]
    pwd = env["CLICKHOUSE_PASSWORD"]

    print(f"[i] Connect {host}:{port} as {user}")
    cli = Client(host=host, port=port, user=user, password=pwd,
                 connect_timeout=10, send_receive_timeout=120,
                 settings={"input_format_null_as_default": 0})

    print(f"[i] CREATE DATABASE IF NOT EXISTS {DB_NAME}")
    cli.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")

    print(f"[i] DROP TABLE IF EXISTS {DB_NAME}.{TABLE_NAME}")
    cli.execute(f"DROP TABLE IF EXISTS {DB_NAME}.{TABLE_NAME}")

    print(f"[i] CREATE TABLE {DB_NAME}.{TABLE_NAME}")
    cli.execute(DDL)

    print("[i] Prepare dataframe ...")
    t0 = time.time()
    df = prepare_df()
    print(f"    rows={len(df):,}  cols={len(df.columns)}  ({time.time() - t0:.1f}s)")

    print("[i] Convert to records ...")
    t0 = time.time()
    records = df_to_records(df)
    print(f"    {len(records):,} tuples ({time.time() - t0:.1f}s)")

    print("[i] Bulk INSERT ...")
    t0 = time.time()
    cli.execute(
        f"INSERT INTO {DB_NAME}.{TABLE_NAME} ({', '.join(INSERT_COLS)}) VALUES",
        records,
        types_check=True,
    )
    print(f"    inserted in {time.time() - t0:.1f}s")

    # Верификация
    print("\n[i] Verify:")
    cnt = cli.execute(f"SELECT count() FROM {DB_NAME}.{TABLE_NAME}")[0][0]
    print(f"  count           = {cnt:,}  (parquet items: {len(df):,})")
    sums = cli.execute(f"""
        SELECT
            sum(loaded_qty),
            sum(sold_qty),
            sum(returned_qty),
            sum(revenue),
            countDistinct(shipment_id),
            countDistinct(item_sku),
            countDistinct(flight_out),
            min(shipment_date),
            max(shipment_date)
        FROM {DB_NAME}.{TABLE_NAME}
    """)[0]
    print(f"  sum(loaded_qty) = {sums[0]:,}")
    print(f"  sum(sold_qty)   = {sums[1]:,}")
    print(f"  sum(returned)   = {sums[2]:,}")
    print(f"  sum(revenue)    = {sums[3]:,.2f} ₽")
    print(f"  uniq shipments  = {sums[4]:,}")
    print(f"  uniq SKU        = {sums[5]}")
    print(f"  uniq flight_out = {sums[6]}")
    print(f"  date range      = {sums[7]} → {sums[8]}")

    parts = cli.execute(f"""
        SELECT partition, sum(rows), formatReadableSize(sum(bytes_on_disk))
        FROM system.parts
        WHERE database = '{DB_NAME}' AND table = '{TABLE_NAME}' AND active
        GROUP BY partition ORDER BY partition
    """)
    print(f"\n  partitions ({len(parts)}):")
    for p, r, sz in parts[:5]:
        print(f"    {p}  rows={r:>7,}  size={sz}")
    if len(parts) > 5:
        print(f"    ... ({len(parts) - 5} more)")
    total_size = cli.execute(f"""
        SELECT formatReadableSize(sum(bytes_on_disk))
        FROM system.parts WHERE database='{DB_NAME}' AND table='{TABLE_NAME}' AND active
    """)[0][0]
    print(f"  total disk      = {total_size}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
