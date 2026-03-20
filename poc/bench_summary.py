#!/usr/bin/env python3
"""
Generate OCR/VLM benchmark summary.

Compares all model results against DeepSeek-OCR v1 baseline.
Outputs: poc/benchmark_results/summary.json
"""

from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = PROJECT_ROOT / "poc" / "benchmark_results"
BASELINE_FILE = RESULTS_DIR / "deepseek_v1_baseline.json"
OUTPUT_FILE = RESULTS_DIR / "summary.json"

MODEL_FILES = {
    "deepseek-ocr-v1": "deepseek_v1_baseline.json",
    "deepseek-ocr-v2": "deepseek_v2.json",
    "easyocr-docling": "easyocr.json",
    "smoldocling-256m": "smoldocling.json",
    "paddleocr-vl-1.5": "paddleocr_vl.json",
    "glm-ocr": "glm_ocr.json",
    "got-ocr2": "got_ocr2.json",
}


def levenshtein_similarity(s1: str, s2: str) -> float:
    if not s1 and not s2:
        return 100.0
    if not s1 or not s2:
        return 0.0

    s1_clean = " ".join(s1.split())
    s2_clean = " ".join(s2.split())

    if len(s1_clean) > 5000 or len(s2_clean) > 5000:
        s1_clean = s1_clean[:5000]
        s2_clean = s2_clean[:5000]

    m, n = len(s1_clean), len(s2_clean)
    if m == 0 and n == 0:
        return 100.0

    prev = list(range(n + 1))
    for i in range(1, m + 1):
        curr = [i] + [0] * n
        for j in range(1, n + 1):
            cost = 0 if s1_clean[i - 1] == s2_clean[j - 1] else 1
            curr[j] = min(curr[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost)
        prev = curr

    distance = prev[n]
    max_len = max(m, n)
    return round((1 - distance / max_len) * 100, 1)


def main():
    print("=" * 60)
    print("OCR/VLM Benchmark Summary")
    print("=" * 60)

    with open(BASELINE_FILE, "r", encoding="utf-8") as f:
        baseline_data = json.load(f)

    baseline_texts = {}
    for r in baseline_data["results"]:
        key = f"{r['doc_code']}_{r['page_num']}"
        baseline_texts[key] = r["text"]

    model_summaries = []

    for model_name, filename in MODEL_FILES.items():
        filepath = RESULTS_DIR / filename
        if not filepath.exists():
            print(f"  SKIP: {model_name} ({filename} not found)")
            continue

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        meta = data["meta"]
        results = data["results"]

        similarities = []
        page_details = []

        for r in results:
            key = f"{r['doc_code']}_{r['page_num']}"
            baseline_text = baseline_texts.get(key, "")
            model_text = r.get("text", "")

            if model_name == "easyocr-docling":
                sim = 0.0
            else:
                sim = levenshtein_similarity(baseline_text, model_text)

            similarities.append(sim)
            page_details.append({
                "doc_code": r["doc_code"],
                "page_num": r["page_num"],
                "page_type": r["page_type"],
                "similarity": sim,
                "chars": r["chars"],
                "inference_time": r["inference_time"],
            })

        avg_sim = round(sum(similarities) / len(similarities), 1) if similarities else 0
        total_time = meta.get("total_inference_time", 0)
        avg_time = meta.get("avg_inference_time", 0)
        load_time = meta.get("load_time", 0)
        vram = meta.get("vram_model_mb", 0)

        by_type: dict[str, list[float]] = {}
        for pd in page_details:
            by_type.setdefault(pd["page_type"], []).append(pd["similarity"])

        type_avg = {}
        for t, sims in by_type.items():
            type_avg[t] = round(sum(sims) / len(sims), 1)

        summary = {
            "model": model_name,
            "model_id": meta.get("model_id", ""),
            "avg_similarity": avg_sim,
            "avg_inference_time": avg_time,
            "total_inference_time": total_time,
            "load_time": load_time,
            "vram_model_mb": vram,
            "pages_count": len(results),
            "similarity_by_type": type_avg,
            "page_details": page_details,
        }

        model_summaries.append(summary)
        print(f"\n  {model_name}:")
        print(f"    Similarity: {avg_sim}%")
        print(f"    Speed: {avg_time}s/page")
        print(f"    VRAM: {vram} MB")
        print(f"    By type: {type_avg}")

    model_summaries.sort(key=lambda x: x["avg_similarity"], reverse=True)

    output = {
        "benchmark": {
            "baseline": "deepseek-ocr-v1",
            "pages_count": len(baseline_texts),
            "models_count": len(model_summaries),
        },
        "ranking": [
            {
                "rank": i + 1,
                "model": s["model"],
                "similarity": s["avg_similarity"],
                "speed": s["avg_inference_time"],
                "vram": s["vram_model_mb"],
            }
            for i, s in enumerate(model_summaries)
        ],
        "models": model_summaries,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print("RANKING (by similarity to baseline):")
    print(f"{'='*60}")
    print(f"{'#':<4} {'Model':<22} {'Sim%':<8} {'s/page':<10} {'VRAM MB':<10}")
    print("-" * 54)
    for r in output["ranking"]:
        print(f"{r['rank']:<4} {r['model']:<22} {r['similarity']:<8} {r['speed']:<10} {r['vram']:<10}")

    print(f"\n  Saved: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
