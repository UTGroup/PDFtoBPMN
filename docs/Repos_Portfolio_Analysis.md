# Сводный анализ репозиториев — портфель albud1978 / BANGroup

> Дата: 2026‑04‑23. Проанализировано **10 публичных репозиториев** (8 у `albud1978` + 2 в организации `BANGroup`) и связь с локальным проектом `Obligations`. Репозиторий `albud1978/todo` **не существует** (404) — рядом по дате обновления только `albud1978/demo`, скорее всего имелся в виду он.

---

## 1. Карта аккаунтов и видимых репо

### 1.1. `albud1978` — личный аккаунт (8 публичных репо)

| Репо | Тип | Язык | Last update | Назначение |
|---|---|---|---|---|
| **`demo`** | own | HTML | 2026‑04‑23 | GitHub Pages‑витрина: `albud1978.github.io/demo/` — авто‑галерея HTML‑артефактов (QMS, ERM, Obligations, Infra, Edu, tt‑pipeline, literature) |
| **`Helicomponents`** | own | Python | 2026‑01‑29 | Helicopter Component Lifecycle Prediction — Agent‑Based симуляция на FLAME GPU + ClickHouse |
| **`CV`** | own | Python | 2025‑12‑21 | Computer Vision для гражданской авиации (YOLOv8/v11, SAM 2, RF‑DETR, Molmo2‑4B), Docker |
| **`ollama`** | own | JavaScript | 2025‑08‑21 | Локальный LLM‑стек (Ollama + Qwen2.5 + web‑чат + AI Sheets), Docker‑compose |
| `andrej-karpathy-skills` | fork | — | 2026‑04‑15 | Принципы LLM‑coding pitfalls (Karpathy), интегрированы в наши агенты |
| `planning-with-files` | fork | — | 2026‑01‑05 | Manus‑style persistent markdown planning (skill для агентов) |
| `llm-council` | fork | — | 2025‑11‑22 | LLM Council pattern (мульти‑LLM ансамбль) |
| `nanochat` | fork | — | 2025‑10‑23 | Минимальный chat‑скаффолд |

### 1.2. `BANGroup` — организация (2 репо)

| Репо | Тип | Язык | Last update | Назначение |
|---|---|---|---|---|
| **`PDFtoBPMN`** | own | Python | 2026‑04‑23 | **Источник истины** для локального `Obligations` — Digital QMS (PDF/DOCX → Knowledge Graph → BPMN/RACI/KPI) |
| **`YOLOv8tabletennis-seg`** | own | Python | 2026‑03‑21 | Table Tennis CV Score — YOLOv8 segmentation + Kalman tracking + scoring |

### 1.3. Локальный workspace (не на GitHub)

- `Obligations` (= рабочая копия `BANGroup/PDFtoBPMN`, ветка `v2-graphrag`).

---

## 2. Подробный разбор по репо

### 2.1. `BANGroup/PDFtoBPMN` (= local `Obligations`)
**Назначение:** «Digital QMS Backbone» — превращение бумажной СМК в исполняемый цифровой контур (Quality 4.0).

**Архитектура (D‑001/D‑009/D‑010):**
- Один pipeline `ingestion → typed extraction → graph + vector indexing`.
- `Organizational Knowledge Graph` — единственный SSOT.
- BPMN, RACI, KPI, Control — **views** из графа (не отдельные модели).

**Стек:** Python 3.12, Docling 2.80, EasyOCR / DeepSeek‑OCR / GLM‑OCR / Qwen2‑VL, NetworkX, LangGraph, Cursor multi‑agent (5 ролей: orchestrator/coder/validator/scribe/extractor) + 4 хука enforcement.

**Состояние:**
- Фаза 0 завершена (POC × 7, в т.ч. OCR/VLM benchmark из 7 моделей; Document Authority — 369 документов, 329 семейств; Page Classifier 397 страниц).
- MCP‑интеграции: `domino-keep` (СУБП/ЭСЗ), `domino-keep-bnd` (БНД, 1380 документов), `superset-utair`, `jira-utair`, `singularity-app`.
- Дашборды AS‑IS: ЦУП (RCA + Operational Regularity), Debt Control v5 с матрицей зрелости, SFV catering, КД‑РГ‑110‑05.

**Связь с другими репо:** прародитель/SSoR для всех HTML‑артефактов в `albud1978/demo`; methodology «Validation discipline» — импортирована из `Helicomponents`.

