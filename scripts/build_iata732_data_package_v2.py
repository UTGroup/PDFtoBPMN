#!/usr/bin/env python3
"""TASK-015: пакет данных IATA-732 + AMOS-слой v2.

Собирает все артефакты (codifier, structure, levels_meta, lineage, matching,
cup_overlay, meridian_upgrade) + новые из TASK-014 (mer_amos_sources,
cup_zone2_to_amos, amos_apn_catalog, cup_zone2_amos_mapping_v1.md) в один
zip-архив для дашборда `/info/iata732/`.

Выход:
  output/iata732/iata732_data_package_v2.zip
  webBI/iata732/static/iata732_data_package_v2.zip  (копия для фронта)
"""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

ROOT = Path("/home/budnik_an/Obligations")
TODO_STATIC = Path("/home/budnik_an/todo/webBI/iata732/static")

OUT_ZIP = ROOT / "output" / "iata732" / "iata732_data_package_v2.zip"
README = ROOT / "output" / "iata732" / "iata732_data_package_v2_README.md"

FILES = [
    (ROOT / "output" / "iata732" / "codifier.json", "codifier.json"),
    (ROOT / "output" / "iata732" / "structure.json", "structure.json"),
    (ROOT / "output" / "iata732" / "levels_meta.json", "levels_meta.json"),
    (ROOT / "output" / "iata732" / "lineage.json", "lineage.json"),
    (ROOT / "output" / "cup_codifier" / "matching.json", "matching.json"),
    (ROOT / "output" / "cup_codifier" / "cup_overlay.json", "cup_overlay.json"),
    (ROOT / "output" / "cup_codifier" / "meridian_upgrade_v1.csv", "meridian_upgrade_v1.csv"),
    (ROOT / "output" / "amos_layer" / "mer_amos_sources.json", "mer_amos_sources.json"),
    (ROOT / "output" / "amos_layer" / "mer_amos_sources.csv", "mer_amos_sources.csv"),
    (ROOT / "output" / "amos_layer" / "cup_zone2_to_amos.json", "cup_zone2_to_amos.json"),
    (ROOT / "output" / "amos_layer" / "cup_zone2_to_amos.csv", "cup_zone2_to_amos.csv"),
    (ROOT / "output" / "amos_layer" / "amos_apn_catalog.json", "amos_apn_catalog.json"),
    (ROOT / "docs" / "reports" / "cup_zone2_amos_mapping_v1.md", "cup_zone2_amos_mapping_v1.md"),
    (README, "README.md"),
]


def main() -> None:
    print("── build_iata732_data_package_v2 ───────────────────────────────")
    missing = [src for src, _ in FILES if not src.exists()]
    if missing:
        raise SystemExit(f"Missing source files:\n  " + "\n  ".join(str(m) for m in missing))

    OUT_ZIP.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUT_ZIP, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for src, arc in FILES:
            z.write(src, arcname=f"iata732_data_package_v2/{arc}")
            print(f"  + {arc:40s} ({src.stat().st_size:>10,} B)")

    size = OUT_ZIP.stat().st_size
    print(f"\nWrote {OUT_ZIP}  ({size:,} B)")

    TODO_STATIC.mkdir(parents=True, exist_ok=True)
    shutil.copy2(OUT_ZIP, TODO_STATIC / OUT_ZIP.name)
    shutil.copy2(README, TODO_STATIC / README.name)
    print(f"Synced  → {TODO_STATIC / OUT_ZIP.name}")
    print(f"Synced  → {TODO_STATIC / README.name}")


if __name__ == "__main__":
    main()
