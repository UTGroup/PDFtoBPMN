# TASK-011: Статический дашборд «Таксономия IATA-732 (2028) + Data Lineage»

**Дата:** 2026-05-12
**Исполнитель:** scribe + coder (cross-repo: Obligations + todo)
**Зависимость:** TASK-010 (codifier analysis) — даёт исходный xlsx и понимание структуры.
**Не зависит от:** TASK-009 (live-дашборд ЦУП) — параллельный артефакт под `/info/iata732/`.

## Цель

Создать **отдельный статический SPA** рядом с дашбордом ЦУП, в котором:

1. **Вкладка «Таксономия IATA-732»** — иерархическое раскрытие 4-уровневой структуры будущего стандарта (GROUP → PROCESS → REASON → STAKEHOLDER), 4 493 полных кода. Поиск, экспорт, счётчики.
2. **Вкладка «Data Lineage»** — sankey-диаграмма каналов автоматического сбора данных под IATA-732 (A-CDM, ACARS DLY/DDM, DCS, MX, Manual) → группы IATA-732 → роли (stakeholders) → назначение (отчёты/биллинг/бенчмарк/B2B).
3. **Вкладка «Размерности»** — короткие визуализации: распределение по stakeholder, объём кодов в каждой GROUP, top-процессы.

Текущую реальность (Меридиан/ЦУП/IATA-730) **не трогаем** — это про будущий стандарт и сценарий его автоматизации.

## Скоуп

- Данные **статические** — JSON-файл рядом с дашбордом, без backend API. Источник — лист `IATA(28) Процесс+Причина+Отв.сл` (4493 строки) и `IATA(28) Процесс+Причина` (572 строки).
- URL: `/info/iata732/` (по аналогии с `/info/tsup/` для ЦУП).
- Интеграция с `kk-backend` — только 2 точки в `app.py` (редирект + index) и `app.mount` под статику. **API endpoint'ов нет.**
- Карточка в `webBI/info.html` в разделе «Производство» (или новом «Стандарты»).
- Стилистика — переиспользует Utair-палитру и шрифты из `cup-tsup` (тот же CSS-словарь переменных).

## Допущения

- **A1.** Источник `Кодификатор_ЦУП_МЕР_IATA_730_732.xlsx` остаётся истиной для всех 4493 кодов. Если IATA пересмотрит документ — перегенерация JSON (одна команда, скрипт версионируется).
- **A2.** Колонка `STAKEHOLDER SUBGROUP` может быть NaN — это случаи когда подгруппы не разворачиваются (например, `J — pax`). В JSON кладём `null`, в UI показываем как пустую.
- **A3.** Data Lineage — описан в отчёте `CUP_codifier_genesis_v1.md` § 4а (если будет добавлен) и в § 3 моего ответа в чате. 5 каналов источников, 4 направления назначения. **Это экспертная карта**, не из источника, помечена `(описано экспертом на основе индустриальной практики A-CDM/ACARS, без верификации Утайр)`.

## Rule 0

- В таксономии не интерпретируем NaN: если в колонке `STAKEHOLDER SUBGROUP` пусто — оставляем пусто, не подставляем родительский.
- Data Lineage помечаем как **экспертную карту**, не как факт из исходного файла. В сноске указываем источники (A-CDM, IATA AHM 732 reference).
- Маппинг IATA-730 → IATA-732 **не строим** на этом дашборде. Он есть в отчёте `CUP_codifier_genesis_v1.md` и в этом дашборде намеренно отсутствует — чтобы не мешать восприятию «чистого» нового стандарта.

## Артефакты

| Файл | Назначение |
|---|---|
| `output/iata732/build_codifier_json.py` | Скрипт сборки JSON из xlsx (Obligations) |
| `output/iata732/codifier.json` | Нормализованный иерархический JSON (~250 KB) |
| `todo/webBI/iata732/index.html` | HTML-каркас дашборда |
| `todo/webBI/iata732/static/style.css` | Стили (Utair-палитра) |
| `todo/webBI/iata732/static/app.js` | UI логика (ECharts sankey + tree-grid) |
| `todo/webBI/iata732/static/codifier.json` | Копия JSON для фронта (или symlink) |
| `todo/backend/app.py` (правки) | 2 точки: redirect + index, + 1 mount static |
| `todo/webBI/info.html` (правка) | Карточка-ссылка |

