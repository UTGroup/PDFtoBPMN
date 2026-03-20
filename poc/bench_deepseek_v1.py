#!/usr/bin/env python3
"""
OCR Benchmark: DeepSeek-OCR v1 baseline.

Run from DeepSeek-OCR/venv:
    /home/budnik_an/Obligations/DeepSeek-OCR/venv/bin/python poc/bench_deepseek_v1.py
"""

from __future__ import annotations

import gc
import io
import json
import time
from pathlib import Path

import fitz
import torch
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PAGES_FILE = PROJECT_ROOT / "poc" / "fixtures" / "benchmark_pages.json"
OUTPUT_FILE = PROJECT_ROOT / "poc" / "benchmark_results" / "deepseek_v1_baseline.json"
TMP_IMG = Path("/tmp/bench_ocr_tmp.png")
DPI = 200


def get_vram_mb() -> int:
    if torch.cuda.is_available():
        return round(torch.cuda.memory_allocated(0) / 1024**2)
    return 0


def render_page(pdf_path: str, page_num: int) -> Image.Image:
    doc = fitz.open(pdf_path)
    page = doc[page_num]
    mat = fitz.Matrix(DPI / 72, DPI / 72)
    pix = page.get_pixmap(matrix=mat)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    doc.close()
    return img.convert("RGB")


def main():
    print("=" * 60)
    print("Benchmark: DeepSeek-OCR v1 (baseline)")
    print("=" * 60)

    with open(PAGES_FILE, "r", encoding="utf-8") as f:
        pages = json.load(f)

    print(f"Pages: {len(pages)}")
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(f"VRAM before: {get_vram_mb()} MB")

    from transformers import AutoModel, AutoTokenizer

    print("\nLoading model...")
    t_load = time.time()
    tokenizer = AutoTokenizer.from_pretrained(
        "deepseek-ai/DeepSeek-OCR", trust_remote_code=True
    )
    model = AutoModel.from_pretrained(
        "deepseek-ai/DeepSeek-OCR",
        _attn_implementation="flash_attention_2",
        trust_remote_code=True,
        use_safetensors=True,
        torch_dtype=torch.bfloat16,
        device_map="cuda:0",
    )
    model = model.eval()
    load_time = round(time.time() - t_load, 1)
    vram_model = get_vram_mb()
    print(f"Loaded in {load_time}s, VRAM: {vram_model} MB")

    prompt = "<image>\nFree OCR. "

    results = []
    for i, page in enumerate(pages):
        doc_code = page["doc_code"]
        page_num = page["page_num"]
        page_type = page["page_type"]

        print(f"\n[{i+1}/{len(pages)}] {doc_code} p.{page_num+1} [{page_type}]")

        image = render_page(page["pdf_path"], page_num)
        image.save(str(TMP_IMG))

        t0 = time.time()
        text = model.infer(
            tokenizer,
            prompt=prompt,
            image_file=str(TMP_IMG),
            output_path="/tmp",
            base_size=1024,
            image_size=640,
            crop_mode=False,
            save_results=False,
            test_compress=False,
            eval_mode=True,
        )
        elapsed = round(time.time() - t0, 1)
        vram_now = get_vram_mb()

        if not isinstance(text, str):
            text = ""

        print(f"  Time: {elapsed}s | VRAM: {vram_now} MB | Chars: {len(text)}")
        preview = text[:200].replace("\n", " ") if text else "(empty)"
        print(f"  Preview: {preview}")

        results.append({
            "doc_code": doc_code,
            "page_num": page_num,
            "page_type": page_type,
            "model": "deepseek-ocr-v1",
            "prompt": "free_ocr",
            "text": text,
            "chars": len(text),
            "inference_time": elapsed,
            "vram_mb": vram_now,
        })

    TMP_IMG.unlink(missing_ok=True)

    del model
    del tokenizer
    gc.collect()
    torch.cuda.empty_cache()

    meta = {
        "model": "deepseek-ocr-v1",
        "model_id": "deepseek-ai/DeepSeek-OCR",
        "load_time": load_time,
        "vram_model_mb": vram_model,
        "prompt": prompt,
        "dpi": DPI,
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
