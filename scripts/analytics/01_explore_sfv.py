#!/usr/bin/env python3
"""Разведка структуры еженедельных xlsx-отчётов СФВ (питание на борт).

Для нескольких репрезентативных файлов печатает:
  - имя файла,
  - список листов,
  - для каждого листа: размерность, dtypes, первые 3 строки,
    количество NaN по колонкам.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

DATA_DIR = Path("/home/budnik_an/Obligations/data/sfv_trade_reports/Отчеты по торговому сервису СФВ")


def describe(xlsx: Path) -> None:
    print("=" * 100)
    print(f"FILE: {xlsx.name}")
    print("=" * 100)
    try:
        xls = pd.ExcelFile(xlsx, engine="openpyxl")
    except Exception as exc:  # noqa: BLE001
        print(f"  !! cannot open: {exc}")
        return
    print(f"  Sheets ({len(xls.sheet_names)}): {xls.sheet_names}")
    for sn in xls.sheet_names:
        try:
            df = pd.read_excel(xls, sheet_name=sn, header=None, nrows=20)
        except Exception as exc:  # noqa: BLE001
            print(f"   - sheet {sn!r}: read error {exc}")
            continue
        print("-" * 80)
        print(f"  Sheet: {sn!r}  shape(head)={df.shape}")
        with pd.option_context("display.max_columns", None,
                               "display.width", 220,
                               "display.max_colwidth", 40):
            print(df.head(15).to_string(index=True, header=False))


def main() -> int:
    files = sorted(DATA_DIR.glob("*.xlsx"))
    if not files:
        print(f"Нет файлов в {DATA_DIR}")
        return 1
    print(f"Найдено файлов: {len(files)}")
    sample = [files[0], files[len(files) // 2], files[-1]]
    for f in sample:
        describe(f)
    return 0


if __name__ == "__main__":
    sys.exit(main())