## Этапы

1. **A. Данные** — `output/iata732/build_codifier_json.py` строит `codifier.json` из листов 2 и 3.
   - Структура: `{ groups: [{ name, processes: [{ letter, name, reasons: [{ letter, name, code2, stakeholders: [{ letter, sub_letter, sub_name, code }] }] }] }] }`.
   - Tests inline: `assert sum(reasons_count) == 553`, `assert sum(codes_count) == 4493`.
2. **B. Frontend** — статический SPA.
   - Tabs: Таксономия / Lineage / Размерности.
   - Tree-grid (Таксономия): нативный HTML/JS, без сторонних UI-библиотек. Раскрытие click'ом.
   - Sankey (Lineage): ECharts (CDN, как в cup-tsup).
   - Donut/bar (Размерности): ECharts.
3. **C. Backend** — добавить:
   - `IATA732_PREFIX = "/info/iata732"`, `IATA732_STATIC_DIR = WEBBI_DIR / "iata732"`.
   - `@app.get(IATA732_PREFIX)` → редирект.
   - `@app.get(IATA732_PREFIX + "/")` → FileResponse(index.html).
   - `app.mount(IATA732_PREFIX + "/static", ...)`.
4. **D. info.html** — карточка в новом разделе «Стандарты и кодификаторы».
5. **E. Deploy** — backend файл копируется через Docker REST API в контейнер `kk-backend`, перезапуск, smoke-test `/info/iata732/`.

## Что НЕ входит

- ❌ Маппинг IATA-730 → IATA-732 — он уже в отчёте, в дашборде «чистый» новый стандарт.
- ❌ Реальные данные Утайр в IATA-732 (их пока нет — нечего отображать).
- ❌ Биллинг-калькулятор / KPI / ML-тренды — это TASK-012+.
- ❌ Связь с Меридианом/ЦУП — отдельная задача (TASK-010 уже разбирает разрывы).

## Ownership

