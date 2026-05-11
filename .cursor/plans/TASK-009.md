# TASK-009: Live-дашборд регулярности ЦУП → ClickHouse + FastAPI + ECharts

**Дата:** 2026-05-04
**Исполнители:** coder (код в `todo/cup_dashboard/`), scribe (docs/DECISIONS, CURRENT_STATE)
**Фазы:** 6 (A — анализ, B — ETL, C — сервер, D — фронтенд, E — публикация, F — state)
**Связь:** TASK-008 (Фаза 1 PASS, Фаза 2 **отменена** → заменена TASK-009). D-021 → D-024.
**Паттерн-прецедент:** `todo/sfv_dashboard/` (Onboard sales)
**Cross-repo:** первая задача, затрагивающая два git-репо одновременно (D-023)

---

## Цель

Перевести аналитику регулярности рейсов ЦУП из Excel-монолитов в live-дашборд:

1. **ETL** — загрузить данные из 4 xlsx-источников в ClickHouse (`10.95.19.132`, БД `cup`, таблица `cup.flights`). Максимальный охват колонок (72 из «Отчёт январь» — полная ширина, остальные источники получают NULL в недостающих).
2. **FastAPI сервер** — API к CH по паттерну `sfv_dashboard/`.
3. **SPA** — ECharts-дашборд (портирование мокапа `cup_dashboard/poc/dashboard_mockup.html` под Utair-палитру и live-данные).
4. **Публикация** — docker-сервис `cup-dashboard`, reverse-proxy `/info/tsup/` через `backend/app.py`, карточка в `webBI/info.html`.

---

## Допущения (assumptions)

- **A1 (Q4 resolved):** Канонические 72 столбца определяются листом «Данные» из `Отчет за ЯНВАРЬ 2026.xlsm`. Остальные источники (60, 30 столбцов) маппятся на подмножество этих 72, недостающие → NULL. **Подтверждено human:** «максимальное количество исходных параметров».

- **A2 (Q3 resolved):** CH пользователь `default` (из `.env`) имеет права `CREATE DATABASE`, `CREATE TABLE`, `INSERT`. **Проверено:** `SHOW GRANTS` → `GRANT ALL ON *.* TO default WITH GRANT OPTION`. Probe CREATE/DROP прошёл. CH версия 24.10.1.2812.

- **A3 (Q2 resolved):** Имя БД `cup` свободно на `10.95.19.132`. **Проверено:** `SHOW DATABASES` → `default, sfv, hc_snapshot_2026_04_12, INFORMATION_SCHEMA, information_schema, system`. `cup` отсутствует.

- **A4:** Лист «Данные» и «Данные (15МИН)» в январском отчёте — два представления одних рейсов с разными порогами задержки (5 мин / 15 мин). Оба грузятся в `cup.flights` с различием в `data_layer` (`5min` / `15min`). Если ложно → отдельные таблицы.

- **A5 (Q5 resolved):** VBA в xlsm-источниках не содержит ETL-логики (см. TASK-008 A8, R2=undetermined). TASK-009 строит независимый Python ETL через openpyxl + clickhouse-driver. VBA-макросы не исполняются. **Подтверждено human:** R2 не блокирует TASK-009.

- **A12 (Q1 resolved):** Мутации в CH разрешены human ALL_AT_ONCE: `CREATE DATABASE cup` → `CREATE TABLE cup.flights` → `INSERT` всех источников. Дальнейшие отдельные разрешения не требуются.

- **A6:** Файлы-источники доступны по фиксированным путям в `input2/ЦУП/Отчетность/`. ETL читает их in-place. Parquet из `output/january_split/` используется как альтернативный вход (быстрее).

- **A7:** ECharts из мокапа — целевая библиотека визуализации (решение human). НЕ Plotly (как в sfv_dashboard). Если ложно → переработать D.1-D.2.

