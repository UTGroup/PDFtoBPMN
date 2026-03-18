# TASK-001: Валидация развёртывания мультиагентной среды

## Цель
Проверить что мультиагентная среда v2.1 полностью работоспособна после bootstrap.
Зафиксировать результат в CURRENT_STATE.md и dev_state.sqlite.

## Scope

### Файлы: ПРОВЕРИТЬ (read-only)
- `.cursor/hooks/hooks.json` — формат корректен, 4 события
- `.cursor/hooks/*.py` — executable, синтаксис валиден
- `.cursor/rules/*.mdc` — все 12 файлов загружаются, нет конфликтов globs между v1 и v2
- `.cursor/agents/*.md` — все 10 файлов (4 v2 + 6 v1) валидны
- `.cursor/state/dev_graph.py` — SqliteSaver API работает
- `.cursor/state/batch_graph.py` — SqliteSaver API работает
- `core/` — imports работают, типы корректны
- `tests/test_dev_graph.py` — 6/6 pass

### Файлы: ИЗМЕНИТЬ (scribe)
- `docs/CURRENT_STATE.md` — обновить статусы компонентов по результатам валидации

### ТЕСТЫ
- `pytest tests/test_dev_graph.py -v` — 6/6 pass
- `python3 -c "from core.knowledge_types import KnowledgeType; print(len(KnowledgeType))"` — 13
- `python3 -c "from core.edge_types import EdgeType; print(len(EdgeType))"` — 18
- `python3 -c "from core.stores import GraphStore, VectorStore"` — no error
- `python3 .cursor/hooks/check_handoff.py < /dev/null` — exit 0 (no agent = pass)
- `python3 .cursor/hooks/check_ownership.py < /dev/null` — exit 0 (no agent = pass)
- `python3 .cursor/hooks/block_orchestrator_code.py < /dev/null` — exit 0 (no agent = pass)
- Проверка синтаксиса: `python3 -m py_compile .cursor/hooks/*.py`

## Non-goals
- НЕ начинать POC (Фаза 0 POC — отдельная задача)
- НЕ менять архитектуру или код
- НЕ менять rules (human only)
- НЕ удалять v1 rules/agents (они сохранены для обратной совместимости)

## Инварианты
- dev_state.sqlite содержит D-001 (Bootstrap complete)
- Все 6 тестов dev_graph проходят
- Код v1 (scripts/pdf_to_context/, scripts/document_graph/) не затронут

## Критерии успеха
1. Все тесты и проверки из секции ТЕСТЫ — PASS
2. CURRENT_STATE.md обновлён с актуальными статусами
3. dev_state.sqlite обновлён: phase 0_setup, task TASK-001 completed

## Ownership
- **coder**: запуск тестов и проверок (H4 dispatch)
- **scribe**: обновление CURRENT_STATE.md и dev_state (H7 dispatch)

## Риски
1. Hooks могут не работать в реальном Cursor (API зависит от версии IDE) — LOW
   Митигация: проверяем синтаксис и базовую логику, полный тест hooks — при первом реальном dispatch
2. Конфликт globs между v1 и v2 rules — LOW
   Митигация: v2 rules имеют специфичные globs (scripts/ingestion/**, core/**), v1 — более общие
