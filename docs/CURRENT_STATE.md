# Текущее состояние

## Фаза: 0_setup (мультиагент + архитектура)
## Задача: TASK-006 — POC Qwen VLM описание графики
## Статус: completed
## Ветка: v2-graphrag

### Компоненты
- ✅ **cursor_rules**: 7 .mdc файлов (v1 удалены, v2 синхронизированы с DECISIONS)
- ✅ **cursor_hooks**: 4 хука — синтаксис OK, базовая логика OK, executable
- ✅ **cursor_agents**: 5 агентов (orchestrator, coder, validator, scribe, extractor)
- ✅ **langgraph_state**: dev_graph + batch_graph — pip install OK, 6/6 тестов pass
- ✅ **docs**: Architecture_v2.1, DECISIONS (D-001..D-012), Handoff Protocol — готовы
- ✅ **core_types**: KnowledgeType (13), EdgeType (19), GraphStore/VectorStore Protocol — импорт OK
- ✅ **docling**: v2.80.0 — парсит PDF, таблицы, структуру
- ✅ **easyocr**: v1.7.2 — OCR winner (D-012), lang=["ru","en"], GPU

### Сделано
- Bootstrap v2.1 выполнен (ветка v2-graphrag, 2 коммита)
- SqliteSaver API исправлен (langgraph v1.1+ совместимость)
- dev_state.sqlite инициализирован (phase: 0_setup)
- setupv2/ сохранён как архивная копия
- TASK-001 валидация: 11/11 проверок PASS
- TASK-002 POC OCR: EasyOCR победитель (D-012), RapidOCR отклонён (18-31% на русском)
  - docling 2.80.0 + easyocr 1.7.2 + rapidocr 3.7.0 + onnxruntime 1.23.2 установлены
  - 2 PDF протестированы, 5 сценариев x 2 OCR = 10 прогонов
  - Артефакты: poc/poc_ocr_comparison.py, poc/ocr_comparison_report.json
- TASK-003 POC Graph Population: NetworkXGraphStore реализован, все критерии PASS
  - NetworkXGraphStore: 10 методов (add_artifact, add_relation, query_process, query_raci, query_kpi, query_controls, query_for_rag, query_neighbors, save, load)
  - Fixture: 17 артефактов (5 Role, 8 ProcessStep, 2 DecisionRule, 2 InputOutput), 31 relation
  - query_process: 5 ролей, 8 шагов, 2 решения, 9 потоков — структура пригодна для BPMN compiler
  - query_raci: 90% совпадение с существующим КД-РГ-039-05_RACI.md (порог 80% — PASS)
  - Round-trip save/load: JSON 17.6KB, без потерь — PASS
  - Артефакты: poc/poc_graph_population.py, poc/fixtures/kd_rg_039_05_artifacts.json, poc/graph_КД-РГ-039-05.json
- TASK-004 POC Document Authority: парсер кодов + реестр семейств + conflict detection
  - DocumentCodeParser: 10 паттернов, 323/323 = 100% распознавание кодов
  - DocumentRegistry: 329 семейств, 369 документов, 11 типов (ДП, РГ, ИОТ, РД, СТ, РИ, РК, СТО, ПР, TPM, unknown)
  - Authority resolver: canonical/superseded/draft, 1 мультиверсионное семейство (РИ-М1.005)
  - Conflict detection: 9 дубликатов между output/[код]/ и ocr_full_run/
  - Артефакты: poc/poc_document_authority.py, poc/document_registry.json
- TASK-005 POC Page Classifier: rule-based классификатор страниц PDF
  - 4 типа: cover, content, appendix, approval_sheet
  - Тестирование на 5 реальных PDF (397 страниц): cover 10 (2.5%), content 344 (86.6%), appendix 40 (10.1%), approval_sheet 3 (0.8%)
  - Эвристики: ключевые слова, позиция страницы, плотность текста, OCR-паттерны
  - Артефакт: poc/poc_page_classifier.py
- TASK-006 POC Qwen VLM: описание графики из PDF через Qwen2-VL-2B
  - GPU: RTX 5080, модель Qwen2-VL-2B-Instruct (4.2GB VRAM)
  - 3 PDF, 15 страниц с графикой, 30 промптов (общий + BPMN)
  - Среднее время inference: 14.4с/промпт, загрузка модели: 6.3с
  - Качество 2B модели: извлекает текст с титульных страниц, но слаба на реальных схемах (галлюцинации, зацикливание)
  - Вывод: для production нужна 7B модель; 2B — только для быстрых проверок
  - Артефакт: poc/poc_qwen_graphics.py

- TASK-007 OCR/VLM Benchmark: 7 моделей протестированы на 18 страницах из 4 PDF (D-018)
  - DeepSeek-OCR v1 — лидер (baseline, 100%)
  - GLM-OCR — лучший баланс скорость/качество (63.2%, 10.6с/стр, 2.1GB VRAM)
  - DeepSeek-OCR v2 — хуже v1 на наших документах (51.3%, зацикливание генерации — known issue)
  - GOT-OCR2 — экономичный (51.1%, 1GB VRAM), но плохо с кириллицей
  - PaddleOCR-VL-1.5 — аномально медленный (189.7с/стр)
  - SmolDocling-256M — слишком маленький (31.7%)
  - EasyOCR (Docling) — обрабатывает целый PDF, прямое сравнение невозможно
  - Инфраструктура: 3 venv (DeepSeek-OCR/venv, venv, ocr_bench_venv)
  - Артефакты: poc/benchmark_results/ (7 JSON + summary.json), poc/bench_*.py (9 скриптов)

### Следующее
- Фаза 0 POC завершена. Следующий шаг: планирование Фазы 1 (production pipeline).
- OCR стратегия определена (D-018): DeepSeek-OCR v1 primary, GLM-OCR fast fallback.
- Ансамбль OCR моделей — Фаза 2.
- Qwen-7B VLM тестирование — на машине с RTX 5090 (дома).
- Отложено: POC 2 (LightRAG, нет API) → Фаза 3, POC 5 (BS) → Фаза 4

### Блокеры
- Нет

### Последние handoff'ы
- H1: Human → Orchestrator (18.03.2026) — /start, валидация развёртывания
- H9: Orchestrator → Human (18.03.2026) — TASK-001 completed, 11/11 PASS
- H9: Orchestrator → Human (18.03.2026) — TASK-002 completed, EasyOCR winner (D-012)
- H9: Orchestrator → Human (18.03.2026) — TASK-003 completed, Graph Population POC all PASS
- H9: Orchestrator → Human (18.03.2026) — TASK-004 completed, Document Authority POC all PASS
- H9: Orchestrator → Human (18.03.2026) — TASK-005 completed, Page Classifier POC 397 pages classified
- H9: Orchestrator → Human (19.03.2026) — TASK-006 completed, Qwen VLM POC: 2B работает, для production нужна 7B
- H10: Orchestrator → Human (20.03.2026) — TASK-007 completed, OCR/VLM Benchmark: 7 моделей, D-018
