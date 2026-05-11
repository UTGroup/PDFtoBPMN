# TASK-008: Раскол xlsm-монолита + дашборд регулярности ЦУП

**Дата:** 2026-05-04
**Исполнители:** coder (код), scribe (docs/DECISIONS, CURRENT_STATE)
**Фазы:** 2 (split + dashboard)
**Связь:** ANALYSIS_AS-IS_RCA_и_Сбойные.md (§6 узкое место №3)

---

## Цель

### Фаза 1: Раскол `Отчет за ЯНВАРЬ 2026.xlsm` (136 МБ) на файлы ≤ 30 МБ
Без потери данных и логической структуры. Результат в `output/january_split/`.

### Фаза 2: Подпроект `cup_dashboard/` — статичный self-contained HTML
Переиздаваемый дашборд регулярности рейсов из свежих xlsx-источников. Три представления (operational/daily/strategy). ECharts, один файл `.html` с вшитыми данными.

---

## Допущения (assumptions)

- **A1:** Два листа данных («Данные» и «Данные (15МИН)») содержат одни и те же рейсы, различаясь только нормировкой порога задержки (5 мин vs 15 мин). Для дашборда оба нужны — секция расхождений обязательна. PRIMARY для KPI-графиков — «Данные (15МИН)» (текущий стандарт AHM 730). Если ложно → пересмотреть ETL-маппинг.

- **A2:** VBA-макросы в исходном xlsm служат для управления pivot-таблицами и slicers. При расколе: pivot-данные замораживаются как cached values (не static values-only, а именно pivot cache — Excel покажет последнее состояние без автообновления). VBA сохраняется в файле отчёта, но pivot-refresh не будет работать без подключения внешних данных. Если ложно (VBA делает критичные вычисления) → нужен аудит `vbaProject.bin`.

- **A3:** Каждый лист данных (~138K строк × 72 столбца) в standalone xlsx занимает ~40-50 МБ сжатого. Для достижения ≤ 30 МБ потребуется раскол данных по строкам (пополам) или экспорт в CSV/Parquet. Если ложно (xlsx после оптимизации < 30 МБ) → раскол данных не нужен, упрощается.

- **A4:** Файлы-источники для ETL доступны по фиксированным путям в `input2/ЦУП/Отчетность/`. ETL читает их in-place, не копируя. Если ложно → добавить шаг копирования.

- **A5:** sharedStrings.xml содержит все строковые значения обоих листов данных. При расколе по листам sharedStrings нужно пересобирать для каждого файла. Прямая ZIP-хирургия без пересборки sharedStrings даст артефакты. Если ложно → можно использовать ZIP-split.

- **A6:** Исторические данные для дашборда ограничены YTD 2026 (из `БАЗА ДАННЫХ 2026` + `Причины РЗ 2026`). Многолетнее сравнение (2019/2025) — вторая итерация, не MVP. Если ложно → расширить ETL reader.

- **A7:** Для колонок листа «Данные» используется маппинг из sharedStrings, расшифрованный parent-агентом (72 столбца от «Летный период» до «Без МЕТЕО 4»). Если ложно → нужен ручной маппинг.

- **A8 (Q1 resolved):** VBA → `doc_only`. Достаточно документации (`VBA_INVENTORY.md` в output). VBA не реинженерим — дашборд живёт в HTML. Если coder обнаружит бизнес-логику (а не UI-кнопки) в `vbaProject.bin` — флаг + ревизия Фазы 1 (связь с R2).

- **A9 (Q2 resolved):** Периодичность обновления — `monthly`. MVP = январь 2026. ETL pipeline параметризован по `--month YYYY-MM`, чтобы переиспользовать для февраля/марта/… без изменения кода.

- **A10 (Q3 resolved):** Визуальный стиль — `inspire`. Screenshot_1..4 — референс для метрик/разрезов (стопка-бары по кодам, доли по аэропортам, KPI с δ), но дизайн современный, не воспроизводит легаси-вид. Палитра: нейтральный сине-серый, без логотипа Utair.

- **A11 (Q4 resolved):** Справочники подтверждены:
  - `БАЗА ДАННЫХ 2026 (2).xlsm` (hidden листы): `БОРТ. НОМЕРА`, `код РЗ`, `аэроп`, `Календарь`
  - `Причины РЗ 2026 (2).xlsx` (visible лист): `Причины` (маппинг кодов и подкодов)

