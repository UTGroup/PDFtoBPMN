# Решения проекта PDFtoBPMN v2.1

> Append-only. Scribe добавляет. Orchestrator читает перед каждым планом.
> Изменить решение = добавить новое с пометкой "supersedes D-NNN".

## D-001: Graph as SSOT (18.03.2026)
**Контекст:** 410 документов СМК — нужна машиночитаемая модель организации, а не просто парсинг PDF.
**Решение:** Organizational knowledge graph — единственный источник истины. BPMN, RAG, RACI, KPI — views из графа.
**Отклонено:** Два отдельных контура (Knowledge Base + Process Model), ProcessSpec как промежуточный формат.
**Вернуться если:** graph population оказывается unreliable на реальных документах.

## D-002: Knowledge graph НЕ убран из MVP (18.03.2026)
**Контекст:** Ранее было решение убрать graph из MVP. Пересмотрено: граф — это продукт, не компонент RAG.
**Решение:** NetworkX + SQLite в MVP. BPMN и management views рендерятся из графа. LightRAG оценивается в POC.
**Отклонено:** Metadata-rich chunks в ChromaDB как единственный storage.
**Supersedes:** Решение об убирании graph из MVP.

## D-003: OCR — POC решает (18.03.2026)
**Контекст:** EasyOCR vs RapidOCR. Оба через Docling. Tesseract исключён.
**Решение:** POC на 10 документах, 5 сценариев, Levenshtein ≥95%/≥90%. Победитель — единственный OCR.
**Отклонено:** Tesseract (слабый на русском + таблицы).

## D-004: LLM стратегия — Cursor + Claude API (18.03.2026)
**Контекст:** Нет локального LLM 72B/32B. GPU только для Qwen VL-7B.
**Решение:** Dev: Cursor AI (Opus/Composer/Auto). Batch: Claude API sonnet-4-6 (~$210). VLM: Qwen VL-7B.
**Отклонено:** Qwen 72B/32B локально, LangGraph Platform/Cloud.

## D-005: 4 агента + hooks enforcement (18.03.2026)
**Контекст:** Helicomponents паттерн: архитектор → исполнитель → ревьюер → верификатор.
**Решение:** Orchestrator (Opus 0.2), Coder (Auto/Composer 0.4), Validator (Composer 0.0), Scribe (Composer 0.0). Hooks блокируют без handoff.
**Отклонено:** 3 агента (scribe + validator в одном), 7 агентов.

## D-006: Handoff protocol H1-H9 (18.03.2026)
**Контекст:** Без формализованных handoff'ов агенты дрейфуют, state рассинхронизируется.
**Решение:** 9 handoff'ов, каждый записывается в LangGraph. Hooks блокируют агента без предыдущего handoff.
**Отклонено:** Convention-based (правила без enforcement).

## D-007: Git model — ветка + коммиты (18.03.2026)
**Контекст:** Нужна изоляция работы от main, но без overhead веток на каждую задачу.
**Решение:** Ветка v2-graphrag. 1 задача = 1 коммит. Human коммитит после H9. Merge в main по phase gate.
**Отклонено:** Feature branches per task, trunk-based.

## D-008: PyMuPDF исключён (18.03.2026)
**Контекст:** AGPL лицензия несовместима с потенциальным коммерческим использованием.
**Решение:** Docling + docling-parse (MIT).
**Отклонено:** PyMuPDF (AGPL).

## D-009: Unified pipeline — не два контура (18.03.2026)
**Контекст:** Два контура (A: Knowledge Base, B: Process Model) усложняют архитектуру, дублируют extraction.
**Решение:** Один pipeline: ingestion → extraction → graph population + text indexing. Views (BPMN, RACI, KPI) из графа.
**Отклонено:** Контуры A и B как отдельные pipelines.

## D-010: ProcessSpec убран как промежуточный формат (18.03.2026)
**Контекст:** ProcessSpec.yaml был intermediate format между extraction и BPMN compiler.
**Решение:** Граф = source of truth. BPMN compiler читает graph query напрямую.
**Отклонено:** ProcessSpec.yaml как обязательный промежуточный файл.

## D-011: 5 агентов — добавлен extractor (18.03.2026)
**Контекст:** LLM-based extraction (6 типов: Role, ProcessStep, DecisionRule, KPI, Control, InputOutput) требует LLM. Claude API пока нет — используем Cursor AI. Нужен специализированный агент с детерминированным промптом (temp 0.0) и строгим JSON-выводом.
**Решение:** Добавлен 5-й агент `extractor` (Sonnet 4.6, temp 0.0). Вызывается orchestrator'ом при рабочем прогоне и тестах. Read-only, AS-IS, provenance обязательна.
**Отклонено:** Extraction как роль coder'а (менее изолированно, нет воспроизводимых промптов).
**Supersedes:** D-005 (было 4 агента, стало 5).

