#!/usr/bin/env python3
"""
Prepare benchmark test set: select diverse pages from PDFs for OCR/VLM benchmark.

Analyzes pages in input2/BND/pdf/ and selects ~20-25 pages covering:
  - text-only (dense text, no graphics)
  - tables (structured tabular data)
  - diagrams/graphics (drawings, flowcharts)
  - mixed (text + tables on same page)
  - scan/cover (title pages, approval sheets)

Output: poc/fixtures/benchmark_pages.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import fitz  # PyMuPDF

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_DIR = PROJECT_ROOT / "input2" / "BND" / "pdf"
OUTPUT_FILE = PROJECT_ROOT / "poc" / "fixtures" / "benchmark_pages.json"

TARGET_PDFS = [
    "КД-РГ-039-05",
    "ДП-М1.020-06",
    "РГ-179-02",
    "ДП-Б1.004-06",
    "КД-РГ-110-05",
]


def find_pdf(code: str) -> Path | None:
    for d in INPUT_DIR.iterdir():
        if d.is_dir() and d.name.startswith(code):
            pdfs = list(d.glob("*.pdf"))
            if pdfs:
                return pdfs[0]
    return None


def classify_page(page: fitz.Page, page_num: int, total_pages: int) -> dict:
    text = page.get_text().strip()
    text_lines = [l for l in text.split("\n") if l.strip()]
    drawings = page.get_drawings()
    images = page.get_images()
    tables = page.find_tables()
    table_count = len(tables.tables) if tables else 0

    n_lines = len(text_lines)
    n_drawings = len(drawings)
    n_images = len(images)
    n_chars = len(text)

    page_type = "text"

    is_cover = page_num <= 1 and (
        n_lines < 20
        or any(kw in text.upper() for kw in ["УТВЕРЖДАЮ", "ЭТАЛОН", "ПРЕДИСЛОВИЕ"])
    )
    is_approval = page_num >= total_pages - 2 and any(
        kw in text.upper() for kw in ["ЛИСТ СОГЛАСОВАНИЯ", "СОГЛАСОВАНО", "ПОДПИСЬ"]
    )

    if is_cover or is_approval:
        page_type = "cover_scan"
    elif n_drawings > 30 or n_images > 2:
        if table_count > 0 and n_lines > 10:
            page_type = "mixed"
        else:
            page_type = "diagram"
    elif table_count > 0:
        if n_lines > 20 and n_chars > 500:
            page_type = "mixed"
        else:
            page_type = "table"
    elif n_lines > 5:
        page_type = "text"

    return {
        "page_num": page_num,
        "type": page_type,
        "text_lines": n_lines,
        "chars": n_chars,
        "drawings": n_drawings,
        "images": n_images,
        "tables": table_count,
    }


def select_pages(all_pages: list[dict], target_per_type: dict) -> list[dict]:
    by_type: dict[str, list[dict]] = {}
    for p in all_pages:
        by_type.setdefault(p["type"], []).append(p)

    selected = []
    for ptype, count in target_per_type.items():
        candidates = by_type.get(ptype, [])
        candidates.sort(key=lambda x: x["chars"], reverse=True)
        step = max(1, len(candidates) // count) if candidates else 1
        picked = candidates[::step][:count]
        selected.extend(picked)

    return selected


def main():
    print("=" * 60)
    print("Подготовка тестового набора для OCR/VLM Benchmark")
    print("=" * 60)

    pdf_paths = {}
    for code in TARGET_PDFS:
        path = find_pdf(code)
        if path:
            pdf_paths[code] = path
            print(f"  OK: {code} -> {path.name}")
        else:
            print(f"  SKIP: {code} not found")

    if len(pdf_paths) < 3:
        print("ERROR: need at least 3 PDFs")
        sys.exit(1)

    all_pages = []
    for code, pdf_path in pdf_paths.items():
        doc = fitz.open(str(pdf_path))
        total = len(doc)
        print(f"\n  {code}: {total} стр.")

        type_counts: dict[str, int] = {}
        for i in range(total):
            info = classify_page(doc[i], i, total)
            info["doc_code"] = code
            info["pdf_path"] = str(pdf_path)
            all_pages.append(info)
            t = info["type"]
            type_counts[t] = type_counts.get(t, 0) + 1

        for t, c in sorted(type_counts.items()):
            print(f"    {t}: {c}")
        doc.close()

    print(f"\n  Всего страниц: {len(all_pages)}")

    target = {
        "text": 5,
        "table": 5,
        "diagram": 5,
        "mixed": 5,
        "cover_scan": 3,
    }

    selected = select_pages(all_pages, target)
    print(f"\n  Отобрано: {len(selected)} страниц")

    type_summary: dict[str, int] = {}
    for p in selected:
        type_summary[p["type"]] = type_summary.get(p["type"], 0) + 1
    for t, c in sorted(type_summary.items()):
        print(f"    {t}: {c}")

    benchmark_pages = []
    for p in selected:
        benchmark_pages.append({
            "doc_code": p["doc_code"],
            "pdf_path": p["pdf_path"],
            "page_num": p["page_num"],
            "page_type": p["type"],
            "text_lines": p["text_lines"],
            "chars": p["chars"],
            "drawings": p["drawings"],
            "images": p["images"],
            "tables": p["tables"],
        })

    benchmark_pages.sort(key=lambda x: (x["doc_code"], x["page_num"]))

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(benchmark_pages, f, ensure_ascii=False, indent=2)

    print(f"\n  Сохранено: {OUTPUT_FILE}")
    print(f"\n  Список страниц:")
    for p in benchmark_pages:
        print(f"    {p['doc_code']} стр.{p['page_num']+1} [{p['page_type']}] "
              f"({p['text_lines']} lines, {p['tables']} tables, {p['drawings']} drawings)")


if __name__ == "__main__":
    main()