- **A12 (Q5 resolved):** Язык интерфейса — `ru_en_codes`. Русский для заголовков, подписей осей, GAP-маркеров. Латиница для IATA-кодов аэропортов и бортовых номеров (как в исходных xlsx).

---

## Анализ стратегии раскола (Фаза 1)

### Почему файл большой

| Компонент | Размер (в zip) | Примечание |
|---|---|---|
| sheet9 (`Данные`) | ~46 МБ | 138 278 строк × 72 столбца |
| sheet10 (`Данные (15МИН)`) | ~46 МБ | 138 404 строки × 72 столбца |
| pivotCacheRecords 3-5 | ~15-20 МБ | Ref `'Данные'!A1:BJ1048576` → 244 888 пустых записей |
| calcChain.xml | ~5-8 МБ (в zip) | 26 МБ распакованный, можно удалить |
| sharedStrings.xml | ~10-15 МБ | Строковые значения обоих листов |
| Все остальное | < 5 МБ | 16 человеческих листов, VBA, styles, slicers |
| **Итого** | **~136 МБ** | |

### Рассмотренные альтернативы

| # | Стратегия | Плюсы | Минусы | Вердикт |
|---|---|---|---|---|
| 1 | **Optimize + Structural Split** (починка pivotCache + удаление calcChain + раскол на Отчёт + Данные) | Сохраняет логику, VBA, slicers | Данные по-прежнему > 30 МБ → нужен доп. раскол | **Выбрана** (с доп. расколом данных) |
| 2 | Split по периодам (недели/полумесяцы) | Каждый кусок мал | Ломает pivot-таблицы, VBA, slicers; сложная сборка | Отклонена |
| 3 | Экспорт данных в CSV + Report.xlsm | CSV компактнее xlsx | Теряются типы, форматирование; два формата | Частично (CSV как дополнительный формат) |
| 4 | Экспорт в Parquet | Максимальное сжатие (~5 МБ) | Не открывается в Excel | Для ETL, не для раскола |
| 5 | Наивный split (openpyxl copy_worksheet) | Простота кода | OOM на 380 МБ XML; sharedStrings не пересобираются; VBA теряется | Отклонена |

### Выбранная стратегия: Optimize + Structural Split + Row Split

**Шаг A: Оптимизация (ZIP-хирургия)**
1. Открыть xlsm как ZIP
2. В `xl/pivotCache/pivotCacheDefinition{3,4,5}.xml`: заменить `ref="'Данные'!$A$1:$BJ$1048576"` на `ref="'Данные'!$A$1:$BJ$138279"` (и аналогично для 15МИН)
3. Удалить `xl/calcChain.xml`, убрать его из `[Content_Types].xml`
4. (Опционально) Обрезать пустые записи в `xl/pivotCache/pivotCacheRecords{3,4,5}.xml`
5. Пересобрать ZIP с максимальным сжатием (deflate level 9)

**Оценка после оптимизации:** ~100-110 МБ (−25-35 МБ от pivotCache fix + calcChain removal)

**Шаг B: Структурный раскол (pandas/openpyxl + ZIP-манипуляция)**
1. **`Январь_2026_Отчёт.xlsm`** — все листы кроме sheet9 и sheet10, + VBA (`xl/vbaProject.bin`), + slicers, + оптимизированные pivotCaches (с cached data). Pivot tables покажут закешированные данные.
   - Ожидаемый размер: **5-15 МБ** ✓

2. **`Январь_2026_Данные.csv`** — лист «Данные» экспортирован в CSV (UTF-8, `;` разделитель).
   - Ожидаемый размер: **~20-25 МБ** ✓
   - Альтернатива: если нужен xlsx — раскол на 2 файла по ~69K строк каждый

3. **`Январь_2026_Данные_15мин.csv`** — лист «Данные (15МИН)» экспортирован в CSV.
   - Ожидаемый размер: **~20-25 МБ** ✓

4. **`Январь_2026_Данные.parquet`** + **`Январь_2026_Данные_15мин.parquet`** — Parquet-версии для ETL.
   - Ожидаемый размер: **~3-5 МБ каждый** ✓

