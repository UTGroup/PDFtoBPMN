"""POC: построение обогащённого каталога APN AMOS, используемых отделами UTair.

Read-only генератор данных для отчёта `docs/reports/AMOS_APN_usage_analysis_v1.md`.
НЕ production. Не использовать в pipeline.

Источники:
- input2/AMOS/APN_usage/Рабочие APN AMOS по отделам.xlsx (72 строки, AS-IS)
- input2/AMOS/APN_usage/Выгрузка всех номеров APN из AMOS.xlsx (940 APN)
- input2/AMOS/APN_usage/наименование отчетов UTA.REP....xlsx (215 отчётов)
- /home/budnik_an/todo/webBI/amos-help/ (HTM Guide + toc.xml + map.jhm)
- /home/budnik_an/todo/unpublished/amos-pdf-en/ (PDF Guide)

Output: poc/amos_apn_enriched.json
"""
from __future__ import annotations

import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Optional

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
INPUT_DIR = REPO_ROOT / "input2" / "AMOS" / "APN_usage"
GUIDE_HTM_DIR = Path("/home/budnik_an/todo/webBI/amos-help")
GUIDE_PDF_DIR = Path("/home/budnik_an/todo/unpublished/amos-pdf-en")
OUT_PATH = REPO_ROOT / "poc" / "amos_apn_enriched.json"

OUT_OF_AMOS_TOKENS = {
    "SAP", "Superset", "Business Studio",
}
GAP_TOKENS = {
    "сборный отчет", "Автомат из AMOS", "через виджит Mini report",
    "через виджет Mini report",
}


def parse_xlsx_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    df_dept = pd.read_excel(INPUT_DIR / "Рабочие APN AMOS по отделам.xlsx")
    df_dept = df_dept.rename(columns={
        "Наименование ответственного отдела ": "department",
        "Руководитель отдела": "manager_raw",
        "APN": "apn_raw",
        "Name": "name_raw",
        "Description": "usage_note",
    })
    df_dept["department"] = df_dept["department"].astype(str).str.strip()
    df_dept["manager"] = df_dept["manager_raw"].ffill().astype(str).str.strip()
    df_dept["manager"] = df_dept["manager"].replace({"nan": None})

    df_cat = pd.read_excel(INPUT_DIR / "Выгрузка всех номеров APN из AMOS.xlsx")
    df_cat = df_cat.rename(columns={
        "APN": "apn",
        "Description": "name_en",
        "Описание - перевод": "name_ru",
    })
    df_cat["apn"] = df_cat["apn"].astype(int)

    df_uta = pd.read_excel(INPUT_DIR / "наименование отчетов UTA.REP....из виджет Mini report ..xlsx")
    df_uta = df_uta.rename(columns={"Report ID": "report_id", "Description": "report_desc"})

    return df_dept, df_cat, df_uta


def parse_guide_index() -> tuple[dict[str, str], dict[str, str]]:
    """Parse map.jhm and toc.xml. Returns (target -> url, name_norm -> target)."""
    map_tree = ET.parse(GUIDE_HTM_DIR / "map.jhm")
    tgt2url: dict[str, str] = {
        m.get("target"): m.get("url")
        for m in map_tree.getroot().findall(".//mapID")
        if m.get("target") and m.get("url")
    }

    toc_tree = ET.parse(GUIDE_HTM_DIR / "toc.xml")
    name2tgt: dict[str, str] = {}
    for it in toc_tree.getroot().findall(".//tocitem"):
        text = (it.get("text") or "").strip()
        target = it.get("target") or ""
        if text and target and text not in name2tgt:
            name2tgt[text] = target
    return tgt2url, name2tgt


_norm_re = re.compile(r"[^a-z0-9]+")


def norm_name(s: str) -> str:
    s = unicodedata.normalize("NFKC", s).lower()
    return _norm_re.sub("", s)


def build_pdf_index() -> dict[str, str]:
    """Map normalized english module name -> pdf filename."""
    idx: dict[str, str] = {}
    for p in GUIDE_PDF_DIR.glob("*.pdf"):
        stem = p.stem
        idx[norm_name(stem.replace("_", " "))] = p.name
    return idx


_title_re = re.compile(r"<title>\s*(.+?)\s*</title>", re.IGNORECASE | re.DOTALL)
_heading_re = re.compile(
    r'<h\d[^>]*class="heading\d"[^>]*>(.+?)</h\d>', re.IGNORECASE | re.DOTALL
)


def read_htm_titles(htm_path: Path) -> dict[str, Optional[str]]:
    try:
        text = htm_path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return {"title": None, "heading": None}
    title = None
    heading = None
    m = _title_re.search(text)
    if m:
        title = re.sub(r"\s+", " ", m.group(1)).strip()
    m = _heading_re.search(text)
    if m:
        heading = re.sub(r"<[^>]+>", "", m.group(1))
        heading = re.sub(r"\s+", " ", heading).strip()
    return {"title": title, "heading": heading}


