#!/usr/bin/env python3
"""Готовит JSON-агрегаты для интерактивного дашборда СФВ.

Собирает 4 секции:
  - overview: KPI + weekly timeseries + month×dow heatmap
  - sku:      per-SKU метрики (33 SKU) + категории
  - flights:  per-flight метрики, top/bottom Z-score, SKU×flight heatmap
  - patterns: dow, month, SKU lifecycle, missing_days
  - meta:     period, missing_days, etl summary

Выход:  data/sfv_processed/dashboard_payload.json (одним файлом)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "sfv_processed"
OUT_FILE = PROC / "dashboard_payload.json"


def to_jsonable(obj):
    if isinstance(obj, (pd.Timestamp,)):
        return obj.isoformat()
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        f = float(obj)
        if np.isnan(f):
            return None
        return f
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, dict):
        return {k: to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_jsonable(x) for x in obj]
    return obj


def df_to_records(df: pd.DataFrame) -> list[dict]:
    return [to_jsonable(rec) for rec in df.to_dict(orient="records")]


def main() -> int:
    ships = pd.read_parquet(PROC / "shipments.parquet")
    items = pd.read_parquet(PROC / "items.parquet")

    # ---- Item names: возьмём самое частое название для каждого SKU как display ----
    sku_names = (items.dropna(subset=["item_sku"])
                       .groupby("item_sku")["item_name"]
                       .agg(lambda s: s.value_counts().index[0])
                       .to_dict())

    # =================== overview ===================
    period_start = ships["shipment_date"].min()
    period_end = ships["shipment_date"].max()
    days_total = (period_end - period_start).days + 1
    present_days = ships["shipment_date"].dt.normalize().nunique()
    missing_days_n = days_total - present_days
    total_loaded = int(items["loaded_qty"].fillna(0).sum())
    total_sold = int(items["sold_qty"].fillna(0).sum())
    total_returned = int(items["returned_qty"].fillna(0).sum())
    total_revenue = float(items["revenue"].fillna(0).sum())

    kpis = {
        "files": int(items["source_file"].nunique()),
        "shipments": int(len(ships)),
        "items": int(len(items)),
        "period_start": period_start.strftime("%Y-%m-%d"),
        "period_end": period_end.strftime("%Y-%m-%d"),
        "days_total": int(days_total),
        "days_present": int(present_days),
        "missing_days": int(missing_days_n),
        "coverage_pct": round(present_days / days_total * 100, 2),
        "total_revenue": total_revenue,
        "total_loaded": total_loaded,
        "total_sold": total_sold,
        "total_returned": total_returned,
        "sell_through_pct": round(total_sold / total_loaded * 100, 2) if total_loaded else 0.0,
        "return_pct": round(total_returned / total_loaded * 100, 2) if total_loaded else 0.0,
        "unique_flights": int(ships["flight_out"].nunique()),
        "unique_sku": int(items["item_sku"].nunique()),
        "categories": int(items["item_category"].nunique()),
    }

    # ---- weekly timeseries (по неделе ISO) ----
    s_week = ships.copy()
    s_week["week"] = s_week["shipment_date"].dt.to_period("W-SUN")
    weekly_ships = (s_week.groupby("week")
                          .agg(ships=("shipment_id", "size"),
                               loaded=("loaded_total", "sum"),
                               sold=("sold_total", "sum"),
                               revenue=("revenue_total", "sum"),
                               returned=("returned_total", "sum"))
                          .reset_index())
    weekly_ships["week_start"] = weekly_ships["week"].dt.start_time.dt.strftime("%Y-%m-%d")
    weekly_ships["week_end"] = weekly_ships["week"].dt.end_time.dt.strftime("%Y-%m-%d")
    weekly_ships["sell_through"] = weekly_ships["sold"] / weekly_ships["loaded"].replace({0: np.nan})
    weekly_ships["return_pct"] = weekly_ships["returned"] / weekly_ships["loaded"].replace({0: np.nan}) * 100
    weekly_ships = weekly_ships.drop(columns=["week"])

    # ---- month × dow heatmap (avg revenue per ship) ----
    pivot = (ships.assign(month=ships["shipment_date"].dt.to_period("M").astype(str))
                   .groupby(["month", "dow"])["revenue_total"].mean()
                   .unstack(fill_value=None))
    months_sorted = sorted(pivot.index.tolist())
    dow_sorted = list(range(7))
    z = []
    for m in months_sorted:
        row = []
        for d in dow_sorted:
            v = pivot.loc[m].get(d) if d in pivot.columns else None
            row.append(None if v is None or pd.isna(v) else round(float(v), 1))
        z.append(row)
    heatmap = {
        "x": ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"],
        "y": months_sorted,
        "z": z,
    }

    overview = {
        "kpis": kpis,
        "weekly": df_to_records(weekly_ships),
        "month_dow_heatmap": heatmap,
    }

    # =================== sku ===================
    sku = (items.dropna(subset=["item_sku"])
                .groupby(["item_sku", "item_category"], as_index=False)
                .agg(loadings=("loaded_qty", "size"),
                     loaded=("loaded_qty", "sum"),
                     sold=("sold_qty", "sum"),
                     returned=("returned_qty", "sum"),
                     revenue=("revenue", "sum"),
                     avg_loaded=("loaded_qty", "mean"),
                     avg_sold=("sold_qty", "mean"),
                     avg_price=("price", "mean"),
                     med_return_pct=("return_pct", "median"),
                     avg_return_pct=("return_pct", "mean")))
    sku["sell_through"] = (sku["sold"] / sku["loaded"].replace({0: np.nan})).round(4)
    sku["soldout_share"] = (
        items.dropna(subset=["item_sku"])
             .assign(so=items["sold_qty"].fillna(0) >= items["loaded_qty"].fillna(0))
             .groupby("item_sku")["so"].mean()
             .reindex(sku["item_sku"]).values
    )
    sku["item_name"] = sku["item_sku"].map(sku_names)
    sku = sku.sort_values("revenue", ascending=False)

    # category roll-up
    cat = (items.groupby("item_category", as_index=False)
                 .agg(loaded=("loaded_qty", "sum"),
                      sold=("sold_qty", "sum"),
                      revenue=("revenue", "sum"),
                      returned=("returned_qty", "sum"),
                      rows=("item_name", "size")))
    cat["sell_through"] = (cat["sold"] / cat["loaded"].replace({0: np.nan})).round(4)
    cat["return_pct"] = (cat["returned"] / cat["loaded"].replace({0: np.nan}) * 100).round(2)
    cat = cat.sort_values("revenue", ascending=False)

    sku_section = {
        "rows": df_to_records(sku),
        "categories": df_to_records(cat),
    }

    # =================== flights ===================
    flt = (ships.dropna(subset=["flight_out"])
                .groupby("flight_out", as_index=False)
                .agg(n=("shipment_id", "size"),
                     avg_loaded=("loaded_total", "mean"),
                     avg_sold=("sold_total", "mean"),
                     avg_return=("return_pct_total", "mean"),
                     avg_revenue=("revenue_total", "mean"),
                     total_revenue=("revenue_total", "sum")))
    flt["sell_through"] = flt["avg_sold"] / flt["avg_loaded"].replace({0: np.nan})
    flt_strong = flt[flt["n"] >= 20].copy()
    if not flt_strong.empty:
        st = flt_strong["sell_through"]
        flt_strong["z_st"] = (st - st.mean()) / st.std(ddof=0)
    flt_strong = flt_strong.sort_values("z_st")
    flights_section = {
        "rows": df_to_records(flt_strong),
        "n_total": int(flt["flight_out"].nunique()),
        "n_observed_min20": int(len(flt_strong)),
    }

    # SKU × flight heatmap (sell-through) для топ-15 рейсов × топ-15 SKU
    top_flights = flt_strong.sort_values("total_revenue", ascending=False).head(15)["flight_out"].tolist()
    top_skus = sku.head(15)["item_sku"].tolist()
    sub = items[items["flight_out"].isin(top_flights) & items["item_sku"].isin(top_skus)]
    pv = (sub.groupby(["flight_out", "item_sku"])
              .apply(lambda g: g["sold_qty"].sum() / g["loaded_qty"].sum()
                     if g["loaded_qty"].sum() else None, include_groups=False)
              .unstack())
    z2 = []
    for f in top_flights:
        row = []
        for s in top_skus:
            v = pv.loc[f].get(s) if (f in pv.index and s in pv.columns) else None
            row.append(None if v is None or pd.isna(v) else round(float(v), 4))
        z2.append(row)
    flights_section["sku_heatmap"] = {
        "x": [f"{s} ({sku_names.get(s, '')[:25]})" for s in top_skus],
        "y": [str(int(f)) for f in top_flights],
        "z": z2,
    }

    # =================== patterns ===================
    dow_names = {0: "Пн", 1: "Вт", 2: "Ср", 3: "Чт", 4: "Пт", 5: "Сб", 6: "Вс"}
    dow = (ships.groupby("dow", as_index=False)
                 .agg(n=("shipment_id", "size"),
                      avg_loaded=("loaded_total", "mean"),
                      avg_sold=("sold_total", "mean"),
                      avg_return=("return_pct_total", "mean"),
                      avg_revenue=("revenue_total", "mean")))
    dow["dow_name"] = dow["dow"].map(dow_names)

    mon = (ships.groupby("month", as_index=False)
                 .agg(n=("shipment_id", "size"),
                      avg_loaded=("loaded_total", "mean"),
                      avg_sold=("sold_total", "mean"),
                      avg_return=("return_pct_total", "mean"),
                      avg_revenue=("revenue_total", "mean"),
                      sum_revenue=("revenue_total", "sum")))
    mon = mon.sort_values("month")

    # SKU lifecycle (первая и последняя неделя присутствия)
    lc = (items.dropna(subset=["item_sku"])
                .groupby("item_sku")
                .agg(first_seen=("shipment_date", "min"),
                     last_seen=("shipment_date", "max"),
                     loadings=("loaded_qty", "size"),
                     revenue=("revenue", "sum"))
                .reset_index())
    lc["first_seen"] = lc["first_seen"].dt.strftime("%Y-%m-%d")
    lc["last_seen"] = lc["last_seen"].dt.strftime("%Y-%m-%d")
    lc["item_name"] = lc["item_sku"].map(sku_names)
    lc = lc.sort_values("first_seen")

    # missing days groups
    days_set = set(ships["shipment_date"].dt.date.unique())
    all_days = pd.date_range(period_start, period_end, freq="D").date
    missing = sorted(d for d in all_days if d not in days_set)
    missing_groups = []
    if missing:
        a = b = missing[0]
        for d in missing[1:]:
            if (d - b).days == 1:
                b = d
            else:
                missing_groups.append({"start": str(a), "end": str(b),
                                        "days": (b - a).days + 1})
                a = b = d
        missing_groups.append({"start": str(a), "end": str(b), "days": (b - a).days + 1})

    patterns_section = {
        "dow": df_to_records(dow),
        "monthly": df_to_records(mon),
        "sku_lifecycle": df_to_records(lc),
        "missing_groups": missing_groups,
    }

    payload = {
        "generated_at": pd.Timestamp.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "overview": overview,
        "sku": sku_section,
        "flights": flights_section,
        "patterns": patterns_section,
    }

    OUT_FILE.write_text(json.dumps(to_jsonable(payload), ensure_ascii=False), encoding="utf-8")
    print(f"[OK] payload -> {OUT_FILE}  ({OUT_FILE.stat().st_size/1024:.1f} KB)")
    print(f"  overview.kpis = {payload['overview']['kpis']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