**Шаг C: Верификация**
- Подсчёт строк: оригинал vs CSV vs parquet (должны совпадать)
- Контрольные суммы: 5 случайных строк, все 72 колонки
- Отчёт: xlsx → csv → parquet round-trip без потерь
- Файл отчёта: открывается в Excel, VBA грузится, pivot-таблицы показывают данные

---

## Scope (файлы)

### Фаза 1: Split

| Тип | Путь | Описание |
|---|---|---|
| НОВЫЙ | `cup_dashboard/tools/split_xlsm.py` | Скрипт раскола: optimize + split + export CSV/parquet |
| НОВЫЙ | `cup_dashboard/tools/verify_split.py` | Скрипт верификации: row counts, checksums, report |
| ВЫВОД | `output/january_split/Январь_2026_Отчёт.xlsm` | Отчётная часть (≤ 15 МБ) |
| ВЫВОД | `output/january_split/Январь_2026_Данные.csv` | Данные в CSV (≤ 25 МБ) |
| ВЫВОД | `output/january_split/Январь_2026_Данные_15мин.csv` | Данные 15МИН в CSV (≤ 25 МБ) |
| ВЫВОД | `output/january_split/Январь_2026_Данные.parquet` | Данные в Parquet (≤ 5 МБ) |
| ВЫВОД | `output/january_split/Январь_2026_Данные_15мин.parquet` | Данные 15МИН в Parquet (≤ 5 МБ) |
| ВЫВОД | `output/january_split/split_report.json` | Отчёт верификации |

### Фаза 2: Dashboard

| Тип | Путь | Описание |
|---|---|---|
| НОВЫЙ | `cup_dashboard/__init__.py` | Пакет |
| НОВЫЙ | `cup_dashboard/etl/__init__.py` | ETL пакет |
| НОВЫЙ | `cup_dashboard/etl/reader.py` | Чтение xlsx-источников (openpyxl read_only + pandas) |
| НОВЫЙ | `cup_dashboard/etl/normalizer.py` | Нормализация колонок, валидация, типизация |
| НОВЫЙ | `cup_dashboard/etl/pipeline.py` | Оркестрация: reader → normalizer → parquet + JSON |
| НОВЫЙ | `cup_dashboard/builder/__init__.py` | Builder пакет |
| НОВЫЙ | `cup_dashboard/builder/aggregator.py` | Агрегации по аудиториям (daily, strategy) |
| НОВЫЙ | `cup_dashboard/builder/renderer.py` | Инъекция JSON в HTML-шаблон |
| НОВЫЙ | `cup_dashboard/builder/build.py` | Entry point: parquet → HTML |
| НОВЫЙ | `cup_dashboard/templates/dashboard.html` | HTML-шаблон с ECharts, 3 таба |
| НОВЫЙ | `cup_dashboard/dictionaries/extract_dicts.py` | Извлечение справочников из БАЗА ДАННЫХ.xlsm |
| ВЫВОД | `cup_dashboard/dictionaries/rz_codes.json` | Коды РЗ (IATA AHM 730 + внутренние) |
| ВЫВОД | `cup_dashboard/dictionaries/airports.json` | Справочник аэропортов |
| ВЫВОД | `cup_dashboard/dictionaries/aircraft.json` | Борт. номера + типы ВС |
| НОВЫЙ | `cup_dashboard/README.md` | Инструкция «как обновить дашборд за новый месяц» |
| ТЕСТЫ | `tests/test_cup_etl.py` | Snapshot-тесты ETL (row counts, schema, sample values) |
| ТЕСТЫ | `tests/test_cup_html.py` | Smoke-тесты HTML (файл существует, размер, содержит ECharts) |

---

## Non-goals (что НЕ менять)

- `scripts/**` — существующий pipeline PDFtoBPMN (не затрагивается)
- `core/**` — типы и протоколы графа (не затрагиваются)
- `input2/ЦУП/Отчетность/*` — исходные файлы read-only (не модифицируем)
- Реальный-time оперативный слой НС ЦУП (требует Meridian.OPS, не xlsx)
- Многолетнее сравнение (2019/2025 vs 2026) — не MVP, вторая итерация
- Интеграция с Knowledge Graph (D-001) — dashboard — отдельный инструмент
- Drill-down до конкретного рейса — не требуется в MVP
- Автоматическое обновление — ручной запуск `python -m cup_dashboard.builder.build`

---

## Инварианты (что не должно сломаться)