## D-012: OCR backend — EasyOCR (18.03.2026)
**Контекст:** D-003 требовал POC для выбора OCR. Сравнение EasyOCR vs RapidOCR через Docling pipeline на 4 реальных PDF (русский текст СМК), 5 сценариев (native, full OCR, mixed, tables, graphics).
**Результаты POC (4 документа, 8-253 стр, 465KB-9.3MB):**
- EasyOCR: avg similarity 85-98%, force OCR 70-87%, mixed 100%. lang=["ru","en"], GPU.
- RapidOCR: avg similarity 59-74%, force OCR 18-48% (модели ch_PP-OCRv4 — китайский), mixed 100%.
- Скорость сравнимая, EasyOCR чуть медленнее (~10 мин на 253 стр full OCR).
**Решение:** EasyOCR — единственный OCR backend. Интеграция через Docling `EasyOcrOptions(lang=["ru","en"], use_gpu=True)`.
**Отклонено:** RapidOCR (критически плохое качество на русском тексте — 18-48% similarity при force OCR).
**Артефакт:** `poc/poc_ocr_comparison.py`, `poc/ocr_comparison_report.json`.

## D-013: NetworkXGraphStore — MVP реализация GraphStore Protocol (18.03.2026)
**Контекст:** D-001 определил Graph as SSOT, core/stores.py зафиксировал GraphStore Protocol. Требовалось POC для проверки end-to-end: загрузка артефактов → граф → query views (BPMN, RACI).
**Результаты POC (КД-РГ-039-05, Направление 2 — Просроченная ДЗ):**
- NetworkXGraphStore: 10 методов (add_artifact, add_relation, query_process, query_raci, query_kpi, query_controls, query_for_rag, query_neighbors, save, load).
- Fixture: 17 артефактов (5 Role, 8 ProcessStep, 2 DecisionRule, 2 InputOutput), 31 relation (RACI + sequence + decision + outputs).
- query_process: 5 ролей, 8 шагов, 2 решения, 9 потоков — структура пригодна для BPMN compiler.
- query_raci: 8 строк матрицы, 90% совпадение с существующим КД-РГ-039-05_RACI.md (порог 80% — PASS).
- Round-trip save/load: JSON 17.6KB, 0 потерь — PASS.
**Решение:** NetworkX MultiDiGraph — реализация GraphStore для Фазы 1-2. Перенос в scripts/graph/ при Фазе 2.
**Артефакт:** `poc/poc_graph_population.py`, `poc/fixtures/kd_rg_039_05_artifacts.json`, `poc/graph_КД-РГ-039-05.json`.

## D-014: Document Authority — парсер кодов и реестр семейств (18.03.2026)
**Контекст:** Архитектура v2.1 определяет Document Authority Model (canonical/superseded/draft). Нужен парсер кодов документов СМК для автоматического определения семейств и версий.
**Результаты POC (output/, 369 документов):**
- 10 паттернов парсинга покрывают 100% кодов (323/323 OCR файлов).
- 329 уникальных семейств, 11 типов документов.
- 9 дубликатов между output/[код]/ и ocr_full_run/ (одна версия в двух местах).
- 1 мультиверсионное семейство (РИ-М1.005: v6=superseded, v7=canonical).
**Решение:** Парсер кодов и DocumentRegistry готовы для интеграции в ingestion pipeline (Фаза 2). При миграции на v2: ocr_full_run/ → архив, обработанные папки → canonical source.
**Артефакт:** `poc/poc_document_authority.py`, `poc/document_registry.json`.

## D-015: Разделение output v1 и v2 (18.03.2026)
**Контекст:** В output/ лежат результаты прогонов v1 (14 обработанных папок + 323 OCR в ocr_full_run/). v2 pipeline будет генерировать новые артефакты. Смешивание v1 и v2 output недопустимо — разные форматы, разное качество, разная структура.
**Решение:**
- `output/` — остаётся как есть, read-only. Ориентир для сравнения v2 с v1.
- v2 pipeline пишет результаты в отдельную директорию (конкретное имя определяется при Фазе 2).
- Старые данные не блокируют рефакторинг и не являются canonical source для v2.
- При Gold Standard: v2 генерирует черновики → аналитики правят → эталоны возвращаются как ground truth.
**Отклонено:** Перезапись v1 output новыми данными v2; миграция ocr_full_run/ в папки (не нужно сейчас).