---

### 2.2. `albud1978/Helicomponents`
**Назначение:** прогноз жизненного цикла компонентов вертолётов (планеры Mi‑8Т/Mi‑8АМТ/Mi‑17/Mi‑26 + агрегаты), Agent‑Based симуляция флота.

**Стек:** FLAME GPU 2.0.0rc4 + CUDA 13.0, ClickHouse, Python 3.12 (pandas 2.3.3, numpy 2.2.6, cudf‑cu12 25.12.0, pyflamegpu 2.0.0rc4+cuda130).

**Ключевые особенности:**
- 7 status_id (operations / serviceable / repair / reserve / storage / inactive / unserviceable) + 6 битовых масок ошибок.
- Битовые маски типов ВС (МИ‑8Т=32, МИ‑8АМТ=64, МИ‑26=128).
- Параметризация ресурсов из `MD_Сomponents.xlsx` (`ll`, `oh`, `br`, `br2_mi17`).
- 2 датасета (`v_2025-07-04`, `v_2025-12-30`), 10 лет симуляции (3650 дней), MP2 экспорт в `sim_masterv2`.
- Жёсткая дисциплина «документированных хардкодов» с историей аудита.
- Полный set ETL: extract → transform → load → validate → analyze.

**Прямая связь с `Obligations`:**
- Правило `.cursor/rules/50_quality.mdc` явно ссылается: «Validation discipline (из Helicomponents)».
- Обе системы делят аэро‑тематику (вертолёты Utair) и data‑driven подход к компонентам качества.

**Связь с CV:** обе про авиатехнику Utair, обе используют CUDA‑стек на одном железе (RTX 5080).

**Релевантность Q4.0:** **высокая** — это **predictive quality / RCM** (Reliability‑Centered Maintenance) для парка ВС. То самое слабое место в моём предыдущем отчёте по Q4.0 («нет predictive quality / forecasting») — оно закрыто здесь.

---

### 2.3. `albud1978/CV` — Computer Vision для гражданской авиации
**Назначение:** детекция спецтехники, персонала, контроль СИЗ и регламентов на перроне.

**Стек:** PyTorch + YOLOv8/v11 (Ultralytics), YOLO‑World (zero‑shot), SAM 2 (Meta), RF‑DETR (Roboflow), Molmo2‑4B (VLM, ~19 ГБ), Docker + nvidia‑container‑toolkit, RTX 5080.

**Эталонная архитектура:** `docs/REFERENCE_ARCHITECTURE.md` — RF‑DETR + SAM 2 + SigLIP.

**Ключевые сценарии:**
- Auto‑labeling через YOLO‑World (zero‑shot) с экспортом в CVAT‑совместимом формате.
- Молмо2‑4B как Vision‑Language reasoning поверх кадров.
- Скрипт `download_models.sh` стягивает все веса разом.

**Связь с другими репо:**
- Делит файл `yolov8l-worldv2.pt` (94 МБ) с `Obligations` (тот же бинарник лежит в `BANGroup/PDFtoBPMN`).
- Делит CUDA‑стек и Docker‑паттерны с `Helicomponents` и `BANGroup/YOLOv8tabletennis-seg`.

**Релевантность Q4.0:** **средняя‑высокая** — это **inline visual quality control**: контроль соблюдения регламентов «по картинке» (СИЗ, безопасность перрона). Прямой кейс «Quality 4.0 Connectivity» — IoT‑видеопотоки → ML‑контроль → события в QMS.

---

### 2.4. `BANGroup/YOLOv8tabletennis-seg`
**Назначение:** автоматический подсчёт очков в настольном теннисе через CV.

**Стек:** YOLOv8 Instance Segmentation (5 классов: Ball / Net / Player1 / Player2 / Table) + OpenCV + Kalman Filter + NumPy. 261 размеченный кадр, train10/best.pt.

**Алгоритмы:**
- Детекция удара: вогнутая траектория + Y‑range ≥ 8px + curvature ≥ 5 + точка внутри полигона стола + min_frame_gap = 12 кадров.
- Детекция подачи (`v4_combined`): 2/3 сигналов — пауза > 2.5 с, подброс мяча, первый удар на своей стороне.
- Текущий статус: 70% детекции мяча, 15/15 ударов на тестовом видео; известная проблема — 60% обучающих данных в левой зоне.