1. Исходный `Отчет за ЯНВАРЬ 2026.xlsm` не модифицируется (read-only)
2. Сумма строк во всех split-файлах данных = оригинал (138 278 для Данные, 138 404 для 15МИН)
3. Тесты `tests/` проекта PDFtoBPMN — не ломаются (отдельный подпроект, no import conflicts)
4. `docs/DECISIONS.md` и `docs/CURRENT_STATE.md` — обновляются scribe (не coder)
5. Никаких новых зависимостей в основном `requirements.txt` — `cup_dashboard/requirements.txt` отдельный

---

## Декомпозиция на diff-куски

### D1: Скелет подпроекта + split скрипт (Фаза 1)
**Файлы:** `cup_dashboard/__init__.py`, `cup_dashboard/tools/split_xlsm.py`, `cup_dashboard/requirements.txt`
**Строк:** ~130
**Действие:** Создать скрипт раскола xlsm через ZIP-хирургию + pandas export
**→ verify:** `python cup_dashboard/tools/split_xlsm.py "input2/ЦУП/Отчетность/Отчет за ЯНВАРЬ 2026.xlsm" output/january_split/` → 5+ файлов, каждый ≤ 30 МБ

### D2: Верификация раскола (Фаза 1)
**Файлы:** `cup_dashboard/tools/verify_split.py`
**Строк:** ~80
**Действие:** Скрипт проверки: row counts, sample checksums, report JSON
**→ verify:** `python cup_dashboard/tools/verify_split.py output/january_split/ --original "input2/ЦУП/Отчетность/Отчет за ЯНВАРЬ 2026.xlsm"` → `split_report.json` с `"status": "PASS"`

### D3: ETL reader + normalizer (Фаза 2)
**Файлы:** `cup_dashboard/etl/__init__.py`, `cup_dashboard/etl/reader.py`, `cup_dashboard/etl/normalizer.py`
**Строк:** ~140
**Действие:** Чтение 3 xlsx-источников, маппинг 72 колонок на нормализованные имена, типизация, валидация
**→ verify:** `python -c "from cup_dashboard.etl.reader import read_report; df = read_report(...); assert len(df) == 138278; assert len(df.columns) == 72"`

### D4: Извлечение справочников (Фаза 2)
**Файлы:** `cup_dashboard/dictionaries/extract_dicts.py`
**Строк:** ~80
**Действие:** Из `БАЗА ДАННЫХ 2026.xlsm` извлечь коды РЗ, аэропорты, борт.номера, тип ВС → JSON
**→ verify:** 3 JSON файла в `cup_dashboard/dictionaries/`, каждый непустой, schema корректна

### D5: ETL pipeline (Фаза 2)
**Файлы:** `cup_dashboard/etl/pipeline.py`
**Строк:** ~80
**Действие:** Оркестрация: reader → normalizer → parquet + dictionaries → `cup_dashboard/data/<period>/`
**→ verify:** `python -m cup_dashboard.etl.pipeline --month 2026-01` → `cup_dashboard/data/2026-01/normalized.parquet` + `dictionaries.json`

### D6: Aggregator (Фаза 2)
**Файлы:** `cup_dashboard/builder/__init__.py`, `cup_dashboard/builder/aggregator.py`
**Строк:** ~140
**Действие:** Вычисление агрегаций по двум аудиториям (daily + strategy):
- daily: регулярность по дням, топ причин, топ аэропортов, критичные рейсы
- strategy: KPI % регулярности, динамика м/м, доли категорий, тепловая карта
**→ verify:** JSON-дамп агрегаций, проверка ключей и непустых значений