## D-016: Page Classifier — rule-based эвристики (18.03.2026)
**Контекст:** Pipeline v2.1 требует классификации страниц PDF для routing: cover/approval_sheet → metadata only, appendix → отдельный парсинг, content → full extraction.
**Результаты POC (5 PDF, 397 страниц):**
- 4 типа: cover (2.5%), content (86.6%), appendix (10.1%), approval_sheet (0.8%).
- Эвристики: ключевые слова (УТВЕРЖДАЮ, Лист согласования, Приложение), позиция страницы, плотность текста, OCR-паттерны для сканов.
- Cover детектируется на стр. 1-2 всех документов (скан-обложка + предисловие).
- Approval sheet найден в 2 из 5 документов (последние страницы с подписями).
- Appendix корректно определяется после маркера "Приложение".
**Решение:** Rule-based PageClassifier готов для интеграции в ingestion pipeline (Фаза 2). ML-подход не нужен — эвристики достаточны для СМК документов с предсказуемой структурой.
**Артефакт:** `poc/poc_page_classifier.py`.

## D-017: Qwen VLM — 2B для dev, 7B для production (19.03.2026)
**Контекст:** Архитектура v2.1 определяет Qwen2.5-VL для описания графики (блок-схемы, диаграммы) из PDF. POC проверил 2B модель на реальных документах.
**Результаты POC (3 PDF, 15 страниц с графикой, 30 промптов):**
- Qwen2-VL-2B-Instruct: 4.2GB VRAM, 14.4с/промпт, загрузка 6.3с.
- Титульные страницы: хорошо извлекает текст (название, даты, номера).
- Реальные схемы: слабо — шаблонные описания, галлюцинации BPMN-элементов, зацикливание на длинных ответах.
- BPMN-промпт: более структурированный, но менее точный ответ.
**Решение:** Qwen2-VL-2B — для dev/быстрых проверок. Qwen2-VL-7B или Qwen2.5-VL-7B — для production (требует 16GB VRAM, тестировать при Фазе 2).
**Артефакт:** `poc/poc_qwen_graphics.py`.

## D-018: OCR/VLM Benchmark — 7 моделей, DeepSeek-OCR v1 остаётся лидером (20.03.2026)
**Контекст:** Исследование лучших практик OCR/VLM выявило 6 альтернативных моделей. Проведён полный бенчмарк на 18 страницах из 4 реальных PDF (text, table, diagram, mixed, cover). DeepSeek-OCR v1 — baseline.
**Результаты бенчмарка (Levenshtein similarity к baseline):**

| # | Модель | Similarity | с/стр | VRAM MB | Параметры | venv |
|---|--------|-----------|-------|---------|-----------|------|
| 1 | DeepSeek-OCR v1 (baseline) | 100.0% | 40.1 | 6456 | ~3B | DeepSeek-OCR/venv |
| 2 | GLM-OCR | 63.2% | 10.6 | 2112 | 0.9B | ocr_bench_venv |
| 3 | DeepSeek-OCR v2 | 51.3% | 20.6 | 6562 | ~3B | DeepSeek-OCR/venv |
| 4 | GOT-OCR2 | 51.1% | 21.5 | 1069 | 580M | ocr_bench_venv |
| 5 | PaddleOCR-VL-1.5 | 48.7% | 189.7 | 1738 | 0.9B | ocr_bench_venv |
| 6 | SmolDocling-256M | 31.7% | 41.7 | 489 | 256M | venv |
| 7 | EasyOCR (Docling) | n/a | 61.9 | ~0 | — | venv |

**Известные проблемы:**
- DeepSeek-OCR v1/v2: зацикливание генерации на ~9% страниц (known issue #151 v1, #42 v2). Guardrails не помогают.
- DeepSeek-OCR v2: поддерживает только image_size=768/1024 (не 640). crop_mode=True — официальная рекомендация.
- PaddleOCR-VL-1.5: аномально медленный на SDPA (189.7с/стр).
- EasyOCR через Docling: обрабатывает целый PDF, прямое сравнение по страницам невозможно.
- GOT-OCR2: плохо работает с кириллицей (артефакты транслитерации).
- Levenshtein similarity — грубая метрика, не учитывает семантику.

**Инфраструктура (3 venv):**
- `DeepSeek-OCR/venv/`: transformers 4.46.3 + flash-attn 2.7.3 → DeepSeek-OCR v1, v2
- `venv/`: transformers 4.57.6 → EasyOCR (Docling), SmolDocling-256M
- `ocr_bench_venv/`: transformers 5.3.0 + torch 2.10+cu129 → GLM-OCR, PaddleOCR-VL, GOT-OCR2

**Решение:** DeepSeek-OCR v1 — primary OCR для production. GLM-OCR — fast fallback (4x быстрее, 3x меньше VRAM, 63% quality). Ансамбль и дальнейшее тестирование — Фаза 2.
**Отклонено:** DeepSeek-OCR v2 как замена v1 (хуже на наших документах). PaddleOCR-VL (слишком медленный). SmolDocling (слишком маленький для сложных документов).
**Артефакты:** `poc/benchmark_results/` (7 JSON + summary.json), `poc/fixtures/benchmark_pages.json`, `poc/bench_*.py` (9 скриптов).
