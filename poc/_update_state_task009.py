"""Временный scribe-скрипт: обновить LangGraph state для TASK-009 финализация."""
from __future__ import annotations

import sys
import importlib.util
import typing

# Загружаем dev_graph и регистрируем в sys.modules (нужно для get_type_hints)
spec = importlib.util.spec_from_file_location(
    "dev_graph",
    "/home/budnik_an/Obligations/.cursor/state/dev_graph.py",
)
mod = importlib.util.module_from_spec(spec)
sys.modules["dev_graph"] = mod  # ← ключевое: get_type_hints будет искать здесь
spec.loader.exec_module(mod)

DevGraph = mod.DevGraph
g = DevGraph()

# --- D-027 ---
g.log_decision(
    explicit_id="D-027",
    date="2026-05-04T23:00",
    title="NOT NULL для ORDER BY ключей в cup.flights",
    context=(
        "TASK-009 Phase A.2. ClickHouse не позволяет Nullable в ORDER BY "
        "без allow_nullable_key=1 — анти-паттерн производительности."
    ),
    decision=(
        "flight_no и dep_airport_iata: NOT NULL DEFAULT '' в schema.sql. "
        "ETL reader.py coalesce NaN/None → ''. "
        "Маркер '' = GAP (Rule 0 — разрыв виден в данных)."
    ),
    rejected=[
        "allow_nullable_key=1 — деградация skip-индексов",
        "Убрать из ORDER BY — теряем партиционирование и skip-индексы",
    ],
    revisit_if="Потребуется иной способ хранить unknown flight_no",
)

# --- D-028 ---
g.log_decision(
    explicit_id="D-028",
    date="2026-05-04T23:00",
    title="numeric coercion в reader.py",
    context=(
        "TASK-009 Phase B. Excel-источники содержат нечисловые значения "
        "(пробелы, n/a, —) в Int*/Float* колонках. Нормальная практика Excel."
    ),
    decision=(
        "INT_COLUMNS (44 колонки), FLOAT_COLUMNS (3 колонки). "
        "pd.to_numeric(errors='coerce') → NaN → NULL в CH. "
        "Для Int-колонок .round() (float-репрезентация int)."
    ),
    rejected=[
        "Строгая валидация — сбой ETL на реальных данных",
        "Сохранять нечисловые как строку — несовместимо с CH-типами",
    ],
    revisit_if="Нужен audit trail → добавить coerced-counter в reader.py",
)

# --- Компонент cup_dashboard ---
g._invoke("update_component", {
    "name": "cup_dashboard",
    "status": "done",
    "tests_pass": True,
    "task": "TASK-009",
    "note": "533344 строк cup.flights. FastAPI+ECharts SPA. Деплой: /info/tsup/.",
    "gaps": [
        "rz_causes_*.year=NULL (нет маппинга из источника)",
        "rz_causes_2019 отложен (D-026)",
        "pps_column1_unknown (анонимная колонка)",
        "avg_load_factor 2026=NULL (не заполнено в источнике)",
    ],
})

# --- Handoff'ы ---
g.log_handoff(
    "H7", "orchestrator", "scribe", "TASK-009",
    summary="Финализация TASK-009: D-027 D-028; Phases A+B+C+D+E done; 533344 строк; деплой /info/tsup/",
    result="PASS",
)
g.log_handoff(
    "H8", "scribe", "orchestrator", "TASK-009",
    summary="DECISIONS: D-027 D-028 confirmed. CURRENT_STATE: актуально. LangGraph: cup_dashboard=done.",
    result="PASS",
)

# --- Phase ---
g.update_phase("0_cup_dashboard_done", "TASK-009: cup_dashboard live", "done")

# --- Проверка ---
state = g.get_state()
print(f"phase:        {state.get('phase')}")
print(f"current_task: {state.get('current_task')}")
print(f"task_status:  {state.get('task_status')}")
decisions = state.get("decisions", [])
print(f"decisions count: {len(decisions)}")
print(f"decision IDs:    {[d.get('id') for d in decisions]}")
handoffs = state.get("handoffs", [])
print(f"handoffs count:  {len(handoffs)}")
comp = state.get("components", {}).get("cup_dashboard", {})
print(f"cup_dashboard: status={comp.get('status')}, tests_pass={comp.get('tests_pass')}")
print(f"  note: {comp.get('note')}")
print(f"  gaps: {comp.get('gaps')}")
print("OK")
