#!/usr/bin/env python3
"""
POC: DeepSeek-OCR — разовый запуск на тестовых страницах с графикой.

Запуск ТОЛЬКО из DeepSeek-OCR/venv:
    /home/budnik_an/Obligations/DeepSeek-OCR/venv/bin/python poc/poc_deepseek_ocr.py

Требования: flash-attn 2.7.3, torch 2.9+, transformers 4.46+
Модель: deepseek-ai/DeepSeek-OCR (~3B, ~6GB VRAM bf16)
"""

from __future__ import annotations

import gc
import io
import sys
import time
from pathlib import Path

import fitz  # PyMuPDF
import torch
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent

TEST_PDFS = [
    PROJECT_ROOT / "input2/BND/pdf/КД-РГ-039-05 ^98922A5C1D13C8AF45258B0400287F5F/КД-РГ-039-05 (эталон №1 для печати).pdf",
    PROJECT_ROOT / "input2/BND/pdf/ДП-М1.020-06 ^692386276D6DDE30452584F50038090F/ДП-М1.020-06 (Эталон №15 для печати).pdf",
    PROJECT_ROOT / "input2/BND/pdf/РГ-179-02 ^B88F3504B6B7C3D3452582C0003229D5/РГ-179-02 (Эталон для печати).pdf",
]

MAX_PAGES_PER_DOC = 3
DPI = 200

PROMPTS = {
    "document": "<image>\n<|grounding|>Convert the document to markdown. ",
    "figure": "<image>\nParse the figure.",
    "free_ocr": "<image>\nFree OCR. ",
}


def get_vram_mb() -> int:
    if torch.cuda.is_available():
        return round(torch.cuda.memory_allocated(0) / 1024**2)
    return 0


def find_graphics_pages(pdf_path: Path, max_pages: int) -> list[int]:
    """Find pages with drawings/graphics using PyMuPDF heuristics."""
    doc = fitz.open(str(pdf_path))
    candidates = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        drawings = page.get_drawings()
        images = page.get_images()
        text = page.get_text().strip()
        text_lines = len([l for l in text.split("\n") if l.strip()])

        has_graphics = len(drawings) > 30 or len(images) > 0
        is_sparse_text = text_lines < 15

        if has_graphics or (is_sparse_text and page_num < 3):
            candidates.append({
                "page": page_num,
                "drawings": len(drawings),
                "images": len(images),
                "text_lines": text_lines,
            })

    doc.close()

    candidates.sort(key=lambda x: x["drawings"], reverse=True)
    selected = candidates[:max_pages]
    selected.sort(key=lambda x: x["page"])
    return selected


def render_page(pdf_path: Path, page_num: int, dpi: int = DPI) -> Image.Image:
    """Render PDF page to PIL Image."""
    doc = fitz.open(str(pdf_path))
    page = doc[page_num]
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    doc.close()
    return img.convert("RGB")


def load_model():
    """Load DeepSeek-OCR with flash_attention_2."""
    from transformers import AutoModel, AutoTokenizer

    print("  Loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(
        "deepseek-ai/DeepSeek-OCR", trust_remote_code=True
    )

    print("  Loading model (flash_attention_2, bf16)...")
    model = AutoModel.from_pretrained(
        "deepseek-ai/DeepSeek-OCR",
        _attn_implementation="flash_attention_2",
        trust_remote_code=True,
        use_safetensors=True,
    )
    model = model.eval().cuda().to(torch.bfloat16)

    return model, tokenizer


def run_inference(model, tokenizer, image: Image.Image, prompt_key: str) -> tuple[str, float]:
    """Run single inference, return (text, elapsed_seconds)."""
    tmp_path = Path("/tmp/deepseek_ocr_tmp.png")
    image.save(str(tmp_path))

    prompt = PROMPTS[prompt_key]
    t0 = time.time()
    result = model.infer(
        tokenizer,
        prompt=prompt,
        image_file=str(tmp_path),
        output_path="/tmp",
        base_size=1024,
        image_size=640,
        crop_mode=False,
        save_results=False,
        test_compress=False,
        eval_mode=True,
    )
    elapsed = time.time() - t0

    text = result if isinstance(result, str) else ""
    tmp_path.unlink(missing_ok=True)
    return text, elapsed


def unload_model(model, tokenizer):
    """Unload model and free VRAM."""
    del model
    del tokenizer
    gc.collect()
    torch.cuda.empty_cache()


