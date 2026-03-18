# TASK-002: POC 1 — Docling + OCR (EasyOCR vs RapidOCR)

## Цель
Проверить что Docling парсит реальные PDF документы СМК на русском языке.
Сравнить EasyOCR и RapidOCR на 5 сценариях. Выбрать единственный OCR.
Результат: решение D-012 (OCR winner) + poc/poc_ocr_comparison.py.

## Контекст
- D-003: OCR — POC решает. EasyOCR vs RapidOCR, Tesseract исключён.
- D-008: PyMuPDF исключён, используем Docling + docling-parse (MIT).
- GPU: RTX 5080 16GB, свободен.
- PyPI: основной зеркало недоступно, использовать pypi.tuna.tsinghua.edu.cn.

## Scope

### Файлы: НОВЫЙ
- `poc/poc_ocr_comparison.py` — скрипт сравнения EasyOCR vs RapidOCR через Docling

### Файлы: ИЗМЕНИТЬ
- (нет — POC не меняет существующий код)

### ТЕСТЫ
- Docling парсит PDF (нативный текст) — текст извлекается
- EasyOCR через Docling — сканированная страница → текст
- RapidOCR через Docling — сканированная страница → текст
- Levenshtein similarity: ≥95% на нативном, ≥90% на скане

### Зависимости (pip install)
- docling (>=2.70)
- easyocr (>=1.7)
- rapidocr-onnxruntime
- Levenshtein (для метрик)

## 5 сценариев тестирования (из Architecture_v2.1)

```
Тест 1: Нативный текст (копируемый PDF) — baseline
Тест 2: Сканированные страницы — чистый OCR
Тест 3: Смешанные страницы (скан + натив в одном PDF)
Тест 4: Таблица (merged cells, multiline)
Тест 5: Графика с русским текстом (блок-схема)
```

Метрика: Levenshtein similarity с ручной транскрипцией (или нативным текстом как ground truth).
Порог: ≥95% на тестах 1-2, ≥90% на тестах 3-5.

## Non-goals
- НЕ интегрировать в основной pipeline (это Фаза 1)
- НЕ менять scripts/pdf_to_context/ (v1 read-only)
- НЕ менять core/ или scripts/ingestion/ (пока только POC)
- НЕ запускать на всех 410 документах (только 2-3 тестовых)

## Инварианты
- Код v1 не затронут
- Зависимости ставятся в venv, не в pyproject.toml (POC)
- Результаты в poc/ (разрешено без согласования)

## Критерии успеха
1. Docling успешно парсит хотя бы 1 PDF из input/
2. Оба OCR (EasyOCR + RapidOCR) дают результат на русском тексте
3. Метрики Levenshtein собраны для 5 сценариев
4. Есть чёткий победитель → решение D-012

## Ownership
- **coder**: установка зависимостей, написание poc/poc_ocr_comparison.py, запуск
- **scribe**: запись D-012 в DECISIONS.md по результатам

## Риски
1. Docling может не установиться (тяжёлая зависимость ~2GB) — MEDIUM
   Митигация: использовать зеркало PyPI, увеличить таймаут
2. EasyOCR/RapidOCR могут плохо работать на русском через Docling — MEDIUM
   Митигация: это и есть цель POC — выяснить
3. Нет тестовых документов со сканами — LOW
   Митигация: использовать документы из input/ (часть содержит сканы)
