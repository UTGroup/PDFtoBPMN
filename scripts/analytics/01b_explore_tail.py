#!/usr/bin/env python3
"""Доразведка: хвост файла, кол-во строк, шапка целиком, пример блока."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

DATA_DIR = Path("/home/budnik_an/Obligations/data/sfv_trade_reports/Отчеты по торговому сервису СФВ")

SAMPLE_NAMES = [
    "Общие продажи по ТТН С 25.04 ПО 1.05.xlsx",
    "ЮТ общие продажи по ттн с 14 по 20.11.xlsx",
    "ют общие продажи по ттн с 13 по 19 марта.xlsx",
]


def main() -> int:
    for name in SAMPLE_NAMES:
        f = DATA_DIR / name
        if not f.exists():
            print(f"!! not found: {name}")
            continue
        df = pd.read_excel(f, sheet_name=0, header=None, engine="openpyxl")
        print("=" * 90)
        print(f"{name}: shape={df.shape}, sheet0")
        print("--- HEAD 6 ---")
        with pd.option_context("display.max_columns", None,
                               "display.width", 220,
                               "display.max_colwidth", 50):
            print(df.head(6).to_string(index=True, header=False))
        print("--- TAIL 10 ---")
        with pd.option_context("display.max_columns", None,
                               "display.width", 220,
                               "display.max_colwidth", 50):
            print(df.tail(10).to_string(index=True, header=False))
        # подсчёт строк, где col1 (номер накладной) — число
        col1 = pd.to_numeric(df.iloc[:, 1], errors="coerce")
        n_inv = int(col1.notna().sum())
        # подсчёт строк, где col2 (дата) — datetime/число (накладная)
        col2 = df.iloc[:, 2]
        # подсчёт пустых строк
        empties = int(df.isna().all(axis=1).sum())
        print(f"--- Накладных (по col1 numeric): {n_inv}, всего строк: {len(df)}, пустых: {empties}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
