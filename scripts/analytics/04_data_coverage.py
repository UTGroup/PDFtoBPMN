#!/usr/bin/env python3
"""Аудит непрерывности потока данных по 66 недельным xlsx-отчётам СФВ.

Что проверяем:
  1. Объявленные периоды каждого файла (из шапки) — последовательность недель.
  2. Перекрытия и пропуски между периодами файлов.
  3. Внутри каждого периода — все ли календарные дни присутствуют в накладных.
  4. Дни без накладных по всему dataset.

Выход:
  - data/sfv_processed/coverage/files_periods.csv
  - data/sfv_processed/coverage/week_gaps.csv
  - data/sfv_processed/coverage/missing_days.csv
  - печать отчёта
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "sfv_processed"
OUT = PROC / "coverage"
OUT.mkdir(parents=True, exist_ok=True)


def main() -> int:
    report = json.loads((PROC / "_etl_report.json").read_text(encoding="utf-8"))
    files = report["files"]
    df = pd.DataFrame(files)
    df["period_start"] = pd.to_datetime(df["period_start"])
    df["period_end"] = pd.to_datetime(df["period_end"])
    df["span_days"] = (df["period_end"] - df["period_start"]).dt.days + 1
    df = df.sort_values(["period_start", "period_end"]).reset_index(drop=True)

    print("=" * 90)
    print(f"ВСЕГО ФАЙЛОВ: {len(df)}")
    print(f"Период объявленный (по шапкам): {df['period_start'].min().date()}  →  {df['period_end'].max().date()}")
    print(f"Файлов с span != 7 дней: {int((df['span_days'] != 7).sum())}")
    weird_span = df[df["span_days"] != 7][["file", "period_start", "period_end", "span_days", "shipments"]]
    if not weird_span.empty:
        print(weird_span.to_string(index=False))

    df.to_csv(OUT / "files_periods.csv", index=False, date_format="%Y-%m-%d")

    # ------- Перекрытия и пропуски между объявленными периодами -------
    print("\n" + "=" * 90)
    print("СТЫКИ МЕЖДУ ФАЙЛАМИ (по объявленным периодам):")
    gaps_rows = []
    for i in range(1, len(df)):
        prev = df.iloc[i - 1]
        cur = df.iloc[i]
        expected_start = prev["period_end"] + pd.Timedelta(days=1)
        delta = (cur["period_start"] - expected_start).days
        kind = "OK"
        if delta > 0:
            kind = f"GAP +{delta}d"
        elif delta < 0:
            kind = f"OVERLAP {delta}d"
        gaps_rows.append({
            "i": i,
            "prev_file": prev["file"],
            "prev_end": prev["period_end"].date(),
            "cur_file": cur["file"],
            "cur_start": cur["period_start"].date(),
            "delta_days": delta,
            "kind": kind,
        })
    gaps = pd.DataFrame(gaps_rows)
    gaps.to_csv(OUT / "week_gaps.csv", index=False)
    bad = gaps[gaps["kind"] != "OK"]
    if bad.empty:
        print("  Все стыки идеальны: ни одного пропуска и перекрытия по периодам в шапках.")
    else:
        print(bad.to_string(index=False))

    # ------- Внутри каждого периода: какие дни не имеют ни одной накладной -------
    print("\n" + "=" * 90)
    print("ПРОПУСКИ КАЛЕНДАРНЫХ ДНЕЙ ВНУТРИ ПЕРИОДОВ ФАЙЛОВ:")
    ships = pd.read_parquet(PROC / "shipments.parquet")
    ships["d"] = ships["shipment_date"].dt.date
    by_file = ships.groupby("source_file")["d"].apply(lambda s: set(s)).to_dict()

    rows_missing = []
    no_data_files = []
    for _, r in df.iterrows():
        days_decl = pd.date_range(r["period_start"], r["period_end"], freq="D").date
        present = by_file.get(r["file"], set())
        missing = [d for d in days_decl if d not in present]
        if missing:
            rows_missing.append({
                "file": r["file"],
                "period_start": r["period_start"].date(),
                "period_end": r["period_end"].date(),
                "missing_count": len(missing),
                "missing_days": ",".join(str(x) for x in missing),
            })
        if not present:
            no_data_files.append(r["file"])

    miss_df = pd.DataFrame(rows_missing)
    miss_df.to_csv(OUT / "missing_days_in_periods.csv", index=False)
    if rows_missing:
        print(f"Файлов с дырами внутри периода: {len(rows_missing)}")
        print(miss_df.to_string(index=False))
    else:
        print("  В каждом файле все 7 дней покрыты накладными.")

    # ------- Глобальная карта дней -------
    print("\n" + "=" * 90)
    print("ГЛОБАЛЬНАЯ КАРТА ДНЕЙ:")
    all_days = pd.date_range(df["period_start"].min(), df["period_end"].max(), freq="D").date
    present_global = set()
    for s in by_file.values():
        present_global |= s
    missing_global = sorted(d for d in all_days if d not in present_global)
    print(f"Всего дней в декларируемом окне: {len(all_days)}")
    print(f"Дней БЕЗ накладных:              {len(missing_global)}")
    if missing_global:
        # сгруппировать в непрерывные диапазоны
        ranges = []
        a = b = missing_global[0]
        for d in missing_global[1:]:
            if (d - b).days == 1:
                b = d
            else:
                ranges.append((a, b))
                a = b = d
        ranges.append((a, b))
        for a, b in ranges:
            n = (b - a).days + 1
            print(f"  ▸ {a}  →  {b}  ({n} дн.)")
    pd.DataFrame({"missing_day": missing_global}).to_csv(OUT / "missing_days_global.csv", index=False)

    # ------- Сводка -------
    print("\n" + "=" * 90)
    print("СВОДКА:")
    print(f"  Файлов:           {len(df)}")
    print(f"  Накладных:        {report['totals']['shipments']:,}")
    print(f"  Позиций:          {report['totals']['items']:,}")
    print(f"  Файлов без данных:{len(no_data_files)}")
    print(f"  Дней покрыто:     {len(all_days) - len(missing_global)} / {len(all_days)}  "
          f"({(1 - len(missing_global)/len(all_days)):.1%})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
