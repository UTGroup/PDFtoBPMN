#!/usr/bin/env python3
"""Resilient downloader for the public SFV trade reports Google Drive folder.

Source: https://drive.google.com/drive/folders/12peHCLTR91EQQnCSsHfS084mys0cAbMh
Target: data/sfv_trade_reports/<original folder name>/

Использует manifest sfv_reports_manifest.json со списком (file_id, имя файла),
поштучно качает с экспоненциальным back-off, обходя rate-limit Google.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

import gdown

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = Path(__file__).resolve().with_name("sfv_reports_manifest.json")
DEFAULT_DEST = ROOT / "data" / "sfv_trade_reports"


def download_one(file_id: str, out_path: Path, max_retries: int = 8) -> bool:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists() and out_path.stat().st_size > 0:
        return True
    url = f"https://drive.google.com/uc?id={file_id}"
    delay = 8.0
    for attempt in range(1, max_retries + 1):
        try:
            result = gdown.download(url, str(out_path), quiet=True)
            if result and Path(result).exists() and Path(result).stat().st_size > 0:
                return True
        except Exception as exc:  # noqa: BLE001
            print(f"   ! attempt {attempt} failed: {exc}", flush=True)
        if attempt < max_retries:
            sleep_for = delay + random.uniform(0, delay / 2)
            print(f"   . retry in {sleep_for:.1f}s", flush=True)
            time.sleep(sleep_for)
            delay = min(delay * 2, 240.0)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default=str(MANIFEST), type=Path)
    parser.add_argument("--dest", default=str(DEFAULT_DEST), type=Path)
    parser.add_argument("--throttle", type=float, default=2.0,
                        help="Пауза между файлами, сек")
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    subdir = manifest.get("subdir") or ""
    files = manifest["files"]
    target_dir = args.dest / subdir if subdir else args.dest
    target_dir.mkdir(parents=True, exist_ok=True)
    print(f"[i] Каталог: {target_dir}")
    print(f"[i] Всего файлов в манифесте: {len(files)}")

    failed: list[tuple[str, str]] = []
    skipped = downloaded = 0
    for idx, (file_id, fname) in enumerate(files, 1):
        out_path = target_dir / fname
        if out_path.exists() and out_path.stat().st_size > 0:
            skipped += 1
            continue
        print(f"[{idx}/{len(files)}] -> {fname}", flush=True)
        ok = download_one(file_id, out_path)
        if ok:
            downloaded += 1
        else:
            print(f"   X giving up: {fname}", flush=True)
            failed.append((file_id, fname))
        time.sleep(args.throttle)

    print("-" * 60)
    print(f"Скачано в этом запуске: {downloaded}")
    print(f"Пропущено (уже было):   {skipped}")
    print(f"Не удалось:             {len(failed)}")
    if failed:
        print("Список не скачанных:")
        for fid, name in failed:
            print(f"  - {name}  (id={fid})")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
