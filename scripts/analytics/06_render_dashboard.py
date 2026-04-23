#!/usr/bin/env python3
"""Сборка single-page HTML дашборда СФВ.

Берёт data/sfv_processed/dashboard_payload.json и подставляет в шаблон,
получает docs/dashboards/sfv_catering_dashboard.html (без внешних данных,
кроме CDN Plotly).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAYLOAD = ROOT / "data" / "sfv_processed" / "dashboard_payload.json"
TEMPLATE = Path(__file__).resolve().with_name("sfv_dashboard_template.html")
OUTPUT = ROOT / "docs" / "dashboards" / "sfv_catering_dashboard.html"


def main() -> int:
    if not PAYLOAD.exists():
        print(f"!! payload not found: {PAYLOAD}")
        return 1
    if not TEMPLATE.exists():
        print(f"!! template not found: {TEMPLATE}")
        return 1
    payload = PAYLOAD.read_text(encoding="utf-8")
    html = TEMPLATE.read_text(encoding="utf-8")
    html = html.replace("/*__PAYLOAD__*/null", payload)
    OUTPUT.write_text(html, encoding="utf-8")
    print(f"[OK] dashboard -> {OUTPUT}  ({OUTPUT.stat().st_size/1024:.1f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