def main():
    print("=" * 70)
    print("POC: DeepSeek-OCR — разовый запуск")
    print("=" * 70)

    # Pre-flight
    print(f"\nGPU: {torch.cuda.get_device_name(0)}")
    print(f"VRAM before: {get_vram_mb()} MB allocated")
    print(f"Test PDFs: {len(TEST_PDFS)}")
    print(f"Max pages per doc: {MAX_PAGES_PER_DOC}")
    print(f"DPI: {DPI}")

    # Verify PDFs exist
    for pdf in TEST_PDFS:
        if not pdf.exists():
            print(f"  ERROR: {pdf.name} not found")
            sys.exit(1)
        print(f"  OK: {pdf.name}")

    # Step 1: Find graphics pages
    print(f"\n{'='*70}")
    print("Шаг 1: Поиск страниц с графикой")
    print("=" * 70)

    all_tasks = []
    for pdf_path in TEST_PDFS:
        pages = find_graphics_pages(pdf_path, MAX_PAGES_PER_DOC)
        print(f"\n  {pdf_path.stem}:")
        for p in pages:
            print(f"    стр.{p['page']+1}: {p['drawings']} drawings, {p['images']} images, {p['text_lines']} text lines")
            all_tasks.append((pdf_path, p))

    print(f"\n  Итого: {len(all_tasks)} страниц для обработки")

    if not all_tasks:
        print("  Нет страниц с графикой. Завершение.")
        return

    # Step 2: Load model
    print(f"\n{'='*70}")
    print("Шаг 2: Загрузка DeepSeek-OCR")
    print("=" * 70)

    t_load = time.time()
    model, tokenizer = load_model()
    load_time = time.time() - t_load
    vram_model = get_vram_mb()
    print(f"  Загружено за {load_time:.1f}с, VRAM: {vram_model} MB")

    # Step 3: Inference
    print(f"\n{'='*70}")
    print("Шаг 3: Inference")
    print("=" * 70)

    results = []
    prompt_keys = ["document", "free_ocr"]

    for i, (pdf_path, page_info) in enumerate(all_tasks):
        page_num = page_info["page"]
        doc_name = pdf_path.stem

        print(f"\n{'─'*60}")
        print(f"[{i+1}/{len(all_tasks)}] {doc_name} стр.{page_num+1}")
        print(f"  ({page_info['drawings']} drawings, {page_info['images']} images)")
        print("─" * 60)

        image = render_page(pdf_path, page_num)
        print(f"  Image: {image.size[0]}x{image.size[1]}")

        page_results = {"doc": doc_name, "page": page_num + 1, "prompts": {}}

        for pk in prompt_keys:
            text, elapsed = run_inference(model, tokenizer, image, pk)
            vram_now = get_vram_mb()
            text_preview = text[:300].replace("\n", " ") if text else "(empty)"

            print(f"\n  Промпт: {pk.upper()}")
            print(f"  Время: {elapsed:.1f}с | VRAM: {vram_now} MB")
            print(f"  Длина: {len(text)} chars")
            print(f"  Превью: {text_preview}...")

            page_results["prompts"][pk] = {
                "time": round(elapsed, 1),
                "chars": len(text),
                "text": text[:500],
            }

        results.append(page_results)

    # Step 4: Unload
    print(f"\n{'='*70}")
    print("Шаг 4: Выгрузка модели")
    print("=" * 70)

    unload_model(model, tokenizer)
    vram_after = get_vram_mb()
    print(f"  VRAM после выгрузки: {vram_after} MB")

    # Summary
    print(f"\n{'='*70}")
    print("СВОДКА")
    print("=" * 70)

    total_time = sum(
        r["prompts"][pk]["time"]
        for r in results
        for pk in prompt_keys
        if pk in r["prompts"]
    )
    total_prompts = sum(len(r["prompts"]) for r in results)

    print(f"  Модель: DeepSeek-OCR (flash_attention_2, bf16)")
    print(f"  Загрузка: {load_time:.1f}с")
    print(f"  VRAM модели: {vram_model} MB")
    print(f"  Страниц: {len(results)}")
    print(f"  Промптов: {total_prompts}")
    print(f"  Общее время inference: {total_time:.1f}с")
    if total_prompts > 0:
        print(f"  Среднее время/промпт: {total_time/total_prompts:.1f}с")

    print(f"\n  По страницам:")
    for r in results:
        for pk, data in r["prompts"].items():
            tag = "[SLOW]" if data["time"] > 30 else "[OK]"
            print(f"    {tag} {r['doc'][:40]} стр.{r['page']}: {pk}={data['time']}с ({data['chars']} chars)")

    print(f"\n{'='*70}")
    print("POC завершён")
    print("=" * 70)


if __name__ == "__main__":
    main()