def resolve_apn_guide(
    apn: int,
    name_en: Optional[str],
    tgt2url: dict[str, str],
    name2tgt: dict[str, str],
    pdf_idx: dict[str, str],
) -> dict:
    """Найти guide HTM + PDF для APN. Return dict с найденным/None."""
    htm_apn_pad = f"APN{apn:04d}.htm" if apn < 10000 else None
    htm_apn_path = GUIDE_HTM_DIR / htm_apn_pad if htm_apn_pad else None
    htm_url = None
    htm_match_kind = None
    if htm_apn_path and htm_apn_path.exists():
        htm_url = htm_apn_pad
        htm_match_kind = "apn_padded"
    elif name_en:
        tgt = name2tgt.get(name_en)
        if tgt and tgt in tgt2url:
            url = tgt2url[tgt]
            if (GUIDE_HTM_DIR / url).exists():
                htm_url = url
                htm_match_kind = "toc_name"

    titles = (
        read_htm_titles(GUIDE_HTM_DIR / htm_url)
        if htm_url
        else {"title": None, "heading": None}
    )

    pdf_name = None
    if name_en:
        pdf_name = pdf_idx.get(norm_name(name_en))

    return {
        "guide_htm_url": htm_url,
        "guide_htm_match_kind": htm_match_kind,
        "guide_htm_title": titles["title"],
        "guide_htm_heading": titles["heading"],
        "guide_pdf_filename": pdf_name,
    }


def classify_row(apn_raw, name_raw) -> tuple[str, Optional[int]]:
    """Return (kind, apn_int_or_None). kind in {amos_apn, uta_report, sap, lotus, superset, business_studio, gap_no_apn, other}."""
    raw = "" if pd.isna(apn_raw) else str(apn_raw).strip()
    if raw.isdigit():
        n = int(raw)
        if n >= 10000 and isinstance(name_raw, str) and "UTA.REP" in name_raw:
            return "uta_report", n
        return "amos_apn", n
    raw_low = raw.lower()
    if raw == "SAP":
        return "sap", None
    if "lotus" in raw_low:
        return "lotus", None
    if raw == "Superset":
        return "superset", None
    if raw == "Business Studio":
        return "business_studio", None
    if "сборный" in raw_low or "автомат" in raw_low or "mini report" in raw_low:
        return "gap_no_apn", None
    return "other", None


def main() -> None:
    df_dept, df_cat, df_uta = parse_xlsx_inputs()
    tgt2url, name2tgt = parse_guide_index()
    pdf_idx = build_pdf_index()
    cat_dict: dict[int, dict] = {
        int(r.apn): {"name_en": r.name_en, "name_ru": r.name_ru}
        for r in df_cat.itertuples(index=False)
    }
    uta_dict = dict(zip(df_uta["report_id"], df_uta["report_desc"]))

    used_apns: dict[int, dict] = {}
    used_uta: dict[str, dict] = {}
    rows_normalized = []
    counts = defaultdict(int)

    for r in df_dept.itertuples(index=False):
        kind, apn_int = classify_row(r.apn_raw, r.name_raw)
        counts[kind] += 1
        row = {
            "department": r.department,
            "manager": r.manager,
            "apn_raw": None if pd.isna(r.apn_raw) else str(r.apn_raw),
            "name_raw": None if pd.isna(r.name_raw) else str(r.name_raw),
            "usage_note": None if pd.isna(r.usage_note) else str(r.usage_note),
            "kind": kind,
            "apn_int": apn_int,
        }
        if kind == "amos_apn" and apn_int is not None:
            cat = cat_dict.get(apn_int, {})
            row["name_en"] = cat.get("name_en")
            row["name_ru"] = cat.get("name_ru")
            guide = resolve_apn_guide(apn_int, cat.get("name_en"), tgt2url, name2tgt, pdf_idx)
            row.update(guide)
            if apn_int not in used_apns:
                used_apns[apn_int] = {
                    "apn": apn_int,
                    "name_en": cat.get("name_en"),
                    "name_ru": cat.get("name_ru"),
                    **guide,
                    "departments": [],
                }
            used_apns[apn_int]["departments"].append(
                {"department": r.department, "usage_note": row["usage_note"]}
            )
        elif kind == "uta_report" and apn_int is not None:
            name_raw = row["name_raw"]
            uta_desc = uta_dict.get(name_raw)
            row["uta_report_id"] = name_raw
            row["uta_report_desc"] = uta_desc
            key = name_raw or f"APN{apn_int}"
            if key not in used_uta:
                used_uta[key] = {
                    "apn": apn_int,
                    "report_id": name_raw,
                    "report_desc": uta_desc,
                    "departments": [],
                }
            used_uta[key]["departments"].append(
                {"department": r.department, "usage_note": row["usage_note"]}
            )
        rows_normalized.append(row)

    coverage = {
        "guide_htm_found": sum(1 for v in used_apns.values() if v.get("guide_htm_url")),
        "guide_pdf_found": sum(1 for v in used_apns.values() if v.get("guide_pdf_filename")),
        "guide_both_missing": sum(
            1
            for v in used_apns.values()
            if not v.get("guide_htm_url") and not v.get("guide_pdf_filename")
        ),
    }

    snapshot = {
        "summary": {
            "total_rows_dept_xlsx": len(df_dept),
            "total_apn_catalog": len(df_cat),
            "total_uta_reports_catalog": len(df_uta),
            "row_kinds": dict(counts),
            "unique_amos_apn_used": len(used_apns),
            "unique_uta_reports_used": len(used_uta),
            "guide_coverage": coverage,
        },
        "rows": rows_normalized,
        "used_apns": sorted(used_apns.values(), key=lambda x: x["apn"]),
        "used_uta_reports": sorted(used_uta.values(), key=lambda x: x["apn"]),
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Written: {OUT_PATH}")
    print(json.dumps(snapshot["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
