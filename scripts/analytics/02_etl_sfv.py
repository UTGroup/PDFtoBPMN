#!/usr/bin/env python3
"""ETL еженедельных xlsx-отчётов СФВ "Реестр отгрузок по накладным".

Источник: data/sfv_trade_reports/Отчеты по торговому сервису СФВ/*.xlsx
На выходе:
  - data/sfv_processed/shipments.parquet  (одна строка = накладная/рейс/дата)
  - data/sfv_processed/items.parquet      (одна строка = позиция номенклатуры)
  - data/sfv_processed/_etl_report.json   (счётчики по файлам, ошибки)

Структура входного файла (унифицирована, проверена на нескольких файлах):
  row 0 — "Реестр отгрузок по накладным за период"
  row 1 — период вида "DD.MM.YY - DD.MM.YY"
  row 2 — контрагент
  row 3 — заголовки колонок
  row 4..N — данные:
     * "родительская" строка накладной (col[1] = номер накладной),
     * за ней N "детских" строк по номенклатуре (col[2] = название позиции).
  Хвост: блок(и) "ОБЩИЕ ИТОГИ" / "Итого" — пропускаем.

Колонки (0-based):
  1: Номер накладной | (пусто)
  2: Дата накладной  | Номенклатура
  3: № рейса         | (пусто)
  5: ставка НДС
  6: Загружено по накладной
  7: Количество продано
  8: Цена
  9: Итого продано на сумму
 10: Возврат по накладной
 11: % возврата
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "data" / "sfv_trade_reports" / "Отчеты по торговому сервису СФВ"
OUT_DIR = ROOT / "data" / "sfv_processed"

PERIOD_RE = re.compile(r"(\d{2}\.\d{2}\.\d{2,4})\s*[-–]\s*(\d{2}\.\d{2}\.\d{2,4})")
SKU_RE = re.compile(r"-\s*(ТНБн?-[A-Za-zА-Яа-я0-9]+)\s*$", re.IGNORECASE)
FLIGHT_RE = re.compile(r"^(\d{2,5})(?:\s*/\s*(\d{2,5}))?$")

STOP_TOKENS = ("ОБЩИЕ", "Итого", "ИТОГО")


def to_int(v: Any) -> int | None:
    if v is None or pd.isna(v):
        return None
    if isinstance(v, str):
        v = v.strip().replace("\u00a0", "").replace(" ", "")
        if not v:
            return None
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def to_float(v: Any) -> float | None:
    if v is None or pd.isna(v):
        return None
    if isinstance(v, str):
        v = v.strip().replace("\u00a0", "").replace(" ", "").replace(",", ".").replace("%", "")
        if not v:
            return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def to_date(v: Any) -> pd.Timestamp | None:
    if v is None or pd.isna(v):
        return None
    if isinstance(v, pd.Timestamp):
        return v
    s = str(v).strip()
    for fmt in ("%d.%m.%Y", "%d.%m.%y"):
        try:
            return pd.Timestamp(pd.to_datetime(s, format=fmt))
        except (ValueError, TypeError):
            continue
    try:
        return pd.Timestamp(pd.to_datetime(s, dayfirst=True))
    except Exception:  # noqa: BLE001
        return None


def parse_period(cell: Any) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
    if cell is None or pd.isna(cell):
        return None, None
    m = PERIOD_RE.search(str(cell))
    if not m:
        return None, None
    return to_date(m.group(1)), to_date(m.group(2))


def parse_vat(v: Any) -> float | None:
    if v is None or pd.isna(v):
        return None
    s = str(v).strip().replace("%", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def parse_flight(v: Any) -> tuple[str | None, int | None, int | None]:
    if v is None or pd.isna(v):
        return None, None, None
    raw = str(v).strip()
    m = FLIGHT_RE.match(raw)
    if not m:
        return raw, None, None
    out = int(m.group(1))
    ret = int(m.group(2)) if m.group(2) else None
    return raw, out, ret


def parse_item(name: Any) -> tuple[str, str | None]:
    if name is None or pd.isna(name):
        return "", None
    s = str(name).strip()
    m = SKU_RE.search(s)
    if not m:
        return s, None
    sku = m.group(1).upper().replace(" ", "")
    return s, sku


# Категоризация номенклатуры (упрощённо, по ключевым словам в названии)
CATEGORY_RULES = [
    ("Кофе",            ["кофе"]),
    ("Чай",             ["чай"]),
    ("Вода негаз",      ["вода минеральная", "вода негаз"]),
    ("Газировка",       ["добрый ", "берн", "кола", "лимон-лайм", "апельсин газ", "лайм газ", "груша", "ситро", "тархун"]),
    ("Сок",             ["сок"]),
    ("Пиво",            ["пиво", "крушовице"]),
    ("Сэндвич",         ["сэндвич", "ролл с"]),
    ("Горячее блюдо",   ["курица терияки", "нагетсы", "омлет", "фунчеза", "пельмени", "плов", "паста", "лазанья"]),
    ("Снэк",            ["колбаски", "пиколини", "снек", "чипсы", "орехи", "сухарики"]),
    ("Десерт",          ["маффин", "кукис", "печенье", "шоколад", "кекс", "круассан"]),
    ("Сливки/доп",      ["сливки", "сахар", "соль", "перец", "салфетк"]),
]


def classify(name: str) -> str:
    low = name.lower()
    for cat, keys in CATEGORY_RULES:
        if any(k in low for k in keys):
            return cat
    return "Прочее"


@dataclass
class FileStats:
    file: str
    rows_total: int = 0
    shipments: int = 0
    items: int = 0
    period_start: str | None = None
    period_end: str | None = None
    errors: list[str] = field(default_factory=list)


def parse_file(path: Path) -> tuple[list[dict], list[dict], FileStats]:
    stats = FileStats(file=path.name)
    df = pd.read_excel(path, sheet_name=0, header=None, engine="openpyxl")
    stats.rows_total = len(df)
    if len(df) < 5:
        stats.errors.append("too few rows")
        return [], [], stats
    p_start, p_end = parse_period(df.iat[1, 1])
    stats.period_start = str(p_start.date()) if p_start is not None else None
    stats.period_end = str(p_end.date()) if p_end is not None else None

    shipments: list[dict] = []
    items: list[dict] = []
    current: dict | None = None
    in_totals = False

    for i in range(4, len(df)):
        row = df.iloc[i]
        c1, c2, c3 = row.iat[1], row.iat[2], row.iat[3]
        # Пустая строка → пропуск
        if pd.isna(c1) and pd.isna(c2):
            current = None
            continue
        # Хвост (блок "ОБЩИЕ ИТОГИ" / "Итого")
        c2_str = "" if pd.isna(c2) else str(c2)
        if any(tok in c2_str for tok in STOP_TOKENS):
            in_totals = True
            current = None
            continue
        if in_totals:
            continue

        # Родительская строка накладной — col1 numeric
        ship_id = to_int(c1)
        if ship_id is not None and not pd.isna(c2):
            flight_raw, flight_out, flight_ret = parse_flight(c3)
            ship = {
                "shipment_id": ship_id,
                "shipment_date": to_date(c2),
                "flight_raw": flight_raw,
                "flight_out": flight_out,
                "flight_ret": flight_ret,
                "loaded_total": to_int(row.iat[6]),
                "sold_total": to_int(row.iat[7]),
                "revenue_total": to_float(row.iat[9]),
                "returned_total": to_int(row.iat[10]),
                "return_pct_total": to_float(row.iat[11]),
                "period_start": p_start,
                "period_end": p_end,
                "source_file": path.name,
            }
            shipments.append(ship)
            current = ship
            continue

        # Детская строка — col1 пуст, col2 — название номенклатуры
        if current is None:
            continue
        name_raw, sku = parse_item(c2)
        if not name_raw:
            continue
        items.append({
            "shipment_id": current["shipment_id"],
            "shipment_date": current["shipment_date"],
            "flight_raw": current["flight_raw"],
            "flight_out": current["flight_out"],
            "flight_ret": current["flight_ret"],
            "item_name": name_raw,
            "item_sku": sku,
            "item_category": classify(name_raw),
            "vat_rate_pct": parse_vat(row.iat[5]),
            "loaded_qty": to_int(row.iat[6]),
            "sold_qty": to_int(row.iat[7]),
            "price": to_float(row.iat[8]),
            "revenue": to_float(row.iat[9]),
            "returned_qty": to_int(row.iat[10]),
            "return_pct": to_float(row.iat[11]),
            "period_start": p_start,
            "period_end": p_end,
            "source_file": path.name,
        })

    stats.shipments = len(shipments)
    stats.items = len(items)
    return shipments, items, stats


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(SRC_DIR.glob("*.xlsx"))
    print(f"[i] Файлов на входе: {len(files)}")

    all_ships: list[dict] = []
    all_items: list[dict] = []
    report: list[dict] = []

    for idx, f in enumerate(files, 1):
        try:
            ships, items, st = parse_file(f)
        except Exception as exc:  # noqa: BLE001
            print(f"[{idx}/{len(files)}] !! {f.name}: {exc}")
            report.append({"file": f.name, "error": str(exc)})
            continue
        all_ships.extend(ships)
        all_items.extend(items)
        report.append({
            "file": st.file,
            "period_start": st.period_start,
            "period_end": st.period_end,
            "shipments": st.shipments,
            "items": st.items,
            "rows_total": st.rows_total,
            "errors": st.errors,
        })
        print(f"[{idx:02d}/{len(files)}] {f.name[:60]:60s}  ships={st.shipments:>4d}  items={st.items:>5d}")

    df_ships = pd.DataFrame(all_ships)
    df_items = pd.DataFrame(all_items)

    # Дедупликация по (shipment_id, shipment_date) и (shipment_id, item_name)
    before_s, before_i = len(df_ships), len(df_items)
    df_ships = df_ships.drop_duplicates(subset=["shipment_id", "shipment_date"], keep="first")
    df_items = df_items.drop_duplicates(subset=["shipment_id", "shipment_date", "item_name"], keep="first")
    print(f"[i] Дедуп: ships {before_s} -> {len(df_ships)},  items {before_i} -> {len(df_items)}")

    # Производные поля
    if not df_ships.empty:
        df_ships["dow"] = df_ships["shipment_date"].dt.dayofweek
        df_ships["month"] = df_ships["shipment_date"].dt.to_period("M").astype(str)
        df_ships["year"] = df_ships["shipment_date"].dt.year
    if not df_items.empty:
        df_items["dow"] = df_items["shipment_date"].dt.dayofweek
        df_items["month"] = df_items["shipment_date"].dt.to_period("M").astype(str)
        df_items["year"] = df_items["shipment_date"].dt.year
        df_items["unsold_qty"] = (df_items["loaded_qty"].fillna(0) - df_items["sold_qty"].fillna(0)).clip(lower=0)
        df_items["sell_through"] = df_items.apply(
            lambda r: (r["sold_qty"] / r["loaded_qty"]) if r["loaded_qty"] else None, axis=1
        )

    ships_path = OUT_DIR / "shipments.parquet"
    items_path = OUT_DIR / "items.parquet"
    report_path = OUT_DIR / "_etl_report.json"

    df_ships.to_parquet(ships_path, index=False)
    df_items.to_parquet(items_path, index=False)
    report_path.write_text(
        json.dumps({"files": report, "totals": {
            "shipments": int(len(df_ships)),
            "items": int(len(df_items)),
            "files_in": len(files),
        }}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("-" * 60)
    print(f"[OK] shipments: {len(df_ships):>6d}  -> {ships_path}")
    print(f"[OK] items:     {len(df_items):>6d}  -> {items_path}")
    print(f"[OK] report:    -> {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
