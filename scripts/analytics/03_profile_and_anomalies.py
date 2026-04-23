#!/usr/bin/env python3
"""Профиль и поиск аномалий в загрузке/продажах СФВ.

Вход:  data/sfv_processed/{shipments,items}.parquet
Выход: data/sfv_processed/profile/*.csv  +  печать сводки

Что считаем:
  A. Профиль: rows, period coverage, distinct flights/SKU, дыры в датах.
  B. Дефицит (sold-out / undersupply): sell_through == 1.0 при стабильном спросе.
  C. Перетарка (overstock / dead stock): sell_through < 0.2 при стабильной загрузке.
  D. Возвратные хиты по SKU (медианный return_pct).
  E. Аномалии по рейсам: рейсы с экстремальным sell-through (Z-score).
  F. SKU с нестабильной загрузкой (CV(loaded_qty) > 0.5).
  G. Аномалии по дням недели и месяцам.
  H. Топ-выручка / топ-возвратность.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "sfv_processed"
OUT = PROC / "profile"
OUT.mkdir(parents=True, exist_ok=True)


def hr(title: str) -> None:
    print()
    print("#" * 90)
    print(f"# {title}")
    print("#" * 90)


def main() -> int:
    ships = pd.read_parquet(PROC / "shipments.parquet")
    items = pd.read_parquet(PROC / "items.parquet")
    print(f"shipments: {len(ships):,}   items: {len(items):,}")

    # ---------- A. Профиль ----------
    hr("A. ПРОФИЛЬ ДАННЫХ")
    print(f"Период: {ships['shipment_date'].min().date()}  →  {ships['shipment_date'].max().date()}")
    days = pd.date_range(ships["shipment_date"].min(), ships["shipment_date"].max(), freq="D")
    present = set(ships["shipment_date"].dt.date.unique())
    missing = sorted(d.date() for d in days if d.date() not in present)
    print(f"Уникальных дат с накладными: {ships['shipment_date'].nunique()}  /  всего дней: {len(days)}")
    print(f"Дней БЕЗ накладных (дыры): {len(missing)}")
    if missing:
        print(f"  первые 10: {missing[:10]}")
    print(f"Уникальных № рейсов (raw): {ships['flight_raw'].nunique()}")
    print(f"Уникальных flight_out:     {ships['flight_out'].nunique()}")
    print(f"Уникальных SKU:            {items['item_sku'].nunique()}  (item_name unique: {items['item_name'].nunique()})")
    print(f"Категорий номенклатуры:    {items['item_category'].nunique()}")

    # Распределение по категориям
    cat = (items.groupby("item_category", as_index=False)
                 .agg(rows=("item_name", "size"),
                      loaded=("loaded_qty", "sum"),
                      sold=("sold_qty", "sum"),
                      revenue=("revenue", "sum"),
                      ret=("returned_qty", "sum")))
    cat["sell_through"] = cat["sold"] / cat["loaded"].replace({0: np.nan})
    cat = cat.sort_values("revenue", ascending=False)
    print("\nКатегории (по выручке):")
    print(cat.to_string(index=False))
    cat.to_csv(OUT / "A_categories.csv", index=False)

    # ---------- B. Дефицит ----------
    hr("B. ДЕФИЦИТ (sell_through == 100%)")
    sold_out = items[(items["loaded_qty"].fillna(0) > 0) &
                     (items["sold_qty"].fillna(0) >= items["loaded_qty"].fillna(0))]
    rate_per_sku = (items
                    .assign(soldout=items["sold_qty"].fillna(0) >= items["loaded_qty"].fillna(0))
                    .groupby(["item_sku", "item_category"], as_index=False)
                    .agg(loadings=("loaded_qty", "size"),
                         soldout_rate=("soldout", "mean"),
                         avg_loaded=("loaded_qty", "mean"),
                         avg_sold=("sold_qty", "mean"),
                         total_loaded=("loaded_qty", "sum"),
                         total_sold=("sold_qty", "sum"),
                         revenue=("revenue", "sum")))
    rate_per_sku = rate_per_sku[rate_per_sku["loadings"] >= 50]
    top_def = rate_per_sku.sort_values(["soldout_rate", "revenue"], ascending=[False, False]).head(25)
    print(f"Случаев полной распродажи (sold_qty >= loaded_qty): {len(sold_out):,}  ({len(sold_out)/len(items):.1%})")
    print("\nТоп-25 SKU по доле случаев распродажи (загрузок ≥ 50):")
    print(top_def.to_string(index=False))
    top_def.to_csv(OUT / "B_top_soldout_sku.csv", index=False)

    # ---------- C. Перетарка ----------
    hr("C. ПЕРЕТАРКА (sell_through < 20% при стабильной загрузке)")
    items_st = items.copy()
    items_st["st"] = items_st.apply(
        lambda r: r["sold_qty"] / r["loaded_qty"] if r["loaded_qty"] else np.nan, axis=1)
    over = (items_st.groupby(["item_sku", "item_category"], as_index=False)
                    .agg(loadings=("loaded_qty", "size"),
                         avg_st=("st", "mean"),
                         med_st=("st", "median"),
                         avg_loaded=("loaded_qty", "mean"),
                         total_loaded=("loaded_qty", "sum"),
                         total_unsold=("unsold_qty", "sum")))
    over = over[over["loadings"] >= 100]
    over = over[over["avg_st"] < 0.20].sort_values("total_unsold", ascending=False).head(25)
    print(f"SKU с медианным sell_through < 20% (≥100 загрузок): {len(over)}")
    print(over.to_string(index=False))
    over.to_csv(OUT / "C_overstock_sku.csv", index=False)

    # ---------- D. Возвратность ----------
    hr("D. ВОЗВРАТНОСТЬ ПО SKU")
    ret_sku = (items.groupby(["item_sku", "item_category"], as_index=False)
                    .agg(loadings=("loaded_qty", "size"),
                         med_return_pct=("return_pct", "median"),
                         avg_return_pct=("return_pct", "mean"),
                         total_returned=("returned_qty", "sum"),
                         total_loaded=("loaded_qty", "sum"),
                         revenue=("revenue", "sum")))
    ret_sku = ret_sku[ret_sku["loadings"] >= 50]
    ret_sku = ret_sku.sort_values("med_return_pct", ascending=False).head(25)
    print("Топ-25 SKU по медианному % возврата (≥50 загрузок):")
    print(ret_sku.to_string(index=False))
    ret_sku.to_csv(OUT / "D_return_top.csv", index=False)

    # ---------- E. Аномалии по рейсам ----------
    hr("E. АНОМАЛИИ ПО РЕЙСАМ (flight_out)")
    flt = (ships.groupby("flight_out", as_index=False)
                 .agg(n=("shipment_id", "size"),
                      avg_loaded=("loaded_total", "mean"),
                      avg_sold=("sold_total", "mean"),
                      avg_return=("return_pct_total", "mean"),
                      avg_revenue=("revenue_total", "mean")))
    flt["sell_through"] = flt["avg_sold"] / flt["avg_loaded"].replace({0: np.nan})
    flt = flt[flt["n"] >= 20]
    flt["z_st"] = (flt["sell_through"] - flt["sell_through"].mean()) / flt["sell_through"].std(ddof=0)
    flt = flt.sort_values("z_st")
    print("Самые СЛАБЫЕ рейсы (низкий sell_through, ≥20 наблюдений):")
    print(flt.head(15).to_string(index=False))
    print("\nСамые СИЛЬНЫЕ рейсы (высокий sell_through):")
    print(flt.tail(15).to_string(index=False))
    flt.to_csv(OUT / "E_flights_sell_through.csv", index=False)

    # ---------- F. Нестабильная загрузка ----------
    hr("F. SKU С НЕСТАБИЛЬНОЙ ЗАГРУЗКОЙ (CV(loaded_qty) > 0.5)")
    cv = (items.groupby(["item_sku", "item_category"], as_index=False)
                .agg(loadings=("loaded_qty", "size"),
                     avg_loaded=("loaded_qty", "mean"),
                     std_loaded=("loaded_qty", "std")))
    cv["cv"] = cv["std_loaded"] / cv["avg_loaded"].replace({0: np.nan})
    cv = cv[cv["loadings"] >= 100]
    cv_top = cv.sort_values("cv", ascending=False).head(25)
    print(cv_top.to_string(index=False))
    cv_top.to_csv(OUT / "F_unstable_loading.csv", index=False)

    # ---------- G. По дням недели ----------
    hr("G. СЕЗОННОСТЬ — ДЕНЬ НЕДЕЛИ / МЕСЯЦ")
    dow_names = {0: "Пн", 1: "Вт", 2: "Ср", 3: "Чт", 4: "Пт", 5: "Сб", 6: "Вс"}
    dow = (ships.groupby("dow", as_index=False)
                 .agg(n=("shipment_id", "size"),
                      avg_loaded=("loaded_total", "mean"),
                      avg_sold=("sold_total", "mean"),
                      avg_return=("return_pct_total", "mean"),
                      avg_revenue=("revenue_total", "mean")))
    dow["dow_name"] = dow["dow"].map(dow_names)
    print(dow.to_string(index=False))
    dow.to_csv(OUT / "G_by_dow.csv", index=False)

    mon = (ships.groupby("month", as_index=False)
                 .agg(n=("shipment_id", "size"),
                      avg_loaded=("loaded_total", "mean"),
                      avg_sold=("sold_total", "mean"),
                      avg_return=("return_pct_total", "mean"),
                      avg_revenue=("revenue_total", "mean")))
    print("\nПомесячно:")
    print(mon.to_string(index=False))
    mon.to_csv(OUT / "G_by_month.csv", index=False)

    # ---------- H. Топ-выручка ----------
    hr("H. ТОП-SKU ПО ВЫРУЧКЕ")
    top_rev = (items.groupby(["item_sku", "item_category"], as_index=False)
                    .agg(revenue=("revenue", "sum"),
                         loaded=("loaded_qty", "sum"),
                         sold=("sold_qty", "sum"),
                         price_avg=("price", "mean")))
    top_rev["sell_through"] = top_rev["sold"] / top_rev["loaded"].replace({0: np.nan})
    top_rev = top_rev.sort_values("revenue", ascending=False).head(20)
    print(top_rev.to_string(index=False))
    top_rev.to_csv(OUT / "H_top_revenue.csv", index=False)

    # ---------- Метаотчёт ----------
    summary = {
        "shipments": int(len(ships)),
        "items": int(len(items)),
        "period_start": str(ships["shipment_date"].min().date()),
        "period_end": str(ships["shipment_date"].max().date()),
        "missing_days": len(missing),
        "missing_days_sample": [str(d) for d in missing[:20]],
        "unique_flight_out": int(ships["flight_out"].nunique()),
        "unique_sku": int(items["item_sku"].nunique()),
        "categories": int(items["item_category"].nunique()),
        "total_revenue": float(items["revenue"].fillna(0).sum()),
        "total_loaded": int(items["loaded_qty"].fillna(0).sum()),
        "total_sold": int(items["sold_qty"].fillna(0).sum()),
        "total_returned": int(items["returned_qty"].fillna(0).sum()),
    }
    summary["overall_sell_through"] = summary["total_sold"] / summary["total_loaded"]
    summary["overall_return_pct"] = summary["total_returned"] / summary["total_loaded"] * 100
    (OUT / "_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    hr("СВОДКА")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
