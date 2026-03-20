#!/usr/bin/env python3
"""
OCR Benchmark: EasyOCR via Docling.

Run from main venv:
    /home/budnik_an/Obligations/venv/bin/python poc/bench_easyocr.py
"""

from __future__ import annotations

import gc
import json
import time
from pathlib import Path

import torch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PAGES_FILE = PROJECT_ROOT / "poc" / "fixtures" / "benchmark_pages.json"
OUTPUT_FILE = PROJECT_ROOT / "poc" / "benchmark_results" / "easyocr.json"


def get_vram_mb() -> int:
    if torch.cuda.is_available():
        return round(torch.cuda.memory_allocated(0) / 1024**2)
    return 0


def main():
    print("=" * 60)
    print("Benchmark: EasyOCR via Docling")
    print("=" * 60)

    with open(PAGES_FILE, "r", encoding="utf-8") as f:
        pages = json.load(f)

    pdf_groups: dict[str, list[dict]] = {}
    for p in pages:
        pdf_groups.setdefault(p["pdf_path"], []).append(p)

    print(f"Pages: {len(pages)}, PDFs: {len(pdf_groups)}")

    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.datamodel.pipeline_options import (
        PdfPipelineOptions,
        EasyOcrOptions,
    )
    from docling.datamodel.base_models import InputFormat

    ocr_options = EasyOcrOptions(lang=["ru", "en"], use_gpu=True, force_full_page_ocr=True)
    pipeline_options = PdfPipelineOptions(
        do_ocr=True,
        ocr_options=ocr_options,
    )
    format_options = {InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}

    print("\nLoading Docling + EasyOCR...")
    t_load = time.time()
    converter = DocumentConverter(format_options=format_options)
    load_time = round(time.time() - t_load, 1)
    vram_model = get_vram_mb()
    print(f"Loaded in {load_time}s, VRAM: {vram_model} MB")

    results = []

    for pdf_path, page_list in pdf_groups.items():
        doc_code = page_list[0]["doc_code"]
        page_nums = sorted(set(p["page_num"] for p in page_list))

        print(f"\n  Processing {doc_code} ({len(page_nums)} pages)...")

        t0 = time.time()
        try:
            result = converter.convert(pdf_path)
            doc_md = result.document.export_to_markdown()
        except Exception as e:
            print(f"    ERROR: {e}")
            doc_md = ""
        convert_time = round(time.time() - t0, 1)
        vram_now = get_vram_mb()

        total_pages_in_doc = len(page_list)
        per_page_time = round(convert_time / total_pages_in_doc, 1) if total_pages_in_doc else 0

        for p in page_list:
            page_text = doc_md
            chars = len(page_text)

            results.append({
                "doc_code": p["doc_code"],
                "page_num": p["page_num"],
                "page_type": p["page_type"],
                "model": "easyocr-docling",
                "prompt": "force_full_page_ocr",
                "text": page_text[:2000],
                "chars": chars,
                "inference_time": per_page_time,
                "vram_mb": vram_now,
            })

        print(f"    Done: {convert_time}s total, {per_page_time}s/page, {len(doc_md)} chars, VRAM: {vram_now} MB")

    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    meta = {
        "model": "easyocr-docling",
        "model_id": "easyocr 1.7.2 + docling 2.80.0",
        "load_time": load_time,
        "vram_model_mb": vram_model,
        "prompt": "force_full_page_ocr, lang=[ru,en]",
        "dpi": "docling default",
        "pages_count": len(results),
        "total_inference_time": round(sum(r["inference_time"] for r in results), 1),
        "avg_inference_time": round(
            sum(r["inference_time"] for r in results) / len(results), 1
        ) if results else 0,
    }

    output = {"meta": meta, "results": results}

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"DONE: {OUTPUT_FILE.name}")
    print(f"  Pages: {meta['pages_count']}")
    print(f"  Load: {meta['load_time']}s")
    print(f"  Total inference: {meta['total_inference_time']}s")
    print(f"  Avg per page: {meta['avg_inference_time']}s")
    print("=" * 60)


if __name__ == "__main__":
    main()