### D7: HTML-шаблон (Фаза 2)
**Файлы:** `cup_dashboard/templates/dashboard.html`
**Строк:** ~150
**Действие:** Self-contained HTML с ECharts CDN-fallback (inline), три таба (#operational, #daily, #strategy). Operational — GAP-маркер. Обязательные секции: «Пробелы в источнике», «Расхождения Данные vs 15МИН»
**→ verify:** Открыть в браузере, переключить табы, графики рендерятся

### D8: Renderer + Build entry point (Фаза 2)
**Файлы:** `cup_dashboard/builder/renderer.py`, `cup_dashboard/builder/build.py`
**Строк:** ~100
**Действие:** Инъекция JSON-данных в HTML-шаблон, запись результата в `cup_dashboard/output/<period>/dashboard.html`
**→ verify:** `python -m cup_dashboard.builder.build --month 2026-01` → `dashboard.html`, размер > 100 КБ, содержит `<script>` с данными

### D9: Тесты (Фаза 2)
**Файлы:** `tests/test_cup_etl.py`, `tests/test_cup_html.py`
**Строк:** ~100
**Действие:** Snapshot-тесты ETL (schema, row count), smoke-тесты HTML (файл существует, ECharts loaded)
**→ verify:** `pytest tests/test_cup_etl.py tests/test_cup_html.py -v` → all PASS

### D10: README (Фаза 2)
**Файлы:** `cup_dashboard/README.md`
**Строк:** ~60
**Действие:** Инструкция: установка, как обновить за новый месяц, структура файлов, GAP-описание
**→ verify:** Файл существует, содержит секции: «Установка», «Обновление», «Структура», «Ограничения»

---

## KPI / Содержимое дашборда

### Таб `#operational` — НС ЦУП (оперативная смена)
**⚠ GAP-маркер (Rule 0):** «Оперативный режим требует данных в реальном времени из Meridian.OPS. Текущий дашборд от месячного xlsx не покрывает потребности НС ЦУП. Необходима интеграция с Meridian.Alliance (см. ANALYSIS_AS-IS_RCA §6, узкое место №3, §7.3 п.1-2). Данный таб — заглушка, фиксирующая разрыв.»

Содержимое заглушки:
- Текст GAP-маркера с цитатой из нормативки (`РД-Б8.005-09` §14.1.3)
- Ссылка на B2 decision point и 12 категорий входов
- Список необходимых интеграций для закрытия gap

### Таб `#daily` — Начальник ЦУП (ежедневный/недельный)
| Виджет | Тип графика | Источник (лист, столбцы) | Примечание |
|---|---|---|---|
| Регулярность по дням месяца | Stacked bar (≤15 мин / >15 мин) | Данные(15МИН): Дата, РЗ ≤15min, РЗ >15 min | По оси X — дни, по Y — количество рейсов |
| Топ-10 причин задержек | Horizontal bar | Данные(15МИН): Служба, М/У, НМЧ, ПОО, ППС... | Агрегация по колонкам причин |
| Топ-10 аэропортов по доле задержек | Horizontal bar | Данные(15МИН): Аэропорт вылета, РЗ >15 min | % задержанных от total flights |
| Критичные рейсы (>2ч, запасной а/д, отмены) | Таблица | Данные(15МИН): время РЗ > 120 мин, фильтры | Сортировка по убыванию задержки |
| Фильтры | Select/date-range | Дата, КВ, тип ВС, Аэропорт | ECharts datazoom + selects |

### Таб `#strategy` — Топ-менеджмент (месяц/квартал/год)
| Виджет | Тип графика | Источник | Примечание |
|---|---|---|---|
| KPI: % регулярности (к плану AHM 730) | Gauge / big number | Данные(15МИН): Total flights, РЗ >15 min | С цветовой индикацией (зелёный/жёлтый/красный) |
| Динамика м/м (YTD) | Line chart | БАЗА ДАННЫХ: по месяцам 2026 | Линия % регулярности |
| Доли категорий причин + стрелки изменения | Donut + arrows | Данные(15МИН) + БАЗА ДАННЫХ (пред. месяц) | Как в Screenshot_2 |
| Тепловая карта: аэропорт × категория причины | Heatmap | Данные(15МИН): Аэропорт × Причина | Интенсивность = кол-во задержек |
| Крупные эскалации (A3/A4) | Таблица | Причины РЗ 2026: фильтр по severity | Рейсы с эскалацией |
| Расхождения Данные vs 15МИН | Comparison table | Оба листа | Строки/значения, отличающиеся между двумя нормировками |

### Обязательные секции (Rule 0)
1. **«Пробелы в источнике»** — карточка в footer каждого таба:
   - G1: Обоснования решений B2 отсутствуют (узкое место №3)
   - G2: Классификатор М/У → ПОО различается между документами
   - G3: Две нормировки (5 мин и 15 мин) — расхождения фиксируются, не маскируются
   - G4: Ручной справочник кодов РЗ (Screenshot_1) не версионирован
   - G5: Несинхронность АСБ↔DCS↔Meridian.OPS (gap-06 из ANALYSIS)
   - G6: Оперативный режим НС ЦУП не покрыт дашбордом (только месячные данные)

2. **Провенанс** каждого виджета — tooltip/footer с указанием: файл, лист, диапазон колонок, дата генерации

3. **Секция «Расхождения Данные vs 15МИН»** — в табе #strategy, отдельная таблица

---

## Выбор технологий

### ECharts vs альтернативы

| Библиотека | Bundle size | Интерактивность | Self-contained | Вердикт |
|---|---|---|---|---|
| **ECharts** | ~800 КБ min.js | Высокая (tooltip, zoom, brush) | Да (inline) | **Выбрана** |
| Plotly.js | ~3.5 МБ min.js | Высокая | Да, но тяжёлый | Отклонена (размер) |
| D3.js | ~250 КБ | Максимальная | Да | Отклонена (требует больше кода) |
| Chart.js | ~200 КБ | Средняя | Да | Отклонена (слабые heatmaps) |
| Lightweight Charts | ~50 КБ | Низкая | Да | Отклонена (только финансовые) |

**Решение:** ECharts — оптимальный баланс размера, интерактивности и набора графиков (stacked bar, heatmap, gauge, line, donut). Inline в HTML (~800 КБ). CDN-fallback не нужен (self-contained).

### ETL стек
- **pandas** — чтение xlsx, нормализация, агрегации
- **openpyxl** — read_only mode для больших файлов (streaming)
- **pyarrow** — запись parquet
- **jinja2** — шаблонизация HTML (инъекция JSON)

### `cup_dashboard/requirements.txt`
```
pandas>=2.2
openpyxl>=3.1
pyarrow>=15.0
jinja2>=3.1
```

---

## Риски

| # | Риск | Вероятность | Влияние | Митигация |
|---|---|---|---|---|
| R1 | **pivotCache хрупкость**: замена ref в XML ломает формат, Excel не открывает | Средняя | Высокое | Тест: открыть в Excel после каждой правки. Backup оригинала. Fallback: полная заморозка pivot → values only |
| R2 | **Потеря VBA-логики**: при пересборке ZIP `vbaProject.bin` сломается | Низкая | Среднее | Копировать `vbaProject.bin` байт-в-байт, не модифицировать. Верифицировать: Alt+F11 в Excel |
| R3 | **OOM при чтении 138K×72 pandas**: DataFrame > RAM | Низкая | Высокое | openpyxl `read_only=True` + `iter_rows()` streaming. Chunk-based CSV export |
| R4 | **Дрейф классификатора кодов РЗ**: справочник в БАЗА ДАННЫХ может не совпадать с кодами в Данных | Средняя | Среднее | ETL: валидация join — коды из Данных vs справочник, лог unmatched. В дашборде — бейдж «N кодов не в справочнике» |
| R5 | **sharedStrings.xml**: при расколе по листам строковые индексы сбиваются, если не пересобрать | Высокая | Высокое | Использовать pandas для экспорта данных (пересоздаёт xlsx/csv с нуля), а не ZIP-хирургию для листов данных |
| R6 | **HTML > 10 МБ**: если вшить все 138K строк в JSON, файл будет неподъёмным | Средняя | Среднее | Вшивать только агрегаты (JSON ~50-200 КБ). Raw data не встраивать. Итоговый HTML ≤ 2 МБ |
| R7 | **Две нормировки маскируют проблему**: если тихо выбрать одну — потеря информации | Низкая | Среднее | Rule 0: обязательная секция расхождений. Оба листа читаются, дельта вычисляется и показывается |

---

## Критерии успеха (step → verify)

### Фаза 1
1. Скрипт раскола создан и работает → verify: `python cup_dashboard/tools/split_xlsm.py <input> <output>` завершается без ошибок
2. Все выходные файлы ≤ 30 МБ → verify: `ls -la output/january_split/ | awk '{print $5, $9}'` — все ≤ 31457280 байт
3. Сумма строк данных = оригинал → verify: `verify_split.py` → `rows_match: true`
4. Файл отчёта открывается в Excel → verify: (ручная проверка, или `openpyxl.load_workbook` без ошибок)
5. Контрольные суммы 5 строк совпадают → verify: `verify_split.py` → `checksums_match: true`

### Фаза 2
6. ETL читает 3 источника → verify: `pipeline.py --month 2026-01` → parquet создан, shape совпадает
7. Справочники извлечены → verify: 3 JSON в `dictionaries/`, каждый непустой
8. HTML генерируется → verify: `build.py --month 2026-01` → `dashboard.html` существует, > 100 КБ
9. HTML содержит 3 таба → verify: grep `#operational|#daily|#strategy` в HTML → 3 совпадения
10. HTML содержит ECharts → verify: grep `echarts.min.js` или inline ECharts code → найдено
11. Секция «Пробелы в источнике» присутствует → verify: grep `Пробелы в источнике` → найдено
12. Провенанс виджетов → verify: grep `Источник:` в HTML → ≥ N виджетов с атрибуцией
13. Тесты проходят → verify: `pytest tests/test_cup_etl.py tests/test_cup_html.py -v` → all PASS
14. Секция расхождений Данные vs 15МИН → verify: grep `Расхождения` в HTML → найдено
15. README создан → verify: `cup_dashboard/README.md` существует, содержит «Обновление»

---

## Ownership

| Файл/директория | Агент |
|---|---|
| `.cursor/plans/TASK-008.md` | orchestrator (этот файл) |
| `cup_dashboard/**` (код) | coder |
| `tests/test_cup_*.py` | coder |
| `output/january_split/**` | coder (вывод скрипта) |
| `cup_dashboard/README.md` | coder |
| `docs/DECISIONS.md` (D-021+) | scribe |
| `docs/CURRENT_STATE.md` | scribe |

---

## Порядок исполнения

```
H1: Human → Orchestrator (это задание)
H2: Orchestrator → Validator (pre-gate: этот план)
    checks: plan_vs_decisions, scope_valid, ownership_ok
H4: Orchestrator → Coder (D1 + D2: Фаза 1)
    iteration: 1/3
    scope: split_xlsm.py, verify_split.py
H5: Coder → Validator (post-gate: diff + verify)
H4': Orchestrator → Coder (D3-D5: ETL core)
    iteration: 1/3
H4'': Orchestrator → Coder (D6-D8: Builder + HTML)
    iteration: 1/3
H4''': Orchestrator → Coder (D9-D10: Tests + README)
    iteration: 1/3
H7: Orchestrator → Scribe (D-021: решения, CURRENT_STATE)
H9: Orchestrator → Human (доклад, готово к коммиту)
```

**Fast-track не применим:** задача затрагивает > 1 файла, > 30 строк, создаёт новый подпроект.

---

## Открытые вопросы — ВСЕ RESOLVED (04.05.2026)

Все вопросы закрыты. Ответы human зафиксированы как допущения A8–A12.

1. ~~VBA-логика~~ → A2 + **A8**: doc_only, не реинженерим; флаг если бизнес-логика
2. ~~Primary data sheet~~ → A1: оба, PRIMARY = Данные(15МИН)
3. ~~Исторический горизонт~~ → A6: YTD 2026, многолетнее — не MVP
4. ~~Выходная директория~~ → `output/january_split/`
5. ~~sharedStrings при расколе~~ → A5: pandas export (пересоздаёт), не ZIP-split
6. ~~Периодичность обновления~~ → **A9**: monthly, ETL параметризован по --month
7. ~~Стиль дашборда~~ → **A10**: inspire, современный, сине-серая палитра
8. ~~Листы справочников~~ → **A11**: `БОРТ. НОМЕРА`, `код РЗ`, `аэроп`, `Календарь`, `Причины`
9. ~~Язык интерфейса~~ → **A12**: русский + латиница для IATA/бортовых

---

## Решения для фиксации (scribe → DECISIONS.md)

После завершения и post-gate PASS:

- **D-021: cup_dashboard — статичный self-contained HTML дашборд регулярности**
  Контекст: отчётность ЦУП в xlsm-монолитах (134 МБ), ручная презентация. Решение: Python ETL → parquet → ECharts HTML. Три аудитории (operational GAP, daily, strategy). Отклонено: Plotly (тяжёлый), Grafana (требует сервер), Power BI (проприетарный).

- **D-022: Стратегия раскола xlsm — optimize + structural split + CSV/Parquet export**
  Контекст: файл 136 МБ, pivot-cache bloat, calcChain. Решение: ZIP-хирургия для report-части + pandas export для данных. Отклонено: split по периодам (ломает pivots), наивный openpyxl copy (OOM).