**Связь:** использует **тот же мульти‑агентный паттерн Cursor** (`coder-tracking`, `coder-scoring`, `validator`) и concept «капсул контекста» (`docs/*_capsule.md`), что и `Obligations`.

**Релевантность Q4.0:** **низкая по тематике**, но **высокая методологически** — это испытательный полигон CV‑pipeline + multi‑agent workflow, отлаженный «на безопасной задаче».

---

### 2.5. `albud1978/demo` — GitHub Pages‑витрина артефактов
**Назначение:** опубликованные HTML‑артефакты с автогенерируемой главной страницей. URL: `https://albud1978.github.io/demo/`.

**Структура:**
| Папка | Содержимое | Тег |
|---|---|---|
| `Edu/` | mnist_explainer, periodic-table | ML, doc |
| `Infra/` | `nas_data_flow.html` (70 КБ) — поток данных NAS | data |
| `Obligations/` | `credinform_api_viewer.html` (130 КБ) — просмотрщик API ЕГРЮЛ/Credinform | data |
| **`QMS/`** | **4 артефакта по управлению качеством** (см. ниже) | QMS, doc |
| `literature/` | `voyna_i_mir.html` (141 КБ) — Толстой как long‑text | doc |
| `tt-pipeline/` | dashboard для table‑tennis | viz |

**QMS/ — артефакты прямо по теме Quality 4.0:**
| Файл | Назначение |
|---|---|
| `Misiura_Research_Toolkit_Dashboard.html` | Дашборд инструментария исследований |
| `Misiura_Research_Methodology_Handbook_v2.html` | Справочник по методологии (70 КБ) |
| `DONO_DataSources_Analysis_v1.html` | Критический анализ источников данных ДОНО × ERM × Resilience |
| `ERM_Operating_Model_v2.html` | Baseline операционной модели Enterprise Risk Management для авиакомпании (64 КБ) |

**Тех:** чистый HTML/CSS/JS, авто‑галерея через GitHub API `/git/trees/main?recursive=1`, тёмная тема, теги (ML/data/viz/QMS/doc), `meta.json` в каждой папке.

**Связь с другими:**
- `tt-pipeline/dashboard.html` — публичный фронт от `BANGroup/YOLOv8tabletennis-seg`.
- `Obligations/credinform_api_viewer.html` — UI для интеграции с ЕГРЮЛ/Credinform (не лежит в основном `Obligations`‑репо, вынесен сюда).
- `QMS/*` и `Infra/nas_data_flow.html` — это **публичная "Витрина Q4.0‑артефактов"**, отделённая от рабочих исходников.

**Релевантность Q4.0:** **очень высокая** — здесь живут **готовые публикуемые QMS/ERM‑дашборды** для коммуникации с бизнесом.

---

### 2.6. `albud1978/ollama` — локальный LLM‑стек
**Назначение:** docker‑compose для развёртывания локальной LLM (Qwen2.5 7B Instruct) с web‑чатом и опциональной интеграцией AI Sheets.

**Сервисы:** `ollama` (порт 11434, OpenAI‑совместимый `/v1`), `simple-chat` (Express, порт 3001), `aisheets` (порт 5173, dev‑сборка из исходников HF). Целевая платформа: Windows 10/11 + WSL2 + NVIDIA GPU.

**Особенности:** русская обёртка модели через `Modelfile.qwen2.5-ru` (фиксированный SYSTEM «Отвечай только по‑русски» + temp 0.4), полный powershell‑чек‑лист для брандмауэра.

**Связь:** инфраструктурная подложка для приватного inference в проектах `Obligations` (Qwen2.5‑VL для графики), `CV` (Molmo2‑4B), `Helicomponents` (если потребуется LLM‑слой).

**Релевантность Q4.0:** **средняя** — это **on‑premise privacy‑by‑design**, обязательная плита для обработки чувствительных СМК‑документов локально без отправки во внешние API.

---

### 2.7. Форки (внешние best practices, интегрированные в наши агенты)

| Репо | Что взяли |
|---|---|
| `andrej-karpathy-skills` | 4 принципа `CLAUDE.md`: Think Before Coding, Simplicity First, Surgical Changes, Goal‑Driven Execution → встроены в `.cursor/rules/` (наблюдение из чата [Karpathy skills + наш мультиагент](a49edd85-472d-42b7-a872-df85cfbe4715)) |
| `planning-with-files` | Manus‑style persistent markdown planning → задаёт паттерн `docs/plans/TASK-NNN.md` |
| `llm-council` | LLM Council ансамбль‑паттерн для критического ревью |
| `nanochat` | Минимальный chat‑скаффолд (учебный) |

