# OCR/VLM Benchmark — Handoff для продолжения

> **Дата:** 20.03.2026
> **Машина:** RTX 5080 16GB, WSL2, Ubuntu
> **Статус:** Бенчмарк завершён, результаты зафиксированы

---

## Итоговый рейтинг

| # | Модель | Similarity | с/стр | VRAM MB | venv |
|---|--------|-----------|-------|---------|------|
| 1 | DeepSeek-OCR v1 (baseline) | 100.0% | 40.1 | 6456 | DeepSeek-OCR/venv |
| 2 | GLM-OCR | 63.2% | 10.6 | 2112 | ocr_bench_venv |
| 3 | DeepSeek-OCR v2 | 51.3% | 20.3 | 6562 | DeepSeek-OCR/venv |
| 4 | GOT-OCR2 | 51.1% | 21.5 | 1069 | ocr_bench_venv |
| 5 | PaddleOCR-VL-1.5 | 48.7% | 189.7 | 1738 | ocr_bench_venv |
| 6 | SmolDocling-256M | 31.7% | 41.7 | 489 | venv |
| 7 | EasyOCR (Docling) | n/a | 61.9 | ~0 | venv |

Similarity = Levenshtein к DeepSeek-OCR v1 baseline. Метрика грубая (не семантическая).

---

## Артефакты

### Результаты
- `poc/benchmark_results/summary.json` — агрегированный отчёт с рейтингом
- `poc/benchmark_results/deepseek_v1_baseline.json` — baseline (ground truth)
- `poc/benchmark_results/deepseek_v2.json` — v2 с crop_mode=True (корректный прогон)
- `poc/benchmark_results/glm_ocr.json`
- `poc/benchmark_results/got_ocr2.json`
- `poc/benchmark_results/paddleocr_vl.json`
- `poc/benchmark_results/smoldocling.json`
- `poc/benchmark_results/easyocr.json`

### Скрипты
- `poc/bench_deepseek_v1.py` — baseline скрипт
- `poc/bench_deepseek_v2.py` — v2 (crop_mode=True, image_size=768)
- `poc/bench_glm_ocr.py` — GLM-OCR
- `poc/bench_got_ocr2.py` — GOT-OCR2
- `poc/bench_paddleocr_vl.py` — PaddleOCR-VL-1.5
- `poc/bench_smoldocling.py` — SmolDocling-256M
- `poc/bench_easyocr.py` — EasyOCR через Docling
- `poc/bench_summary.py` — генерация summary.json
- `poc/prepare_benchmark_pages.py` — подготовка тестового набора

### Тестовый набор
- `poc/fixtures/benchmark_pages.json` — 18 страниц из 4 PDF (text, table, diagram, mixed, cover_scan)

---

## Инфраструктура: 3 venv

| venv | transformers | torch | Модели |
|------|-------------|-------|--------|
| `DeepSeek-OCR/venv/` | 4.46.3 | 2.5.1+cu124 | DeepSeek-OCR v1, v2 (+ flash-attn 2.7.3) |
| `venv/` | 4.57.6 | 2.6.0+cu126 | EasyOCR (Docling), SmolDocling-256M |
| `ocr_bench_venv/` | 5.3.0 | 2.10.0+cu129 | GLM-OCR, PaddleOCR-VL, GOT-OCR2 |

**Запуск скриптов:**
```bash
# DeepSeek v1/v2:
DeepSeek-OCR/venv/bin/python poc/bench_deepseek_v1.py

# SmolDocling / EasyOCR:
source venv/bin/activate && python poc/bench_smoldocling.py

# GLM-OCR / PaddleOCR / GOT-OCR2:
ocr_bench_venv/bin/python poc/bench_glm_ocr.py
```

---

## Известные проблемы и решения

### DeepSeek-OCR v1/v2 — зацикливание генерации
- **GitHub:** v1 issue #151, v2 issue #42 — known, unresolved
- **Частота:** ~9% страниц (2 из 18 в нашем тесте)
- **Workaround:** `max_new_tokens` ограничивает длину, но не предотвращает повторы
- **crop_mode=True** — официальная рекомендация для v2

### DeepSeek-OCR v2 — ограничения image_size
- Поддерживает ТОЛЬКО `image_size=768` или `image_size=1024`
- `image_size=640` вызывает `UnboundLocalError` в `deepencoderv2.py` (param_img не определён для n_query, не соответствующего 768/1024)

### PaddleOCR-VL-1.5 — transformers 5.3.0 баг
- `trust_remote_code=True` вызывает `AttributeError: 'PaddleOCRVLConfig' object has no attribute 'text_config'`
- Решение: загрузка через `AutoModelForImageTextToText` БЕЗ `trust_remote_code`
- Inference: `processor.apply_chat_template` → `processor(text=..., images=...)` → `model.generate`

### GOT-OCR2 — кириллица
- Артефакты транслитерации на русском тексте (модель обучена преимущественно на латинице/CJK)

### Levenshtein similarity — ограничения метрики
- Не учитывает семантику, порядок абзацев, форматирование
- Зацикленный вывод (длинный текст) сильно штрафуется
- Для production нужна семантическая метрика (cosine similarity embeddings)

---

## Решения (D-018)

- **Primary OCR:** DeepSeek-OCR v1
- **Fast fallback:** GLM-OCR (4x быстрее, 3x меньше VRAM, 63% quality)
- **Ансамбль:** планируется в Фазе 2
- **DeepSeek-OCR v2:** отклонён как замена v1 (хуже на наших документах)

---

## Что дальше (TODO)

1. **Qwen2.5-VL-7B тестирование** — на машине с RTX 5090 (24+ GB VRAM). Скрипт НЕ написан, нужно создать `poc/bench_qwen_7b.py`. Требования: `transformers>=4.45`, `qwen-vl-utils`, `flash-attn` (опционально).

2. **Ансамбль OCR** — комбинация DeepSeek-OCR v1 + GLM-OCR:
   - DeepSeek v1 для основного прогона
   - GLM-OCR для быстрой верификации / fallback при зацикливании v1
   - Стратегия: если v1 зациклился (output > 2x от ожидаемого) → переключение на GLM-OCR

3. **Семантическая метрика** — заменить Levenshtein на cosine similarity (sentence-transformers). Это даст более адекватную оценку качества OCR.

4. **Gold Standard** — ручная разметка 5-10 страниц аналитиками → ground truth для точного сравнения моделей.

5. **Фаза 1 production pipeline** — интеграция OCR в основной пайплайн (scripts/pdf_to_context/).

---

## Документы обновлены

- `docs/DECISIONS.md` — D-018 добавлен
- `docs/CURRENT_STATE.md` — TASK-007 добавлен, "Следующее" обновлено
- `Changelog.md` — запись 20-03-2026 добавлена
- `poc/benchmark_results/summary.json` — пересчитан с корректным v2
