"""TASK-014: каталог релевантных AMOS APN-модулей для ATA-слоя.

Источник истины — статические материалы в /home/budnik_an/todo/webBI/:
  * amos-help/index.html — TOC из 457 APN с EN/RU именами и ссылками на .htm
  * amos-db-explorer.html — Oracle-модули AMOS с именами таблиц

Фильтр — keyword-list по теме «defects / ATA / WO / MEL / snag / reliability /
troubleshooting / engineering / repair / removal / maintenance».

Выход:  output/amos_layer/amos_apn_catalog.json
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path("/home/budnik_an/Obligations")
TODO = Path("/home/budnik_an/todo")
HELP_INDEX = TODO / "webBI" / "amos-help" / "index.html"
DB_EXPLORER = TODO / "webBI" / "amos-db-explorer.html"
APN_ANALYTICS = TODO / "webBI" / "amos-apn-analytics.md"
OUT_DIR = ROOT / "output" / "amos_layer"
OUT_FILE = OUT_DIR / "amos_apn_catalog.json"

# Keyword list — что считаем «AMOS-уровнем» (отказы/ATA/MEL/WO/надёжность/ТО).
# Регистр: lower(). Проверка против EN+RU имени APN.
KW = [
    # отказы / дефекты / надёжность
    "defect", "snag", "fault", "failure", "reliab", "deferred",
    "дефект", "отказ", "надёжн", "надежн", "отложен",
    # технические замечания / case management
    "technical", "troubleshoot", "case manager",
    "техническ", "замечани",
    # MEL
    "mel ", " mel", "minimum equipment", "min. equip",
    # work orders / job cards / maintenance events
    "workorder", "work order", "job card", "work package",
    "maintenance event", "maintenance forecast", "maintenance program",
    "maintenance finding", "scheduled maintenance",
    "наряд", "карта работ", "пакет работ", "событи", "программа то",
    # engineering / repair / removal
    "engineering order", "repair", "removal", "rotable",
    "инженерн", "ремонт", "снят", "ротиру",
    # ATA / IATA / spec2k
    " ata", "ata ", "ata200", "ata-",
    # availability / OEM / EO
    "availability", "service bulletin", "airworthiness",
    "готовн", "лётн", "директив",
    # cabin / configuration defects
    "cabin defect",
]

# Модули AMOS DB (Oracle) — релевантные для ATA-слоя. Hint-маппинг на APN-группы.
# Используется в финальном JSON как table_hints; источник — amos-db-explorer.html.
RELEVANT_DB_MODULES = [
    "wo",       # Work Orders / Заказ-наряды (33 таблицы)
    "wp",       # Work Packages / Пакеты работ (28)
    "jc",       # Job Cards / Карты работ (23)
    "moc",      # MOC / Центр управления ТО (39) — case management
    "mel",      # MEL / Мин. перечень (12)
    "mevt",     # Maintenance Events (9)
    "event",    # Events / События (23)
    "pm",       # Planned Maintenance (37)
    "msc",      # MSC Planning (55)
    "qa",       # Quality (20)
    "qm",       # QM (13)
    "tech",     # TECH (10)
    "rotables", # ROTABLES (11)
    "sr",       # SR (9)
    "spec2k",   # Spec 2000 / Стандарт ATA (18)
    "rm",       # RM / Reliability (10)
    "doc",      # Documents (45) — SB/AD
]


# ---------- helpers -------------------------------------------------------- #

def _extract_js_var(src: str, marker: str) -> str:
    """Достать тело правого JSON-литерала после `var NAME=` или `const NAME=`.

    Считает фигурные/квадратные скобки до корректного баланса; учитывает строки
    с двойными кавычками (одиночные в этих файлах не используются). Это надёжнее
    регулярки, потому что значения многомегабайтные.
    """
    idx = src.find(marker)
    if idx < 0:
        raise RuntimeError(f"marker not found: {marker!r}")
    start = src.find("[", idx)
    cb = "]"
    alt = src.find("{", idx)
    if alt >= 0 and (start < 0 or alt < start):
        start, cb = alt, "}"
    if start < 0:
        raise RuntimeError(f"no opening bracket after {marker!r}")
    depth = 0
    in_str = False
    esc = False
    ob = "[" if cb == "]" else "{"
    for i in range(start, len(src)):
        c = src[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == ob:
            depth += 1
        elif c == cb:
            depth -= 1
            if depth == 0:
                return src[start : i + 1]
    raise RuntimeError(f"unbalanced for {marker!r}")


def load_toc() -> list[dict]:
    src = HELP_INDEX.read_text(encoding="utf-8")
    body = _extract_js_var(src, "var TOC=")
    return json.loads(body)


def load_db() -> dict:
    src = DB_EXPLORER.read_text(encoding="utf-8")
    body = _extract_js_var(src, "const DB")
    return json.loads(body)


def walk_apns(toc: Any) -> list[dict]:
    out: list[dict] = []

    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            u = node.get("u", "")
            if isinstance(u, str) and u.startswith("APN") and u.endswith(".htm"):
                num = u[3:-4]
                out.append({
                    "apn": num,
                    "apn_int": int(num),
                    "en": node.get("e", "").strip(),
                    "ru": node.get("r", "").strip(),
                    "url": u,
                })
            for ch in node.get("c") or []:
                _walk(ch)
        elif isinstance(node, list):
            for it in node:
                _walk(it)

    _walk(toc)
    return out


def matches_keyword(apn: dict) -> tuple[bool, list[str]]:
    s = (apn["en"] + " | " + apn["ru"]).lower()
    hits = [k.strip() for k in KW if k in s]
    return (bool(hits), sorted(set(hits)))


def load_used_apns_from_analytics() -> set[str]:
    """Из webBI/amos-apn-analytics.md достать использованные APN отделов."""
    if not APN_ANALYTICS.exists():
        return set()
    text = APN_ANALYTICS.read_text(encoding="utf-8")
    used: set[str] = set()
    for m in re.finditer(r"\|\s*(\d{2,5})\s*\|\s*[A-Z]", text):
        used.add(m.group(1).zfill(4))
    return used


# ---------- ATA-routing ---------------------------------------------------- #

# Какие AMOS-модули предположительно держат поля по теме, на основе семантики
# названия APN.  Используется как `table_hints` в каталоге.
APN_GROUP_RULES = [
    # (категория, condition predicate, db-modules hint, поле-намёк)
    ("workorder_defect", lambda a: any(k in a["en"].lower() for k in ["workorder", "work order", "job card", "work package"]),
        ["wo", "jc", "wp"], "Defect description / Component / ATA chapter / Task code"),
    ("mel_deferred", lambda a: "mel" in a["en"].lower() or "deferred" in a["en"].lower() or "отложен" in a["ru"].lower(),
        ["mel", "wo"], "MEL code / Cat / DeferralRef / ATA / Open since"),
    ("reliability", lambda a: "reliab" in a["en"].lower() or "надёжн" in a["ru"].lower() or "надежн" in a["ru"].lower(),
        ["rm", "moc"], "ATA / Aircraft / Failure mode / MTBF / Removals"),
    ("failure_confirmation", lambda a: "failure" in a["en"].lower() or "отказ" in a["ru"].lower(),
        ["rm", "moc", "wo"], "Failure code / ATA chapter / Component / Confirmation status"),
    ("removal", lambda a: "removal" in a["en"].lower() or "remov" in a["en"].lower() or "снят" in a["ru"].lower(),
        ["rotables", "wo"], "Removal reason / ATA / Component PN/SN / Aircraft"),
    ("technical_case", lambda a: "case" in a["en"].lower() or "technical assistance" in a["en"].lower(),
        ["moc"], "Case ID / Description / ATA / Aircraft / Status"),
    ("maintenance_event", lambda a: "maintenance event" in a["en"].lower() or "событи" in a["ru"].lower(),
        ["mevt", "event", "msc"], "Event ID / Type / Aircraft / Due date / ATA"),
    ("engineering_order", lambda a: "engineering" in a["en"].lower() or "инженерн" in a["ru"].lower(),
        ["wo", "doc"], "EO number / Type / ATA / Aircraft applicability"),
    ("repair", lambda a: "repair" in a["en"].lower() or "ремонт" in a["ru"].lower(),
        ["wo", "od"], "Repair order / Vendor / Component / ATA"),
    ("ata_lookup", lambda a: "ata" in a["en"].lower() and "ata" not in "iata",
        ["spec2k"], "ATA chapter / Subchapter / Description"),
    ("rotables_admin", lambda a: "rotable" in a["en"].lower() or "ротиру" in a["ru"].lower(),
        ["rotables", "part"], "PN / SN / ATA / Lifecycle / Position"),
    ("maintenance_plan", lambda a: any(k in a["en"].lower() for k in ["maintenance program", "maintenance forecast", "scheduled maintenance", "maintenance finding"]),
        ["pm", "msc"], "Task / Interval / ATA / Aircraft / Due / Finding"),
    ("airworthiness", lambda a: "airworth" in a["en"].lower() or "лётн" in a["ru"].lower() or "директив" in a["ru"].lower(),
        ["doc", "pm"], "SB/AD ref / Issued / ATA / Aircraft applicability / Status"),
    ("availability", lambda a: "availability" in a["en"].lower() or "готовн" in a["ru"].lower(),
        ["wo", "mevt"], "Aircraft / Date / Down-time / ATA"),
]


def classify_apn(apn: dict) -> dict:
    matches: list[dict] = []
    for cat, pred, hints, fld in APN_GROUP_RULES:
        try:
            ok = pred(apn)
        except Exception:
            ok = False
        if ok:
            matches.append({"category": cat, "db_module_hints": hints, "field_hint": fld})
    return {
        "categories": matches,
        "primary_category": matches[0]["category"] if matches else None,
        "db_module_hints": sorted({m for c in matches for m in c["db_module_hints"]}) if matches else [],
    }


# ---------- main ----------------------------------------------------------- #

def main() -> None:
    print(f"reading {HELP_INDEX}")
    toc = load_toc()
    apns = walk_apns(toc)
    print(f"  TOC: {len(apns)} APN entries")

    print(f"reading {DB_EXPLORER}")
    db = load_db()
    modules = db.get("modules", [])
    mod_index = {m["id"]: m for m in modules}
    print(f"  DB: {len(modules)} modules")

    used = load_used_apns_from_analytics()
    print(f"  apn-analytics: {len(used)} used APN (will be force-included)")

    filtered: list[dict] = []
    for a in apns:
        hit, hits = matches_keyword(a)
        force_used = a["apn"] in used
        if not (hit or force_used):
            continue
        ata = classify_apn(a)
        # «таблицы-намёки»: первые 8 имен из приоритетных модулей AMOS, чтобы
        # не превращать каталог в простыню; полные списки доступны в db-explorer.
        table_hints: list[str] = []
        for mid in ata["db_module_hints"] or RELEVANT_DB_MODULES[:5]:
            mod = mod_index.get(mid)
            if not mod:
                continue
            for tbl in mod.get("tables", [])[:8]:
                table_hints.append(f"{mid}.{tbl}")
        filtered.append({
            "apn": a["apn"],
            "apn_int": a["apn_int"],
            "name_en": a["en"],
            "name_ru": a["ru"],
            "help_url": f"/info/amos-help/{a['url']}",
            "matched_keywords": hits,
            "force_used_by_utair": force_used,
            "categories": [c["category"] for c in ata["categories"]],
            "primary_category": ata["primary_category"],
            "db_module_hints": ata["db_module_hints"],
            "table_hints": table_hints,
            "field_hints": list({c["field_hint"] for c in ata["categories"]}),
        })

    filtered.sort(key=lambda x: x["apn_int"])
    print(f"  relevant APN after filter+force-include: {len(filtered)}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": "v1",
        "task": "TASK-014",
        "source": {
            "toc": str(HELP_INDEX),
            "db_explorer": str(DB_EXPLORER),
            "apn_analytics": str(APN_ANALYTICS),
        },
        "stats": {
            "toc_total_apn": len(apns),
            "db_modules_total": len(modules),
            "relevant_apn": len(filtered),
            "force_used_apn": len(used),
        },
        "relevant_apn_categories": sorted({c for a in filtered for c in a["categories"]}),
        "db_modules_relevant_for_ata": RELEVANT_DB_MODULES,
        "apn": filtered,
    }
    OUT_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"written {OUT_FILE} ({OUT_FILE.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