- Obligations repo: scribe — план, отчёты, скрипт сборки JSON.
- todo repo: coder + publisher (для HTML) — webBI/iata732/* + backend/app.py.
- Human — финальная приёмка визуала.

## Результат (12.05.2026)

Дашборд опубликован на `/info/iata732/`, smoke по 14 URL зелёный, коммит `cb31846` в `origin/main` (todo).

| Артефакт | Статус |
|---|---|
| `output/iata732/build_codifier_json.py` (Obligations) | ✅ сделан |
| `output/iata732/codifier.json` (4 493 кодов) | ✅ сгенерирован |
| `webBI/iata732/{index.html, static/style.css, static/app.js, static/codifier.json}` (todo) | ✅ принято целевым агентом as-is |
| Backend routes (todo `backend/app.py`) | ✅ интегрировано (28 строк перед `/static` mount) |
| Карточка IATA-732 в `webBI/info.html` (todo) | ✅ через publisher-сабагент |
| Docker image rebuild + smoke | ✅ `docker compose build && up -d`, kk-backend healthy |

## Lessons (запись в DECISIONS.md → D-030)

**Что пошло не так у scribe/coder из Obligations:**
1. Сделан прямой PUT обновлённого `backend/app.py` в production-контейнер kk-backend **без** предварительного `git pull` в `/home/budnik_an/todo/`. Локальная копия `todo/backend/app.py` была устаревшей относительно `origin/main` (отсутствовали Keycloak SSO, on-demand-alerts, фильтры дублёров, новый cron 05:00, исключённые импорты `authenticate_domino`/`get_domino_token`).
2. Контейнер упал на `ImportError: authenticate_domino`. В попытке починить я вытянул pristine `app.py` из docker-образа — но образ был собран из ещё более старого коммита, и в нём не было Keycloak SSO. Принял это за «рабочую» версию и залил обратно, фактически снеся production-фичи.
3. Не прочитал `todo/.cursor/rules/portal-navigation.mdc` — там стандарт навигации `.pn-header-nav`/`.pn-breadcrumbs` (а не `.btn-back`), и правило «основной агент HTML напрямую не правит, есть publisher-сабагент». Моя карточка в `webBI/info.html` была вставлена напрямую StrReplace, что нарушает локальный governance.

**Как нужно было:**
1. `cd /home/budnik_an/todo && git pull origin main` перед любым правкой.
2. `ls /home/budnik_an/todo/.cursor/rules/ && cat .cursor/rules/portal-navigation.mdc` — прочитать правила целевого репо.
3. Делегировать HTML-вставку через publisher-сабагента (или хотя бы предупредить human).
4. Изменения backend деплоить через `docker compose build && up -d`, а не через PUT в running-контейнер (PUT — только если git был чистым).

**Регресс ликвидировал целевой агент** (`todo/` coder) коммитом `cb31846`: `git checkout HEAD -- backend/app.py webBI/info.html`, ре-вставка моих 28 строк IATA-732 в актуальный backend, повторная вставка карточки через publisher, rebuild image, smoke по 14 URL. Мой `webBI/iata732/` (фронт) принят без изменений.

**Не делать впредь:** прямой PUT в production-контейнер без `git pull` локальной копии, прямая правка `webBI/*.html` в репозитории `todo` (есть publisher).

---

# Phase 2: Data Lineage «Меридиан → IATA-730 → ЦУП → IATA-732» (13.05.2026)

**Триггер:** user-запрос. Текущая вкладка «Data Lineage» в `/info/iata732/` показывает техническую схему «откуда берутся коды» (5 каналов сбора A-CDM/ACARS/DCS/MX/Manual → IATA-732 GROUP). Её **заменяем** на семантический генезис четырёх систем кодирования причин задержек — это историческая логика «откуда что произошло».

## Цель

Сделать на вкладке «Data Lineage» дашборда `/info/iata732/`:

1. **KPI-полоса сверху** — 4 системы, 88 базовых кодов с маппингом, 161 ЦУП-детализация без кода Меридиана (Rule 0: видимый GAP), распределение confidence (high/medium/none).
2. **Sankey 4 колонки** — Меридиан → IATA-730 → ЦУП → IATA-732. Узлы агрегированы по группам каждого уровня. Толщина связей и цвет показывают confidence маппинга.
3. **Таблица 88+161 строк** — детальный mapping (по образцу § 3 из `CUP_codifier_genesis_v1.md`). С фильтрами по `kind`/`confidence` и поиском по тексту.
4. **Текстовая врезка** — объяснение каждого слоя (Меридиан = production-система Утайр; IATA-730 = действующий стандарт; ЦУП = надстройка для отчётности, аналитик вписывает 161 детализацию руками в Excel; IATA-732 = будущий стандарт 2028).

Старая sankey каналов **не сохраняется** — для канала-сбора есть отдельный текстовый блок «откуда коды берутся в реальности» (5 строк), его оставляем как краткую справку.

## Источник данных

`output/cup_codifier/genesis_full_table.csv` (271 строка, 14 колонок). Содержит:
- `kind`: detail_only (161) / both (64) / header_only (22) / mer_only (12) / iata730_only (12)
- `IATA730_num`, `IATA730_mnem`, `IATA730_text_en`, `IATA730_text_ru`
- `MER_code`, `MER_group`, `MER_descr`
- `IATA732_group`, `IATA732_code2`, `IATA732_process`, `IATA732_reason`
- `IATA732_confidence` (high 22 / medium 57 / none 7 / n/a 185)

## Rule 0

- 161 строка `detail_only` без `MER_code` — **видимая часть «вакуума»** между уровнями. Не сворачиваем, явно показываем как «работа аналитика руками» отдельным баром или цветовой выделенностью узлов.
- 12 `iata730_only` (IATA-730 коды, не покрытые Меридианом Утайр) и 12 `mer_only` (Меридиан-коды без соответствия в IATA-730) — тоже GAP-маркеры, видимы.
- Connection «Меридиан ↔ ЦУП» рисуется только если ЦУП-уровень реально надстраивает MER-группу детализациями. Если нет — связь не рисуем (а не дублируем).
- Confidence сохраняется в каждой связи и в каждой строке таблицы.

## Артефакты

| Файл | Назначение |
|---|---|
| `output/iata732/build_lineage_json.py` | Скрипт сборки lineage.json (Obligations) |
| `output/iata732/lineage.json` | Источник для фронта (Obligations) |
| `todo/webBI/iata732/static/lineage.json` | Копия для фронта (сжатая) |
| `todo/webBI/iata732/static/app.js` | Правка `renderLineage()` — sankey + table + KPI |
| `todo/webBI/iata732/index.html` | Правка вкладки `#lineage` через Publisher-сабагента |

## Ownership

- Obligations: scribe — план, скрипт, lineage.json, README на странице.
- todo:
  - **app.js** — coder напрямую (правило `webbi-html.mdc` действует на `*.html`, JS не покрыт).
  - **index.html** — через Publisher-сабагента.
  - **lineage.json** в static/ — раскладывает scribe (это не HTML, а data-asset).

## Что НЕ входит

- Реальные данные Утайр (объёмы задержек по кодам) — это уже есть в `/info/tsup/`, не повторяем.
- Сам кодификатор IATA-732 (4 493 кода) — это вкладка «Таксономия», не трогаем.
- Mapping recommendations / «какие коды добавить в Меридиан» — это уже есть в `CUP_codifier_analysis_v1.md`, прикрепляем ссылкой, в дашборд не интегрируем.

---

# Phase 3: Анатомия IATA-732 (компактное представление, 14.05.2026)

**Триггер:** user-запрос «расписать значение этих уровней» + «может в дашборде таксономию именно так сделаем и только по 732».

Цель — заменить «дерево из 4 493 узлов» на **педагогически-управляемое** компактное представление структуры стандарта. Идея: вместо одного гигантского tree-grid две формы материала с переключателем:

1. **Анатомия** (по умолчанию) — пять info-карточек уровней L1…L4a + каскадный селектор для пошаговой сборки кода + липкий «телескоп» внизу страницы, показывающий текущий выбор.
2. **Дерево** (старое наполнение) — сохраняется как второй режим. Полезно операторам, которые хотят найти существующий код по поиску («where is `KDR`?»).

User-уточнения (через AskQuestion 14.05):
- **tax_layout = toggle** — оба режима в одной вкладке `#tax`.
- **card_depth = compact** — info-карточки компактные: 4 строки (назначение / размер словаря / вопрос пользователя / пример). Полные алфавиты L2/L3/L4 — в раскрывающемся `<details>` блоке внутри карточки.
- **code_telescope = always** — sticky-панель внизу, обновляется по мере выбора в каскаде. Видна только когда активна вкладка Таксономия и режим Анатомия.

## Содержание info-карточек (источник — анализ структуры codifier.json)

| Уровень | Назначение | Размер словаря | Вопрос пользователя | Кодовое поле в XYZ |
|---|---|---|---|---|
| L1 Group | Хронологическая фаза оборота | 7, фиксированный | Когда: на прилёте / стоянке / вылете? | — (вычисляется из L2) |
| L2 Process | Технологический подэтап в фазе | 26 пар (G,letter); каждая буква уникальна глобально | Что именно: заправка/регистрация/посадка/документы? | 1-я буква |
| L3 Reason | Конкретная причина события | 553 пары (P,letter); среднее 21 на процесс | Почему: опоздание/ошибка/нехватка/повреждение/погода? | 2-я буква |
| L4 Stakeholder | Сторона ответственности | 15 фиксированных | Кто отвечает: airline/airport/ATC/pax/handler? | 3-я буква |
| L4a Sub-airline | Декомпозиция airline на службы | 8 фиксированных | Какая служба перевозчика: КЛО/ИАС/ЦУП/коммерция? | 4-я буква (только если L4=A) |

Полные расшифровки букв L2/L4/L4a — в `levels_meta.json` (статика).

## Каскадный селектор

5 dropdown'ов, фильтрация по выбранным предкам:
- Group ▼ (7) → Process ▼ (2–6) → Reason ▼ (9–26) → Stakeholder ▼ (1–13) → Sub ▼ (1–8, активен только при Stake=A).
- Каждый шаг **только применимые в данном контексте** значения (не глобальный словарь). Это техническая визуализация принципа Rule 0: «недопустимые комбинации не предлагаем».
- Кнопка «Сброс» очищает выбор.

## Телескоп кода (sticky внизу)

Лента из 5 ячеек: `G5 · P · A · A · F`. Под ней — итог: «**Код PAF** · группа: PAX Handling / процесс: приём pax / reason: позднее начало / stakeholder: airline / sub: commercial». Если пользователь выбрал не до конца — показываем «незаполнено».

## Артефакты

| Файл | Назначение | Owner |
|---|---|---|
| `output/iata732/build_levels_meta_json.py` | Скрипт сборки `levels_meta.json` из codifier.json | scribe (Obligations) |
| `output/iata732/levels_meta.json` | Семантическая мета 5 уровней (статика) | scribe |
| `todo/webBI/iata732/static/levels_meta.json` | Копия для фронта | scribe |
| `todo/webBI/iata732/static/app.js` | Новые функции `renderAnatomy`, `renderCascade`, `renderTelescope`, `switchTaxMode`. Старая `renderTree` сохраняется. | coder (правка напрямую, JS не покрыт `webbi-html.mdc`) |
| `todo/webBI/iata732/static/style.css` | Стили `.tax-mode-toggle`, `.lvl-cards`, `.lvl-card`, `.cascade`, `.code-telescope` | coder |
| `todo/webBI/iata732/index.html` | Перестройка секции `#tax`: добавить mode-toggle + два sub-сектиона + sticky телескоп | **Publisher sub-agent** (правило webbi-html.mdc) |

## Rule 0

- Карточки уровней содержат только то, что есть в исходных данных (codifier.json). Никаких «домыслов» про назначение поля без подтверждения структуры.
- В каскадном селекторе — только **реально существующие** в codifier комбинации. Если в Reason X нет Stakeholder Y — Y не показываем (а не блокируем серым).
- В описании кода НЕ утверждаем «X = строго это», только «в исходнике значится: <name_ru>».

## Ownership / Этапы

1. **scribe** — обновляет план (этот файл), создаёт `build_levels_meta_json.py`, генерирует `levels_meta.json`, копирует в `todo/webBI/iata732/static/`.
2. **coder** — пишет `renderAnatomy`/`renderCascade`/`renderTelescope` в `app.js`, дополняет `style.css`. Тест локально: открыть `file://` или dev-сервер.
3. **Publisher sub-agent** — единственно правомочный для правки `index.html`. Получает детальный промпт со списком вставок (toggle, sub-sections, sticky).
4. **coder** — smoke по URL `/info/iata732/`, проверка sticky на маленьких экранах.
5. **human** — финальная приёмка + git commit (по правилу D-030 коммитит только human).

## Что НЕ входит

- ❌ Удаление вкладки «Таксономия» в режиме «Дерево» — пользователь явно выбрал toggle (сохранить).
- ❌ Перевод текстов уровней на английский — оставляем русские из codifier.json + английские из name_en там, где они есть.
- ❌ Реальная статистика использования кодов в полётах ЮТэйр — это не часть IATA-732 как стандарта.
- ❌ Сравнение с Меридиан/IATA-730/ЦУП в этой вкладке — для этого есть отдельная вкладка `Data Lineage` (Phase 2).

---

# Phase 4: Структура IATA-732 на вкладке #lineage (14.05.2026)

**Триггер:** user-запрос «в data lineage сделаем только 732 с его структурой, а потом уже следующим этапом подумаем куда и как присадить остальное».

Меняем содержание вкладки `#lineage` дашборда `/info/iata732/`:
- Старая Sankey «Меридиан → IATA-730 → ЦУП → IATA-732» и таблица 249 строк (артефакты Phase 2) — **полностью удалены** из UI.
- Новая Sankey — 5-колоночная структура самого IATA-732: **Group → Process → Reason-cluster → Stakeholder → Sub-airline**.
- 553 уникальных reason-пары свёрнуты в **7 семантических кластеров** (тайминг / кадры / тех-инфра / документы / физика / среда / прочее). Это UX-приём для читаемости — точные reason'ы доступны через **drill-down по клику на узел Process**.
- KPI обновлены: 7 групп / 26 процессов / 553 reason'а / 15 stakeholders / 8 sub-airline / 4 493 кодов / 609 уникальных терминов / 7.4× сжатие.
- Легенда reason-кластеров — отдельным блоком над Sankey.
- Заголовок вкладки переименован: «Data Lineage» → «Структура».

User-уточнения (AskQuestion 14.05):
- **sankey_shape = 5col_clusters** — 5 колонок с агрегацией reason в 7 семантик.
- **reason_side = drilldown** — клик на Process → отдельная гистограмма «reasons этого процесса» ниже Sankey.
- **keep_lineage_table = replace_all** — старая таблица 249 строк уходит полностью (вернётся в отдельной phase 5 для Меридиан/730/ЦУП).

## Источник данных

`output/iata732/codifier.json` (4 493 строки), генерируется новым скриптом `build_structure_json.py`.

## Rule 0

- KPI и узлы Sankey собраны из codifier напрямую, без интерпретации.
- Кластеризация L3 — экспертная (помечена `cluster_source: "derived: typical IATA AHM 732 reason letter semantics"`), но **не подменяет данные**: точные reason'ы для каждого Process доступны через drill-down с буквой, code2 (XY*), name_ru/en и stakeholder_count.

## Артефакты

| Файл | Назначение | Owner |
|---|---|---|
| `output/iata732/build_structure_json.py` | Скрипт сборки `structure.json` из codifier | scribe (Obligations) |
| `output/iata732/structure.json` (~263 KB indented / 172 KB minified) | Sankey + KPI + drilldown | scribe |
| `todo/webBI/iata732/static/structure.json` | Копия для фронта | scribe |
| `todo/webBI/iata732/static/app.js` | Перепись `renderLineage` под structure.json + новый click handler `_renderProcessDrilldown` | coder |
| `todo/webBI/iata732/static/style.css` | Стили `.lineage-legend`, `.drilldown-wrap`, `.lkpi-accent` | coder |
| `todo/webBI/iata732/index.html` | Полная замена секции `#lineage` + переименование вкладки/заголовка | **Publisher sub-agent** |
| `output/iata732/build_levels_meta_json.py` | Синхронизация L3-кластеров (было 6 → стало 7) | scribe |

## Поведение UI

1. По умолчанию: Sankey 720px высоты, легенда сверху, KPI 8 карточек.
2. Клик на любой узел `col=1` (Process, типа `G5/P`) → внизу появляется анимированный блок drill-down: горизонтальная bar-chart всех reasons этого процесса, отсортированных по `stakeholder_count`. Цвет бара = цвет кластера reason.
3. Кнопка `✕` в drill-down — скрывает блок и обнуляет `_selectedProcess`.
4. Resize и темы (light/dark) обрабатываются через `_charts.lineage.resize()` и `_charts.drilldown.resize()`.

## Что НЕ входит

- ❌ Возврат Меридиан/730/ЦУП — это Phase 5 (отдельная вкладка «Соответствия», задача от пользователя в следующей итерации).
- ❌ Удаление `static/lineage.json` — пока оставляем (потребуется для Phase 5).
- ❌ Связь со старой таблицей 249 строк — удалена из UI, но сам lineage.json не удалён.
- ❌ CSV-экспорт structure.json — структурный артефакт, не оперативные данные.

## Smoke (14.05.2026)

| URL | Code | Size |
|---|---|---|
| `/info/iata732/` | 200 | 13 962 b |
| `/info/iata732/static/structure.json` | 200 | 175 523 b |
| `/info/iata732/static/levels_meta.json` | 200 | 16 458 b |
| `/info/iata732/static/codifier.json` | 200 | 543 668 b |
| `/info/iata732/static/app.js` | 200 | 36 616 b |
| `/info/iata732/static/style.css` | 200 | 23 703 b |

JS: `node --check` OK. Lint: 0. Publisher 12/12 критериев. `Data Lineage` не встречается. 6 новых id присутствуют по одному разу.