---

## 3. Сквозные темы и взаимосвязи

```
                          ┌──────────────────────────┐
                          │   Cursor multi-agent     │
                          │  + .cursorrules + hooks  │
                          └────────────┬─────────────┘
                                       │ паттерн
            ┌──────────────────────────┼──────────────────────────┐
            ▼                          ▼                          ▼
   ┌──────────────────┐   ┌──────────────────────┐   ┌─────────────────────┐
   │ BANGroup/PDFtoBPMN│   │ BANGroup/YOLOv8tt-seg│  │  albud1978/CV       │
   │  = local           │   │  (CV polygon)        │   │  (perron CV)        │
   │  Obligations       │   └──────────────────────┘   └──────────┬──────────┘
   │  Digital QMS       │                                          │
   └────────┬───────────┘                                          │ shared
            │ artifacts                                            │ yolov8l-worldv2.pt
            ▼                                                      │
   ┌──────────────────┐                                            │
   │  albud1978/demo  │ ◄────── публичные HTML дашборды ───────────┤
   │  GitHub Pages    │   (QMS/Misiura, ERM, ДОНО, Infra/NAS,      │
   │  витрина         │    Obligations/credinform, tt-pipeline)    │
   └──────────────────┘                                            │
                                                                   │
   ┌──────────────────────────┐    "Validation discipline"          │
   │ albud1978/Helicomponents │ ────────────────────────────────────►
   │ FLAME GPU + ClickHouse   │   методология импортирована          │
   │ predictive quality MRO   │   в Obligations / 50_quality.mdc     │
   └──────────────────────────┘                                      │
                                                                     │
   ┌──────────────────────────┐    on-prem inference                 │
   │ albud1978/ollama         │ ────────────────────────────────────►
   │ Qwen2.5 + AI Sheets      │   (privacy для СМК и CV)             │
   └──────────────────────────┘
```

### 3.1. Что общее у всех «своих» репо

1. **Аэрокосмическая/авиационная отрасль** (Utair):
   - `Obligations` / `PDFtoBPMN` — нормативные документы СМК авиакомпании;
   - `Helicomponents` — флот вертолётов Mi‑8/17/26;
   - `CV` — детекция на перроне;
   - `BANGroup/YOLOv8tabletennis-seg` — единственное исключение (но используется как технологический полигон).

2. **Cursor multi‑agent + `.cursorrules`** — везде. Везде есть `.cursor/agents/`, `.cursor/rules/`. В `YOLOv8tt-seg` даже специализированные агенты `coder-tracking`/`coder-scoring`.

3. **Docker‑compose как стандарт развёртывания** (`Obligations/docker`, `CV`, `ollama`, `YOLOv8tt-seg`).

4. **NVIDIA CUDA‑стек на одном железе** (RTX 5080):
   - `Helicomponents`: CUDA 13.0 + FLAME GPU.
   - `CV`: CUDA 12.1 (Docker), Molmo2‑4B/SAM 2.
   - `Obligations`: Qwen2‑VL‑2B/Qwen2.5‑VL‑7B + DeepSeek‑OCR/GLM‑OCR (RTX 5080).
   - `ollama`: Qwen2.5 7B + локальный inference.

5. **Документация — ультра‑дисциплинированная**: все репо имеют `README.md` 7–18 КБ с разделами «Структура / Команды / Хардкоды / История изменений / Решение проблем». В `Helicomponents` — отдельный реестр документированных хардкодов.

6. **«Capsules / Rules / Agents» как метапаттерн** — даже в `YOLOv8tt-seg`: `docs/*_capsule.md` (`tracking_capsule.md`, `scoring_capsule.md`, `yolo_model_capsule.md`).

### 3.2. Чего нет/не видно

- Нет CI/CD на CodeQL/Actions (не использовалось активно).
- Нет общей monorepo‑структуры — стратегия «один репо = один продукт + общая витрина в `demo`».
- Нет terraform/k8s — везде docker‑compose.
- Нет общей библиотеки `shared/` (например, общего загрузчика моделей или GPU‑чекера).
- `Obligations` (наш рабочий) и `BANGroup/PDFtoBPMN` сейчас имеют **расхождение** (наш фронт ушёл вперёд: `v2-graphrag`, multi‑agent v2.1; в `BANGroup` лежит «v1 + переходная»).

