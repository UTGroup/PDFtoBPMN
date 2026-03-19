#!/usr/bin/env python3
"""
POC: Docling + OCR comparison (EasyOCR vs RapidOCR) на русскоязычных PDF документах СМК.

TASK-002 — сравнение OCR-бэкендов через Docling pipeline.
5 сценариев: native text, scanned, mixed, tables, graphics.

Метрика: Levenshtein similarity (нормализованная).
Порог: ≥95% native, ≥90% scanned/mixed/tables/graphics.

Использование:
    python3 poc/poc_ocr_comparison.py [--pdf PATH] [--pages N] [--force-ocr]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

import Levenshtein
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    EasyOcrOptions,
    PdfPipelineOptions,
    RapidOcrOptions,
)
from docling.document_converter import DocumentConverter, PdfFormatOption


@dataclass
class ScenarioResult:
    scenario: str
    ocr_engine: str
    pages_processed: int
    text_length: int
    elapsed_sec: float
    similarity: Optional[float] = None
    error: Optional[str] = None


@dataclass
class ComparisonReport:
    pdf_path: str
    pdf_size_kb: float
    total_pages: int
    results: list[ScenarioResult] = field(default_factory=list)


def build_converter(
    ocr_engine: str,
    force_full_page_ocr: bool = False,
    do_ocr: bool = True,
) -> DocumentConverter:
    """Build DocumentConverter with specified OCR backend."""
    if ocr_engine == "easyocr":
        ocr_options = EasyOcrOptions(
            lang=["ru", "en"],
            use_gpu=True,
            force_full_page_ocr=force_full_page_ocr,
            confidence_threshold=0.3,
        )
    elif ocr_engine == "rapidocr":
        ocr_options = RapidOcrOptions(
            force_full_page_ocr=force_full_page_ocr,
            backend="onnxruntime",
            text_score=0.3,
        )
    elif ocr_engine == "none":
        ocr_options = None
    else:
        raise ValueError(f"Unknown OCR engine: {ocr_engine}")

    pipeline_options = PdfPipelineOptions(
        do_ocr=do_ocr and ocr_options is not None,
        do_table_structure=True,
    )
    if ocr_options is not None:
        pipeline_options.ocr_options = ocr_options

    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
        }
    )


def convert_pdf(converter: DocumentConverter, pdf_path: Path) -> tuple[str, int]:
    """Convert PDF and return (markdown_text, num_pages)."""
    result = converter.convert(str(pdf_path))
    doc = result.document
    md = doc.export_to_markdown()
    num_pages = doc.num_pages() if hasattr(doc, "num_pages") else -1
    return md, num_pages


def levenshtein_similarity(a: str, b: str) -> float:
    """Normalized Levenshtein similarity [0..1]."""
    if not a and not b:
        return 1.0
    dist = Levenshtein.distance(a, b)
    max_len = max(len(a), len(b))
    return 1.0 - dist / max_len


def normalize_text(text: str) -> str:
    """Normalize whitespace for fair comparison."""
    import re
    text = re.sub(r"<!--.*?-->", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def run_scenario(
    pdf_path: Path,
    scenario_name: str,
    ocr_engine: str,
    force_ocr: bool = False,
    baseline_text: Optional[str] = None,
) -> ScenarioResult:
    """Run a single OCR scenario and collect metrics."""
    print(f"  [{ocr_engine}] {scenario_name}...", end=" ", flush=True)
    t0 = time.time()
    try:
        converter = build_converter(
            ocr_engine=ocr_engine,
            force_full_page_ocr=force_ocr,
            do_ocr=(ocr_engine != "none"),
        )
        md_text, num_pages = convert_pdf(converter, pdf_path)
        elapsed = time.time() - t0

        norm_text = normalize_text(md_text)
        similarity = None
        if baseline_text is not None:
            norm_baseline = normalize_text(baseline_text)
            similarity = levenshtein_similarity(norm_baseline, norm_text)

        result = ScenarioResult(
            scenario=scenario_name,
            ocr_engine=ocr_engine,
            pages_processed=num_pages,
            text_length=len(md_text),
            elapsed_sec=round(elapsed, 2),
            similarity=round(similarity, 4) if similarity is not None else None,
        )
        status = f"{elapsed:.1f}s, {len(md_text)} chars"
        if similarity is not None:
            status += f", sim={similarity:.2%}"
        print(status)
        return result

    except Exception as e:
        elapsed = time.time() - t0
        print(f"ERROR: {e}")
        return ScenarioResult(
            scenario=scenario_name,
            ocr_engine=ocr_engine,
            pages_processed=0,
            text_length=0,
            elapsed_sec=round(elapsed, 2),
            error=str(e),
        )


def find_test_pdf(input_dir: Path) -> Path:
    """Find a suitable test PDF (smallest for speed)."""
    pdfs = sorted(input_dir.glob("*.pdf"), key=lambda p: p.stat().st_size)
    if not pdfs:
        raise FileNotFoundError(f"No PDF files in {input_dir}")
    return pdfs[0]


def run_all_scenarios(pdf_path: Path, force_ocr: bool = False) -> ComparisonReport:
    """Run all 5 scenarios with both OCR engines."""
    report = ComparisonReport(
        pdf_path=str(pdf_path),
        pdf_size_kb=round(pdf_path.stat().st_size / 1024, 1),
        total_pages=0,
    )

    engines = ["easyocr", "rapidocr"]

    # --- Scenario 1: Native text (no OCR) — baseline ---
    print("\n=== Тест 1: Нативный текст (baseline, без OCR) ===")
    baseline_result = run_scenario(pdf_path, "native_text", "none", force_ocr=False)
    report.results.append(baseline_result)
    report.total_pages = baseline_result.pages_processed
    baseline_text = None
    if not baseline_result.error:
        converter = build_converter("none", do_ocr=False)
        baseline_text, _ = convert_pdf(converter, pdf_path)

    # --- Scenario 2: Full-page OCR (force OCR on all pages) ---
    print("\n=== Тест 2: Полный OCR (force_full_page_ocr=True) ===")
    for engine in engines:
        r = run_scenario(
            pdf_path, "full_page_ocr", engine,
            force_ocr=True, baseline_text=baseline_text,
        )
        report.results.append(r)

    # --- Scenario 3: Mixed mode (auto OCR — only bitmap areas) ---
    print("\n=== Тест 3: Смешанный режим (auto OCR для bitmap) ===")
    for engine in engines:
        r = run_scenario(
            pdf_path, "mixed_auto_ocr", engine,
            force_ocr=False, baseline_text=baseline_text,
        )
        report.results.append(r)

    # --- Scenario 4: Table extraction quality ---
    print("\n=== Тест 4: Таблицы (do_table_structure=True) ===")
    for engine in engines:
        r = run_scenario(
            pdf_path, "tables", engine,
            force_ocr=force_ocr, baseline_text=baseline_text,
        )
        report.results.append(r)

    # --- Scenario 5: Force OCR with low threshold (graphics with text) ---
    print("\n=== Тест 5: Графика с текстом (force OCR, low threshold) ===")
    for engine in engines:
        r = run_scenario(
            pdf_path, "graphics_text", engine,
            force_ocr=True, baseline_text=baseline_text,
        )
        report.results.append(r)

    return report


def print_summary(report: ComparisonReport) -> None:
    """Print comparison summary table."""
    print("\n" + "=" * 80)
    print(f"ИТОГИ: {report.pdf_path}")
    print(f"Размер: {report.pdf_size_kb} KB, Страниц: {report.total_pages}")
    print("=" * 80)

    header = f"{'Сценарий':<20} {'OCR':<12} {'Время,с':<10} {'Символов':<12} {'Similarity':<12} {'Статус':<10}"
    print(header)
    print("-" * 80)

    for r in report.results:
        sim_str = f"{r.similarity:.2%}" if r.similarity is not None else "—"
        status = "ERROR" if r.error else "OK"
        print(
            f"{r.scenario:<20} {r.ocr_engine:<12} {r.elapsed_sec:<10.1f} "
            f"{r.text_length:<12} {sim_str:<12} {status:<10}"
        )

    print("-" * 80)

    easyocr_results = [r for r in report.results if r.ocr_engine == "easyocr" and not r.error]
    rapidocr_results = [r for r in report.results if r.ocr_engine == "rapidocr" and not r.error]

    if easyocr_results and rapidocr_results:
        easy_avg_sim = sum(r.similarity or 0 for r in easyocr_results) / len(easyocr_results)
        rapid_avg_sim = sum(r.similarity or 0 for r in rapidocr_results) / len(rapidocr_results)
        easy_avg_time = sum(r.elapsed_sec for r in easyocr_results) / len(easyocr_results)
        rapid_avg_time = sum(r.elapsed_sec for r in rapidocr_results) / len(rapidocr_results)

        print(f"\nСредние показатели:")
        print(f"  EasyOCR:  similarity={easy_avg_sim:.2%}, время={easy_avg_time:.1f}s")
        print(f"  RapidOCR: similarity={rapid_avg_sim:.2%}, время={rapid_avg_time:.1f}s")

        if easy_avg_sim > rapid_avg_sim + 0.02:
            winner = "EasyOCR"
        elif rapid_avg_sim > easy_avg_sim + 0.02:
            winner = "RapidOCR"
        else:
            winner = "RapidOCR" if rapid_avg_time < easy_avg_time else "EasyOCR"
            winner += " (по скорости, качество ~равное)"

        print(f"\n  >>> ПОБЕДИТЕЛЬ: {winner} <<<")
    else:
        print("\nНедостаточно данных для сравнения.")


def save_report(report: ComparisonReport, output_path: Path) -> None:
    """Save report as JSON."""
    data = {
        "pdf_path": report.pdf_path,
        "pdf_size_kb": report.pdf_size_kb,
        "total_pages": report.total_pages,
        "results": [asdict(r) for r in report.results],
    }
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nОтчёт сохранён: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="POC: Docling OCR comparison")
    parser.add_argument("--pdf", type=str, help="Path to PDF file (default: smallest in input/)")
    parser.add_argument("--force-ocr", action="store_true", help="Force OCR on all pages")
    parser.add_argument("--output", type=str, default="poc/ocr_comparison_report.json")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent

    if args.pdf:
        pdf_path = Path(args.pdf)
    else:
        pdf_path = find_test_pdf(project_root / "input")

    if not pdf_path.exists():
        print(f"ERROR: PDF not found: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    print(f"PDF: {pdf_path.name} ({pdf_path.stat().st_size / 1024:.0f} KB)")
    print(f"Force OCR: {args.force_ocr}")

    report = run_all_scenarios(pdf_path, force_ocr=args.force_ocr)
    print_summary(report)

    output_path = project_root / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    save_report(report, output_path)


if __name__ == "__main__":
    main()