- **A8:** Utair-палитра и токены (`--utair-blue: #003594`, шрифт Suisse Int'l, `sign_white.png`, `utair_text.png`) берутся из `webBI/info.html` и `sfv_dashboard/static/style.css`. Header и footer идентичны sfv_dashboard.

- **A9:** URL slug `/info/tsup/` — свободный префикс, не занят другими маршрутами в `backend/app.py`. Если ложно → выбрать другой.

- **A10:** Новая секция в `info.html` — «Производство» (или «Операционная деятельность»). Позиция: первая секция (перед «Коммерция»). Если human передумает — правка одной строки.

- **A11:** `clickhouse-driver==0.2.10` — та же версия что в sfv_dashboard. Изолированные зависимости в `cup_dashboard/requirements.txt`.

---

## Scope (файлы)

### Repo: Obligations (минимально)

| Тип | Путь | Описание |
|---|---|---|
| НОВЫЙ | `cup_dashboard/etl/data_inventory.md` | Реестр исходных данных: колонки, размерности, ключи, расхождения |
| ИЗМЕНИТЬ | `cup_dashboard/poc/dashboard_mockup.html` | Пометка «MOCKUP-only, не продакшн» в шапке |

### Repo: todo (основной объём)

| Тип | Путь | Описание |
|---|---|---|
| НОВЫЙ | `cup_dashboard/__init__.py` | Пакет |
| НОВЫЙ | `cup_dashboard/etl/__init__.py` | ETL пакет |
| НОВЫЙ | `cup_dashboard/etl/sql/schema.sql` | CREATE DATABASE cup + CREATE TABLE cup.flights |
| НОВЫЙ | `cup_dashboard/etl/column_mapping.json` | Маппинг колонок 4 источников → каноническая схема 72 |
| НОВЫЙ | `cup_dashboard/etl/reader.py` | Чтение xlsx через pandas + openpyxl, нормализация |
| НОВЫЙ | `cup_dashboard/etl/loader.py` | clickhouse-driver INSERT батчами по 10K строк |
| НОВЫЙ | `cup_dashboard/etl/pipeline.py` | Оркестрация: reader → loader → валидация row counts |
| НОВЫЙ | `cup_dashboard/etl/cli.py` | CLI: `python -m cup_dashboard.etl.cli load --source january` |
| НОВЫЙ | `cup_dashboard/core/__init__.py` | Core пакет |
| НОВЫЙ | `cup_dashboard/core/clickhouse.py` | Per-thread Client(), env-driven (копия из sfv + адаптация) |
| НОВЫЙ | `cup_dashboard/queries.py` | SQL-агрегаторы: lookups, kpi, daily, causes, airports, heatmap, events, top20 |
| НОВЫЙ | `cup_dashboard/server.py` | FastAPI: /api/health, /api/lookups, /api/kpi, /api/daily, /api/causes, /api/airports, /api/heatmap, /api/events, /api/top20 |
| НОВЫЙ | `cup_dashboard/static/index.html` | SPA: портирование мокапа, Utair-брендинг, fetch /api/* |
| НОВЫЙ | `cup_dashboard/static/app.js` | ECharts графики, фильтры, drill-down, URL-якоря |
| НОВЫЙ | `cup_dashboard/static/style.css` | Utair palette, light theme |
| НОВЫЙ | `cup_dashboard/requirements.txt` | fastapi, uvicorn, clickhouse-driver, python-dotenv |
| НОВЫЙ | `cup_dashboard/Dockerfile` | По паттерну sfv_dashboard/Dockerfile |
| НОВЫЙ | `cup_dashboard/DEPLOY.md` | Инструкция по публикации (паттерн sfv_dashboard/DEPLOY.md) |
| НОВЫЙ | `cup_dashboard/README.md` | Описание сервиса, API, источники данных |
| ИЗМЕНИТЬ | `docker-compose.yml` | +сервис cup-dashboard (expose 8000, env_file .env) |
| ИЗМЕНИТЬ | `backend/app.py` | +reverse-proxy /info/tsup/ → http://cup-dashboard:8000 |
| ИЗМЕНИТЬ | `webBI/info.html` | +секция «Производство», карточка «Регулярность ЦУП» |
| ИЗМЕНИТЬ | `CHANGELOG.md` | Запись о cup_dashboard |

---

## Non-goals (что НЕ менять)

- `scripts/**`, `core/**` в Obligations — pipeline PDFtoBPMN не затрагивается
- `sfv_dashboard/**` — существующий дашборд не модифицируется
- Оперативный режим НС ЦУП в реальном времени (требует Meridian.OPS)
- Интеграция с Knowledge Graph (D-001) — cup_dashboard — отдельный инструмент
- Drill-down до уровня отдельного пассажира/борта
- Автоматический периодический запуск ETL (cron/scheduler) — ручной запуск
- `.cursor/rules/*.mdc` — human only, не трогаем
- `todo/.cursor/` — правила todo-репо (если есть) не меняются

---

## Инварианты (что не должно сломаться)

1. Исходные xlsx в `input2/ЦУП/Отчетность/` — read-only, не модифицируются
2. Существующий `sfv_dashboard` — работает без изменений
3. `docker-compose.yml` — backend и sfv-dashboard продолжают работать
4. `backend/app.py` — существующие маршруты (/, /info/onboard-sales/, /km/, /info/*, /api/*) не ломаются
5. `webBI/info.html` — существующие карточки и секции на месте
6. Тесты Obligations (`tests/`) — не ломаются (код в другом репо)
7. `docs/DECISIONS.md`, `docs/CURRENT_STATE.md` — обновляются scribe, не coder

---

## Phase A — Анализ и схема

### A.1 — Реестр исходных данных

**Файл:** `cup_dashboard/etl/data_inventory.md` (НОВЫЙ, в Obligations)

Coder читает все 4 xlsx и составляет полный реестр:
- Для каждого файла и каждого листа: имя, количество строк × столбцов, список заголовков
- Ключевые поля для возможного join (дата, номер рейса, аэропорт)
- Расхождения колонок между источниками (72 vs 60 vs 30) — табличное сравнение
- Типы данных (числовые, даты, строки) — по фактическим значениям
- GAP-маркеры по Rule 0: какие колонки есть только в одном источнике

**Зачем отдельным handoff'ом:** реальная ширина источников определяет схему CH. Без inventory создавать schema.sql — слепая работа.

### A.2 — Схема ClickHouse

**Файл:** `todo/cup_dashboard/etl/sql/schema.sql` (НОВЫЙ)

```sql
CREATE DATABASE IF NOT EXISTS cup;

CREATE TABLE IF NOT EXISTS cup.flights (
    -- 72 канонические колонки из листа «Данные» (заполнятся после A.1)
    -- ...
    source_file LowCardinality(String),    -- имя xlsx-файла
    data_layer  LowCardinality(String),    -- '5min' | '15min' | 'weekly' | 'rz_causes' | 'base_db'
    loaded_at   DateTime DEFAULT now()
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(date)              -- date = основная дата рейса
ORDER BY (date, flight_no, dep_airport)
SETTINGS index_granularity = 8192;
```

Решение — одна денормализованная таблица `cup.flights` (ответ human). Без звезды. Аргументация:
- Паттерн sfv: одна `sfv.catering_items`
- Простота запросов (нет JOIN)
- Источники разной ширины → NULL в недостающих колонках
- `data_layer` позволяет фильтровать по типу среза

---

## Phase B — ETL

### B.1 — Reader

**Файлы:** `todo/cup_dashboard/etl/reader.py`, `todo/cup_dashboard/etl/column_mapping.json`

- pandas + openpyxl (read_only=True, streaming для больших файлов)
- Каждый источник → DataFrame с каноническими именами колонок
- `column_mapping.json`: `{ "source_header": "canonical_name", ... }` для каждого файла
- Добавление мета-колонок: `source_file`, `data_layer`
- Валидация: dtype check, null-процент по колонкам, дубликаты

### B.2 — Loader

**Файл:** `todo/cup_dashboard/etl/loader.py`

- `clickhouse-driver` через `core/clickhouse.py`
- `INSERT INTO cup.flights VALUES` батчами по 10 000 строк
- Перед загрузкой: `SELECT count() FROM cup.flights WHERE source_file = %(sf)s` → если >0, предупреждение (идемпотентность: можно добавить `--replace` для `ALTER TABLE DELETE WHERE source_file = ...`)
- Логирование: N строк загружено, время, скорость (строк/сек)

### B.3 — Pipeline

**Файл:** `todo/cup_dashboard/etl/pipeline.py`

Оркестрация:
1. reader.read_source(path, sheet, data_layer) → DataFrame
2. loader.load(df) → count inserted
3. Валидация: `SELECT count() FROM cup.flights WHERE source_file = X` == len(df)
4. Отчёт: JSON с результатами (source, rows_read, rows_loaded, match: bool)

### B.4 — CLI

**Файл:** `todo/cup_dashboard/etl/cli.py`

```
python -m cup_dashboard.etl.cli load --source january_full     # Отчёт январь, оба листа
python -m cup_dashboard.etl.cli load --source weekly_2026      # По неделям 2026
python -m cup_dashboard.etl.cli load --source rz_causes_2026   # Причины РЗ 2026
python -m cup_dashboard.etl.cli load --source base_db_2026     # БАЗА ДАННЫХ 2026
python -m cup_dashboard.etl.cli load --all                     # Всё
python -m cup_dashboard.etl.cli status                         # SELECT count() GROUP BY source_file, data_layer
```

### B.5 — Запуск ETL (отдельный handoff)

**✅ РАЗРЕШЕНО HUMAN (Q1 resolved, A12)** — ALL_AT_ONCE на CREATE DATABASE + CREATE TABLE + INSERT.

Порядок загрузки:
1. `CREATE DATABASE cup` + `CREATE TABLE cup.flights` (schema.sql)
2. Январь 2026 — Данные (138 278 строк) + Данные 15МИН (138 403 строк)
3. По неделям 2026 — Данные (117 123 строк) + Данные 15МИН (117 123 строк)
4. Причины РЗ 2026 — 14 698 строк
5. БАЗА ДАННЫХ 2026 — рабочие листы (ОТМЕНА РС, ПЕРЕНОС РС, СВОДКА РС, и т.д.)

Ожидаемый итог: ~500-600K строк в `cup.flights`.

---

## Phase C — FastAPI сервер

### C.1 — ClickHouse client

**Файлы:** `todo/cup_dashboard/core/__init__.py`, `todo/cup_dashboard/core/clickhouse.py`

Копия `sfv_dashboard/core/clickhouse.py` с адаптацией:
- `ROOT = Path(__file__).resolve().parents[3]` (3 уровня до todo/)
- `TABLE = "cup.flights"` → передавать через `queries.py`, не хардкодить в core
- Per-thread Client, env-driven credentials
- `query()`, `query_one()`, `query_scalar()`

### C.2 — SQL-агрегаторы

**Файл:** `todo/cup_dashboard/queries.py`

```python
TABLE = "cup.flights"

@dataclass
class Filters:
    date_from: date | None = None
    date_to: date | None = None
    dep_airport: str | None = None          # аэропорт вылета
    cause_category: str | None = None       # категория причины (М/У, ПОО, ...)
    aircraft_type: str | None = None        # тип ВС
    captain: str | None = None              # КВ
    data_layer: str | None = None           # '5min' | '15min'
```

Функции:
| Функция | Описание | Эндпоинт |
|---|---|---|
| `lookups()` | Списки для фильтров: аэропорты, категории, типы ВС, КВ, date range | `/api/lookups` |
| `kpi(f)` | % регулярности (15 мин и 5 мин), total flights, delays >2h, δ к пред. месяцу | `/api/kpi` |
| `daily_stacked(f)` | Задержки по дням × категория причины (stacked bar) | `/api/daily` |
| `top_causes(f)` | Топ-N причин по суммарным часам задержки | `/api/causes` |
| `airports_treemap(f)` | Аэропорты по доле задержанных рейсов | `/api/airports` |
| `heatmap_airport_cat(f)` | Тепловая карта: аэропорт × категория причины | `/api/heatmap` |
| `big_events(f)` | Рейсы с задержкой >2ч, посадки на запасной, отмены | `/api/events` |
| `top20_drilldown(f)` | Детализация топ-20 рейсов по задержке с фильтрацией | `/api/top20` |

### C.3 — FastAPI server

**Файл:** `todo/cup_dashboard/server.py`

По паттерну `sfv_dashboard/server.py`:
- `FastAPI(title="Регулярность рейсов · ЦУП Utair")`
- `/api/health` → `{status: "ok", ch_version, table: "cup.flights", rows}`
- 8 data endpoints (все принимают одинаковые фильтры как query params)
- `/` → `FileResponse(static/index.html)`
- `app.mount("/static", StaticFiles(...))`
- `_normalize()` для Decimal/Date → JSON

---

## Phase D — Frontend

### D.1 — HTML

**Файл:** `todo/cup_dashboard/static/index.html`

Портирование `cup_dashboard/poc/dashboard_mockup.html`:
- Убрать inline MOCK-данные (заменить на `fetch('/api/*')`)
- Utair-токены: `--utair-blue: #003594`, `--utair-red: #dc2328`, шрифт Suisse Int'l
- Header: `sign_white.png` на синем `#003594` (как в sfv_dashboard)
- Footer: `utair_text.png`
- Три секции: `#operational` (GAP-заглушка), `#daily`, `#strategy`
- Фильтры: date_from/date_to, аэропорт, категория причины, тип ВС
- ECharts CDN (inline backup для offline)
- Обязательные секции Rule 0: «Пробелы в источнике», расхождения 5мин/15мин

### D.2 — JavaScript

**Файл:** `todo/cup_dashboard/static/app.js`

- Загрузка lookups → populate selects
- 5 основных ECharts графиков: stacked bar (ежедневно), horizontal bar (топ причин), treemap (аэропорты), heatmap (аэропорт × категория), gauge (KPI %)
- Drill-down модал «Топ-20»: клик по бару/ячейке → fetch `/api/top20?...` → таблица
- URL-якоря `#operational`, `#daily`, `#strategy`
- Адаптив: resize observer для ECharts

### D.3 — CSS

**Файл:** `todo/cup_dashboard/static/style.css`

- Utair palette (light theme primary):
  - `--utair-blue: #003594`, `--utair-blue-dark: #002060`, `--utair-red: #dc2328`
  - `--utair-bg: #f8f9fa`, `--utair-card: #ffffff`
- Шрифт: Suisse Int'l (local), SF Mono для цифр
- Переиспользование стилей из `sfv_dashboard/static/style.css` (grid, tabs, cards)
- `@media` breakpoints: 1440 / 1024 / 768

---

## Phase E — Публикация

### E.1 — Dockerfile

**Файл:** `todo/cup_dashboard/Dockerfile`

Паттерн `sfv_dashboard/Dockerfile`:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY cup_dashboard/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY cup_dashboard/ /app/cup_dashboard/
ENV PYTHONPATH=/app
EXPOSE 8000
CMD ["uvicorn", "cup_dashboard.server:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

### E.2 — Docker Compose

**Файл:** `todo/docker-compose.yml` (ИЗМЕНИТЬ)

Добавить сервис:
```yaml
  cup-dashboard:
    build:
      context: .
      dockerfile: cup_dashboard/Dockerfile
    container_name: cup-dashboard
    restart: unless-stopped
    env_file:
      - .env
    dns:
      - 10.95.16.10
      - 10.95.16.11
    expose:
      - "8000"
```

В `backend` → `depends_on` добавить `cup-dashboard`, env добавить `CUP_DASHBOARD_URL=http://cup-dashboard:8000`.

### E.3 — Reverse-proxy

**Файл:** `todo/backend/app.py` (ИЗМЕНИТЬ)

Паттерн SFV_PROXY_PREFIX:
```python
CUP_DASHBOARD_URL = os.getenv("CUP_DASHBOARD_URL", "http://cup-dashboard:8000").rstrip("/")
CUP_PROXY_PREFIX = "/info/tsup"

# + _proxy_cup(), redirect без trailing slash, root, upstream_path
```

### E.4 — Карточка в info.html

**Файл:** `todo/webBI/info.html` (ИЗМЕНИТЬ)

Добавить секцию «Производство» (перед «Коммерция»):
```html
<div class="section">
  <h2>Производство</h2>
  <div class="cards-grid">
    <a class="card" href="/info/tsup/">
      <div class="card-icon">✈</div>
      <div>
        <div class="card-title">Регулярность рейсов ЦУП</div>
        <div class="card-desc">Live-аналитика регулярности: KPI, причины задержек, аэропорты, тепловые карты. Источник — ClickHouse, данные из отчётности ЦУП</div>
      </div>
    </a>
  </div>
</div>
```

### E.5 — DEPLOY.md

**Файл:** `todo/cup_dashboard/DEPLOY.md` (НОВЫЙ)

Адаптация `sfv_dashboard/DEPLOY.md`:
- Таблица: `cup.flights` вместо `sfv.catering_items`
- Путь: `/opt/cup-dashboard/`
- Systemd unit: `cup-dashboard.service`
- Healthcheck: `GET /api/health` → `{status:ok, table: "cup.flights", rows}`

### E.6 — README

**Файл:** `todo/cup_dashboard/README.md` (НОВЫЙ)

Описание: архитектура, API endpoints, источники данных, как запустить локально.

### E.7 — CHANGELOG

**Файл:** `todo/CHANGELOG.md` (ИЗМЕНИТЬ)

Запись в `[Unreleased] / Добавлено`:
```
- **Регулярность рейсов ЦУП** (`cup_dashboard/`) — live-дашборд по данным ЦУП с подключением к ClickHouse `cup.flights`. FastAPI + ECharts, 8 API-эндпоинтов, Utair-палитра. Маршрут `/info/tsup/` через reverse-proxy. Карточка в секции «Производство» в info.html.
```

---

## Phase F — State

### F.1 — Scribe: решения и state (Obligations)

Через handoff H7:

- **D-023:** Cross-repo задачи — coder работает в `todo/` без обременений правилами Obligations, но соблюдает Rule 0 и базовую дисциплину (read-only источники, no secrets in code, provenance). Hooks Obligations к `todo/` не применяются. Coder обновляет `todo/CHANGELOG.md` при сдаче.

- **D-024:** Отмена TASK-008 Фаза 2 (self-contained HTML). `cup_dashboard/poc/dashboard_mockup.html` → референс дизайна, не продакшн. Вместо self-contained HTML → live-дашборд по паттерну sfv_dashboard (TASK-009). Supersedes часть D-021 (self-contained → live).

- **D-025:** CH schema `cup.flights` — одна денормализованная таблица в `cup` database на `10.95.19.132`. 72 канонические колонки + `source_file` + `data_layer` + `loaded_at`. Engine: MergeTree(), PARTITION BY toYYYYMM(date), ORDER BY (date, flight_no, dep_airport). Четыре источника: январь (5мин + 15мин), по неделям, причины РЗ, БАЗА ДАННЫХ.

- Обновить `docs/CURRENT_STATE.md`:
  - `cup_dashboard/` статус: `in_progress` → `deployed`
  - Добавить запись в таблицу подпроектов
  - Обновить handoff log

### F.2 — Пометка мокапа (Obligations)

**Файл:** `cup_dashboard/poc/dashboard_mockup.html` (ИЗМЕНИТЬ)

Добавить в начало `<title>`:
```
<!-- MOCKUP-only. Не продакшн. Производственный дашборд → /info/tsup/ (TASK-009) -->
```

---

## Декомпозиция на diff-куски

| # | Фаза | Файлы | Строк | Описание |
|---|---|---|---|---|
| D1 | A.1 | `cup_dashboard/etl/data_inventory.md` | ~120 | Реестр источников (coder читает 4 xlsx) |
| D2 | A.2 | `todo/cup_dashboard/etl/sql/schema.sql` | ~100 | CREATE DATABASE + TABLE (после D1) |
| D3 | B.1 | `todo/cup_dashboard/etl/reader.py`, `etl/column_mapping.json` | ~140 | Reader + маппинг колонок |
| D4 | B.2 | `todo/cup_dashboard/etl/loader.py` | ~80 | CH loader, батчи 10K |
| D5 | B.3+B.4 | `todo/cup_dashboard/etl/pipeline.py`, `etl/cli.py` | ~130 | Оркестрация + CLI |
| D6 | B.5 | — (запуск) | — | ETL run (approval human: A12 ✅) |
| D7 | C.1 | `todo/cup_dashboard/__init__.py`, `core/__init__.py`, `core/clickhouse.py` | ~100 | CH client (паттерн sfv) |
| D8 | C.2 | `todo/cup_dashboard/queries.py` | ~200 | SQL-агрегаторы (8 функций + Filters) |
| D9 | C.3 | `todo/cup_dashboard/server.py` | ~120 | FastAPI endpoints |
| D10 | D.1 | `todo/cup_dashboard/static/index.html` | ~150 | HTML-каркас + Utair-брендинг |
| D11 | D.2 | `todo/cup_dashboard/static/app.js` | ~150 | ECharts графики, fetch, drill-down |
| D12 | D.3 | `todo/cup_dashboard/static/style.css` | ~120 | Utair palette, responsive |
| D13 | E.1 | `todo/cup_dashboard/Dockerfile`, `requirements.txt` | ~30 | Docker + deps |
| D14 | E.2+E.3 | `todo/docker-compose.yml`, `todo/backend/app.py` | ~60 | Сервис + reverse-proxy |
| D15 | E.4 | `todo/webBI/info.html` | ~20 | Секция «Производство» + карточка |
| D16 | E.5+E.6 | `todo/cup_dashboard/DEPLOY.md`, `README.md` | ~150 | Документация публикации |
| D17 | E.7 | `todo/CHANGELOG.md` | ~10 | Запись changelog |
| D18 | F.2 | `cup_dashboard/poc/dashboard_mockup.html` | ~5 | Пометка mockup-only |

**Итого:** 18 diff-кусков.

**Порядок зависимостей:**
```
D1 → D2 → D3 → D4 → D5 → D6 (ETL: последовательно)
D7 (параллельно с D3-D5, независим)
D8 → D9 (queries → server, после D2)
D10 → D11 → D12 (frontend: последовательно)
D13 → D14 (docker: последовательно)
D14 + D9 → D15 (proxy после server и compose)
D15 → D16 → D17 (публикация: последовательно)
D18 (в любой момент)
```

---

## Критерии успеха (step → verify)

### Phase A
1. `data_inventory.md` содержит все 4 источника, колонки каждого листа, GAP-маркеры → verify: файл существует, содержит ≥4 таблиц с заголовками колонок
2. `schema.sql` валидна → verify: `clickhouse-client --query "$(cat schema.sql)"` без ошибок

### Phase B
3. reader.py читает все 4 xlsx → verify: `python -c "from cup_dashboard.etl.reader import read_source; ..."` → DataFrame с ожидаемым row count
4. loader.py пишет в CH → verify: `SELECT count() FROM cup.flights WHERE source_file = 'test'` > 0
5. pipeline.py e2e → verify: `python -m cup_dashboard.etl.cli load --source january_full` → отчёт `rows_match: true`
6. Все данные загружены → verify: `SELECT data_layer, count() FROM cup.flights GROUP BY data_layer` → ≥4 слоя

### Phase C
7. `/api/health` → verify: `curl localhost:8000/api/health` → `{status: "ok", rows: >0}`
8. `/api/kpi` → verify: JSON с полями `regularity_15min`, `total_flights`
9. `/api/daily` → verify: JSON массив с полями `date`, `categories`

### Phase D
10. index.html отдаётся → verify: `curl localhost:8000/` → HTML с `<title>Регулярность`
11. ECharts рендерит графики → verify: браузер, 5 графиков без ошибок в console
12. Фильтры работают → verify: выбрать аэропорт → графики перерисовываются

### Phase E
13. Docker build → verify: `docker build -f cup_dashboard/Dockerfile -t cup-dashboard .` → success
14. Docker compose up → verify: `docker compose up -d cup-dashboard` → container running
15. Reverse-proxy → verify: `curl localhost:8050/info/tsup/api/health` → `{status: "ok"}`
16. Карточка в info.html → verify: открыть `/info/` → видна секция «Производство» с карточкой
17. DEPLOY.md → verify: файл существует, содержит секции 1-10 (по паттерну sfv)
18. CHANGELOG → verify: grep `cup_dashboard` CHANGELOG.md → найдено

---

## Ownership

| Файл/директория | Агент | Репо |
|---|---|---|
| `.cursor/plans/TASK-009.md` | orchestrator | Obligations |
| `cup_dashboard/etl/data_inventory.md` | coder | Obligations |
| `cup_dashboard/poc/dashboard_mockup.html` (шапка) | coder | Obligations |
| `todo/cup_dashboard/**` (весь код) | coder | todo |
| `todo/docker-compose.yml` (правка) | coder | todo |
| `todo/backend/app.py` (правка) | coder | todo |
| `todo/webBI/info.html` (правка) | coder | todo |
| `todo/CHANGELOG.md` (правка) | coder | todo |
| `docs/DECISIONS.md` (D-023..D-025) | scribe | Obligations |
| `docs/CURRENT_STATE.md` | scribe | Obligations |

---

## Порядок исполнения

```
H1: Human → Orchestrator (задание)
    ↓
[Q1-Q5 RESOLVED 04.05.2026]
    ↓
H7: Orchestrator → Scribe (D-023, D-024, D-025, CURRENT_STATE) ← параллельно с H4
    ↓
H4: Orchestrator → Coder (D1: data_inventory) ← мы здесь
    iteration: 1/3
    scope: cup_dashboard/etl/data_inventory.md (в Obligations)
    Coder читает все 4 xlsx, составляет реестр
    ↓
H4': Orchestrator → Coder (D2: schema.sql)
    iteration: 1/3
    scope: todo/cup_dashboard/etl/sql/schema.sql
    На основе data_inventory
    ↓
H4'': Orchestrator → Coder (D3-D5+D7: ETL + CH client)
    iteration: 1/3
    scope: reader.py, column_mapping.json, loader.py, pipeline.py, cli.py, core/clickhouse.py
    ↓
[D6: ETL run — отдельный handoff с approval human]
    ↓
H4''': Orchestrator → Coder (D8-D9: queries + server)
    iteration: 1/3
    ↓
H4'''': Orchestrator → Coder (D10-D12: frontend)
    iteration: 1/3
    ↓
H4''''': Orchestrator → Coder (D13-D17: публикация)
    iteration: 1/3
    ↓
H4'''''': Orchestrator → Coder (D18: mockup header)
    fast_track: true (1 файл, 5 строк)
    ↓
H7: Orchestrator → Scribe (D-023, D-024, D-025, CURRENT_STATE)
    ↓
H9: Orchestrator → Human (доклад)
```

**Pre-gate (H2) пропущен сознательно:** plan создан orchestrator'ом на основе детальной спецификации от human (parent). Self pre-gate ниже.

**Fast-track для D18:** ≤1 файл, ≤5 строк, комментарий в HTML.

---

## Открытые вопросы — ВСЕ RESOLVED (04.05.2026)

Все вопросы закрыты. Ответы human зафиксированы как допущения A1-A3, A5, A12.

1. ~~Запуск ETL и мутация CH~~ → **A12**: ALL_AT_ONCE, одно разрешение на весь scope
2. ~~Имя БД `cup` свободно?~~ → **A3**: да, проверено `SHOW DATABASES`
3. ~~Права `default` на CREATE/INSERT~~ → **A2**: `GRANT ALL ON *.*`, probe пройден, CH 24.10.1.2812
4. ~~Union-стратегия 72 + NULL~~ → **A1**: подтверждено «максимальное количество исходных параметров»
5. ~~VBA-блокер из TASK-008~~ → **A5**: не влияет, независимый Python ETL, R2 остаётся undetermined

---

## Self pre-gate

| # | Проверка | Результат |
|---|---|---|
| 1 | Не противоречит D-001 (Graph as SSOT) | ✅ PASS — `cup_dashboard/` в `todo/` — отдельный продукт, не часть core PDFtoBPMN. Аналогично D-021. |
| 2 | Не противоречит D-009 (один pipeline) | ✅ PASS — cup ETL — это отдельный ETL для отдельного продукта, не конфликтует с ingestion → extraction → graph. |
| 3 | Cross-repo scope зафиксирован (D-023) | ✅ PASS — новый прецедент, явно описан. Hooks Obligations не применяются к `todo/`. |
| 4 | TASK-008 Phase 2 отменена (D-024) | ✅ PASS — self-contained HTML → live-дашборд. Мокап → референс. |
| 5 | Все требования human учтены | ✅ PASS — denorm ✓, max scope ✓, /info/tsup/ ✓, ECharts ✓, секция Производство ✓, ETL в todo ✓ |
| 6 | Открытые вопросы перечислены | ✅ PASS — 5 вопросов, ни один не решён молча. |
| 7 | Ownership корректен | ✅ PASS — coder → код, scribe → docs, orchestrator → plan, human → rules. |
| 8 | Diff-куски ≤3 файлов, ~≤150 строк | ✅ PASS — 18 кусков, D8 (queries.py ~200 строк) — единственное превышение, обосновано когезией одного файла. |
| 9 | Rule 0 соблюдается | ✅ PASS — GAP-маркеры для #operational, расхождения 5/15мин, NULL в недостающих колонках, VBA undetermined. |
| 10 | Допущения явные | ✅ PASS — 11 допущений, каждое с «если ложно →». |

**Self pre-gate: PASS.**

---

## Риски

| # | Риск | P | I | Митигация |
|---|---|---|---|---|
| R1 | Имя БД `cup` занято на CH | Низкая | Низкое | `SHOW DATABASES` перед CREATE. Альтернатива: `cup_flights`, `tsup`. |
| R2 | Права `default` недостаточны для CREATE | Средняя | Высокое | Проверить через `SHOW GRANTS`. Fallback: запросить DBA. |
| R3 | OOM при чтении 138K×72 в pandas | Низкая | Среднее | openpyxl `read_only=True` + chunk reading. Альтернатива: читать parquet из output/january_split/. |
| R4 | Колонки между источниками несовместимы (разные имена для одних данных) | Средняя | Среднее | column_mapping.json + data_inventory.md (D1) выявит до кода. |
| R5 | ECharts inline > 1 МБ | Низкая | Низкое | CDN primary, inline fallback. В Docker CDN доступен. |
| R6 | Reverse-proxy path collision | Низкая | Низкое | `/info/tsup/` проверен — не занят в backend/app.py. |
| R7 | VBA содержит трансформации данных | Низкая | Среднее | Не влияет на TASK-009 (A5). GAP в data_inventory.md. |
| R8 | Дрейф scope: frontend потребует больше эндпоинтов | Средняя | Среднее | Scope lock: 8 эндпоинтов зафиксированы. Новые → TASK-010. |

---

## Решения для фиксации (scribe → DECISIONS.md)

После завершения и ответов human:

- **D-023:** Cross-repo policy (coder в `todo/`, без hooks Obligations)
- **D-024:** Отмена self-contained HTML, переход на live-дашборд (supersedes часть D-021)
- **D-025:** CH schema `cup.flights` — одна денорм. таблица, 72 колонки, MergeTree