---

## 4. Карта релевантности к Quality 4.0

| Репо | Quality 4.0 пилон | Конкретная роль |
|---|---|---|
| `Obligations` / `PDFtoBPMN` | Digital QMS, Compliance, Data, Management Systems | SSOT СМК как граф, BPMN/RACI/KPI views, multi‑agent QA |
| `demo/QMS/*` | Communication / Reporting | Публичные дашборды ERM, Misiura toolkit, ДОНО data sources |
| `Helicomponents` | Predictive Quality, Reliability | RCM флота — закрывает «нет predictive» из предыдущего отчёта |
| `CV` | Inline Visual Quality, Connectivity | Контроль СИЗ и регламентов перрона по видео |
| `demo/Infra/nas_data_flow` | Data Architecture | Карта потоков данных NAS — основа Connectivity |
| `demo/Obligations/credinform_api_viewer` | External Data / Supplier Quality | UI для ЕГРЮЛ — Supplier risk |
| `ollama` | Privacy / On‑prem AI | Локальный inference для чувствительных СМК |
| `YOLOv8tt-seg` | Methodology Lab | Полигон multi‑agent + CV pipeline |
| `andrej-karpathy-skills` | Engineering Culture | Принципы Karpathy в наших правилах |
| `planning-with-files` | Engineering Culture | Шаблон persistent planning |

---

## 5. Выводы

1. **Портфель — не россыпь, а система.** Минимум 6 из 10 репо подчинены одной отраслевой логике (Utair, авиация, СМК, флот, перрон). Остальные 4 — внешние best practices и инфраструктурный плита.

2. **`Obligations`/`PDFtoBPMN` — центральный узел Q4.0**, к которому подключаются:
   - `Helicomponents` как predictive‑quality слой;
   - `CV` как visual quality control;
   - `demo` как публичная витрина артефактов;
   - `ollama` как on‑prem inference;
   - форки‑skills как engineering discipline.

3. **`demo` — недооценённый актив.** В нём уже лежат 4 готовых QMS/ERM‑дашборда (Misiura Toolkit/Handbook, ДОНО Data Sources, ERM Operating Model). Это финальные артефакты, которые стоит интегрировать в Q4.0‑портфолио следующим шагом.

4. **Расхождение `Obligations` ↔ `BANGroup/PDFtoBPMN`** надо закрыть: либо влить ветку `v2-graphrag` в публичный репо, либо чётко зафиксировать публичный как «v1 frozen», а локальный как «v2 internal».

5. **Что усилить:**
   - Объединить дашборды (`Obligations/docs/dashboards/*.html` + `demo/QMS/*` + `demo/Infra/*`) в единый «Quality 4.0 Cockpit» на GitHub Pages.
   - Подключить `Helicomponents` как **источник KPI надёжности** для дашборда `tsup_as_is_dashboard` (regularity ↔ MRO predictive).
   - Для `CV` — сделать **«events bridge» в Knowledge Graph** `Obligations` (нарушение СИЗ → событие в QMS).
   - Опубликовать общий `shared/` репо (общий GPU‑чекер, model loader, MCP‑клиенты) — снимет копипасту между `CV` / `Helicomponents` / `Obligations`.

6. **Репо `todo` отсутствует** — если нужен новый репо для todo‑трекинга задач Q4.0‑программы, его можно создать как `albud1978/q4-roadmap` или подключить существующий `docs/plans/TASK-NNN.md` Cursor‑паттерн.

---

## 6. Источник данных

- GitHub API: `https://api.github.com/users/albud1978/repos`, `https://api.github.com/orgs/BANGroup/repositories`, contents/трeеs каждого репо.
- README прочитаны напрямую через `raw.githubusercontent.com`.
- Локальные файлы `Obligations`: `.cursor/rules/*.mdc`, `docs/CURRENT_STATE.md`, `docs/Architecture_v2.1.md`, `docs/Gold_Standard_Methodology.md`.
- Чаты: см. предыдущий отчёт `docs/Quality_4_0_Portfolio.md` (если будет создан) и `agent-transcripts`.
