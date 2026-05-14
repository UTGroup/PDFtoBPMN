# TASK-012 — Матчинг ЦУП ↔ MER ↔ IATA-732 в дереве Таксономии + дельта-CSV для Меридиана

**Статус:** черновик плана (orchestrator, ожидает согласования human → coder).
**Тип:** функциональное расширение дашборда `/info/iata732/` + новый экспортёр.
**Связанные задачи:** TASK-010 (анализ кодификатора), TASK-011 (дашборд IATA-732), D-001 (graph as SSOT).
**Соблюдение Rule 0:** все пробелы в источнике (Excel-кодификатор) демонстрируются, а не замещаются.

---

## 1. Цель

Превратить вкладку **«Таксономия»** в дашборде `/info/iata732/` из чистого справочника IATA-732 в **карту соответствия 732 ↔ ЦУП ↔ MER**, а кнопку «Экспорт» — в **готовый дельта-CSV для апгрейда справочника Меридиана** в формате SAP ОЗМ-style (action / target / old → new / source).

### Acceptance criteria
- Каждый узел дерева (Process / Reason / Stakeholder) показывает два бейджа: статус матчинга с ЦУП и с MER (✅ / 🟡 / ⚠).
- При раскрытии reason доступен список конкретных кодов ЦУП и MER, привязанных к этой позиции IATA-732.
- Кнопка «Скачать CSV для апгрейда Меридиана» отдаёт файл с дельта-операциями (`ADD` / `RENAME` / `REMAP` / `DEPRECATE`), пригодный к прямой обработке разработчиком Меридиана.
- Сдвиг колонки IATA в строках r72-r80 Excel зафиксирован override-таблицей, виден в логе сборки.
- Два внутренних кода ЮТэйр (82.1 «Ковер», 83.1 «военные ограничения») явно помечены как `internal_utair`, без скрытой подгонки под IATA AHM 730.

### Out of scope (по уточнениям human)
- Отдельный ТЗ-документ (PDF/MD) — не делаем, только CSV.
- Внешний валидатор маппинга — не привлекаем; сборка маркируется как «черновик 1.0».
- Срок жёсткий — нет.
- Импорт-формат XLSX по специальному шаблону Меридиана — не нужен.

---

## 2. Входные данные

| Источник | Путь | Что берём |
|---|---|---|
| Excel-кодификатор | `input2/ЦУП/Отчетность/Кодификатор_ЦУП_МЕР_IATA_730_732.xlsx` | лист `ЦУП_МЕР_IATA` (272 строки): MER-код, MER-описание, MER-группа, IATA(AHM 730)-код |
| Готовый IATA-732 | `output/iata732/codifier.json` | полный кодификатор 732 (7/26/553/15/8) |
| Готовый ЦУП-маппинг | `output/cup_codifier/cup_to_732_mapping.json` | ЦУП-коды → IATA-732 оси (создан в TASK-010) |
| `MER_AXES` | `output/cup_codifier/build_cup_to_732_mapping.py` | словарь MER-группа → IATA-732 оси (черновик) |

### Что нужно собрать заново
- **`mer_to_732_mapping.json`** — для каждого MER-кода (1–99 + 82.1 + 83.1) указать:
  - `mer_code`, `mer_name_ru`, `mer_group`
  - `iata730_code`, `iata730_name_en` (с учётом override сдвига)
  - `iata732_targets`: список `{group, process, reason, stakeholder, confidence, source}` — возможные позиции 732
  - `kind`: `iata_aligned` / `internal_utair` / `gap`

---

## 3. Override-таблица сдвига Excel (Rule 0: показываем, а не маскируем)

В `build_mer_to_732_mapping.py` ввести **именованный блок `MER_IATA_OVERRIDE`** для строк r72-r80 листа `ЦУП_МЕР_IATA`. Каждая запись содержит источник правки и комментарий.

```python
# r74 столбец D в Excel содержит заголовок-разделитель «AIRPORT AND GOVERNMENTAL AUTHORITIES»,
# а столбец IATA для строк r72-r80 сдвинут на одну позицию вниз относительно столбца MER.
# Восстановление по смысловому совпадению MER-описание ↔ IATA-733 name_en (см. диалог 2026-05-14).
MER_IATA_OVERRIDE = {
  # (row_in_xlsx, mer_code) → (iata730_code, iata730_name_en, kind, note)
  (72, "82.1"): (None, None,                                       "internal_utair", "режим Ковер — внутренний код ЮТэйр, нет пары в IATA AHM 730"),
  (73,  83  ): ("83 (AE)", "ATFM due to RESTRICTION AT DESTINATION AIRPORT",   "iata_aligned", "восстановлено по сдвигу r72-r80"),
  (74, "83.1"): (None, None,                                       "internal_utair", "военные ограничения — внутренний код ЮТэйр, нет пары в IATA AHM 730 (ближайший — 89 AM с упоминанием military exercise)"),
  (75,  84  ): ("84 (AW)", "ATFM due to WEATHER AT DESTINATION",                "iata_aligned", "восстановлено по сдвигу"),
  (76,  85  ): ("85 (AS)", "MANDATORY SECURITY",                                 "iata_aligned", "восстановлено по сдвигу"),
  (77,  86  ): ("86 (AG)", "IMMIGRATION, CUSTOMS, HEALTH",                       "iata_aligned", "восстановлено по сдвигу"),
  (78,  87  ): ("87 (AF)", "AIRPORT FACILITIES",                                 "iata_aligned", "восстановлено по сдвигу"),
  (79,  88  ): ("88 (AD)", "RESTRICTIONS AT AIRPORT OF DESTINATION",             "iata_aligned", "восстановлено по сдвигу"),
  (80,  89  ): ("89 (AM)", "RESTRICTIONS AT AIRPORT OF DEPARTURE",               "iata_aligned", "восстановлено по сдвигу"),
}
```

При логировании сборки **обязательно** напечатать:

```
⚠ Применён override MER-IATA: 9 строк (r72-r80), причина — сдвиг колонки IATA в Excel-источнике.
   Подробности — таблица MER_IATA_OVERRIDE в build_mer_to_732_mapping.py.
```

В UI дашборда (бейдж рядом с этими MER-кодами) — иконка 🔧 «исправлено в импорте, см. журнал».

### IATA-732 мэппинг для двух internal-кодов

| MER | Предлагаемый IATA-732 target | confidence | Альтернатива |
|---|---|---|---|
| 82.1 «Ковер» | `G7 / Z / I` (departure restrictions / network restrictions / governmental authorities) | medium | `G7 / Y / I` если уже после готовности |
| 83.1 «военные» | `G1 / C / X · M` (inbound activity delaying outbound / extraordinary / military) | medium | `S / X / P` если контекст ATFM en-route военные учения |

Coder при имплементации проверяет, какой target чаще встречается в фактических данных регулярности — это и берёт за основной.

---

## 4. Структура `matching.json` (единый ключ для UI)

Один файл, который потребляет дерево Таксономии и экспортёр CSV.

```jsonc
{
  "version": "1.0",
  "generated_at": "2026-05-14T...",
  "sources": ["codifier.json", "cup_to_732_mapping.json", "mer_to_732_mapping.json"],
  "override_applied": {
    "mer_iata_shift": {"rows": "r72-r80", "count": 9, "see": "build_mer_to_732_mapping.py:MER_IATA_OVERRIDE"}
  },

  "by_iata732_node": {
    "G2/D/A:K": {                              // ключ узла дерева
      "iata732_code": "DAK",
      "cup": [{"code": "01.05", "name": "...", "confidence": "high"}, ...],
      "mer": [{"code": 26, "name": "DAMAGE TO AIRCRAFT...", "name_ru": "...", "confidence": "high"}],
      "match_status": "full"                    // full | partial | gap
    },
    ...
  },

  "by_mer_code": {
    "82.1": { "mer_name_ru": "режим Ковер", "kind": "internal_utair", "iata732_targets": [{...}], "alt": [{...}] },
    "83.1": { "mer_name_ru": "военные ограничения", "kind": "internal_utair", "iata732_targets": [{...}] },
    ...
  },

  "by_cup_code": { "01.05": {...}, ... },

  "summary": {
    "iata732_nodes_total": 553,
    "iata732_nodes_with_full_match": ...,
    "iata732_nodes_with_partial":     ...,
    "iata732_nodes_with_gap":         ...,
    "mer_codes_total": 99,
    "mer_codes_aligned": ...,
    "mer_codes_internal_utair": 2,
    "cup_codes_total": ...,
    "cup_codes_orphan": ...
  }
}
```

---

## 5. Дельта-CSV для апгрейда Меридиана

**Формат:** один CSV, плоская таблица. Каждая строка = одно атомарное действие над справочником Меридиана. Логика — как в SAP ОЗМ-импортах: «список изменений», который разработчик прогоняет одной операцией.

### Колонки
| # | name | пример | описание |
|---|---|---|---|
| 1 | `action` | `ADD`,`RENAME`,`REMAP`,`DEPRECATE`,`NO-CHANGE` | тип операции над Меридианом |
| 2 | `mer_code_target` | `26` или `82.1` | целевой код в Меридиане |
| 3 | `mer_name_current` | `ПОВРЕЖДЕНИЕ ВС...` | как сейчас написано в Меридиане (если есть) |
| 4 | `mer_name_proposed` | `ПОВРЕЖДЕНИЕ ВС НА ПЕРРОНЕ (G2/D/K)` | как должно быть после апгрейда |
| 5 | `mer_group` | `СБОЙ`,`М/У`,... | группа Меридиана (без изменений) |
| 6 | `iata730_code` | `26` или `89 (AM)` | предшествующий стандарт |
| 7 | `iata732_target` | `DAK` или `G7/Z/I` | финальный код в IATA-732 |
| 8 | `iata732_group` | `G2` | для группировки в импорте |
| 9 | `iata732_process_ru` | `груз на позиции` | для читателя |
| 10 | `iata732_reason_ru` | `повреждение при погрузке` | для читателя |
| 11 | `iata732_stakeholder` | `K` | L4 |
| 12 | `iata732_subairline` | пусто или `E` | L4a, если применимо |
| 13 | `cup_codes_linked` | `01.05;01.07` | список кодов ЦУП, привязанных к тому же IATA-732 узлу |
| 14 | `confidence` | `high`,`medium`,`low`,`unknown` | уверенность маппинга |
| 15 | `source` | `excel:ЦУП_МЕР_IATA:r26`, `override:mer_shift`, `derived` | откуда взято |
| 16 | `comment` | свободный текст | пояснение, если non-trivial |

### Семантика action
- **`ADD`** — кода нет в Меридиане, нужно завести (поля 3 пустые, 4 — новое имя).
- **`RENAME`** — код есть, но название устарело / некорректно (поле 3 — текущее, 4 — новое).
- **`REMAP`** — код привязан к старому IATA-730, нужно перепривязать к IATA-732.
- **`DEPRECATE`** — кода нет смысла поддерживать после миграции (нет пары в 732).
- **`NO-CHANGE`** — всё ок, миграция не требует изменений (информативная строка).

### Тестовый пример строк (для проверки формата при имплементации)

```csv
action,mer_code_target,mer_name_current,mer_name_proposed,...,confidence,source,comment
RENAME,26,"ПОВРЕЖДЕНИЕ ВС...",  "ПОВРЕЖДЕНИЕ ВС НА ПЕРРОНЕ (G2/D/K)", ..., high, excel:r28, "выравнивание под 732"
ADD,82.1,,                       "Ковер — закрытие пространства правительством (G7/Z/I)", ..., medium, override:mer_shift, "internal_utair, нет пары в 730"
ADD,83.1,,                       "Военные ограничения (G1/C/X·M)",      ..., medium, override:mer_shift, "internal_utair"
REMAP,83,"Временный режим а/п назнач.","Временный режим а/п назнач. (G7/Z/I)", ..., high, override:mer_shift, "ранее ошибочно стоял в строке 84 AW; исправлено override"
NO-CHANGE,11,"Поздняя регистрация","Поздняя регистрация (G5/P/A)", ..., high, excel:r13, ""
```

---

## 6. UI: бейджи в дереве Таксономии

### Размещение
Дерево уже отрисовывается функциями `makeGroupNode`, `makeProcessNode`, `makeReasonNode`, `makeStakeholderNode` в `static/app.js`. Бейджи добавляются **справа от существующего `tx-meta`**.

### Визуал
```
G2/D — груз на позиции                                  [ЦУП ✓ 12]  [MER ✓ 1]
  └─ B — поздняя приёмка на склад                        [ЦУП ✓ 02]  [MER ✓ 26]
       └─ K — ground handler                            [ЦУП 🟡 -]   [MER ⚠ -]
                                                         ↑ partial   ↑ gap
```

### Состояния бейджа
- ✅ `match-full` — есть прямой матч на этом уровне (цвет: utair-green)
- 🟡 `match-partial` — матч на уровне родителя, на текущем нет (цвет: utair-orange)
- ⚠ `match-gap` — матча нет вообще (цвет: utair-red)
- 🔧 `match-override` — данные восстановлены через MER_IATA_OVERRIDE (badge с подсказкой)

### Клик
- Клик на ЦУП-бейдж — модалка со списком ЦУП-кодов и их описаниями.
- Клик на MER-бейдж — модалка со списком MER-кодов, описаний и кнопкой «Скопировать».
- В модалке также: confidence маппинга, source (где взято), кнопка «Скачать строки CSV для этой ветки».

### Кнопка экспорта
- В шапке вкладки «Таксономия» добавить **`Скачать CSV для апгрейда Меридиана`** рядом с существующей `Экспорт CSV`.
- Сейчас существующая кнопка делает дамп всех 4493 кодов IATA-732 — её **не трогаем**, переименуем подпись для ясности на `Скачать сырой кодификатор IATA-732 (CSV)`.

---

## 7. Этапы реализации

| Phase | Что делаем | Файлы (≤3 на phase) | Owner |
|---|---|---|---|
| **P0** | **Hot-fix существующего UI** (не относится к матчингу, но запрошен вместе с TASK-012, 2026-05-14): (1) убрать `<span class="tag-future">FUTURE STANDARD</span>` из шапки `index.html` — после исследования о реальной стадии (опубликован с 2022 г.) бейдж стал нерелевантным; (2) на Sankey в режиме «+CUP Overlay» **показать коды ЦУП непосредственно на узле** (а не только в тултипе) — компактным суффиксом к label узла, например `G2/D · груз на позиции [ЦУП 01.05, 01.07]`, с правилом «не более 3 кодов, остальные `+N` с тултипом полного списка». Источник кодов — массив `cup_examples` в `cup_overlay.json`. Smoke: `grep "tag-future" index.html` → 0; визуально на overlay у covered-узлов виден список кодов ЦУП. | `webBI/iata732/static/app.js`, `webBI/iata732/static/style.css`, `webBI/iata732/index.html` (через Publisher) | coder + Publisher |
| **P1** | `build_mer_to_732_mapping.py` — чтение Excel, override-блок, прогрев. Smoke: 99+2 MER-кодов в выходном JSON, 9 строк override залогированы. | `output/cup_codifier/build_mer_to_732_mapping.py`, `output/cup_codifier/mer_to_732_mapping.json` | coder |
| **P2** | `build_matching_json.py` — объединение codifier + cup + mer в `matching.json`. Smoke: ключи `by_iata732_node`, `by_mer_code`, `by_cup_code` заполнены, summary считается. | `output/cup_codifier/build_matching_json.py`, `output/cup_codifier/matching.json`, `webBI/iata732/static/matching.json` | coder |
| **P3** | `build_meridian_upgrade_csv.py` — дельта-CSV. Smoke: 99+2 строк, корректные action-значения, no NaN. | `output/cup_codifier/build_meridian_upgrade_csv.py`, `output/cup_codifier/meridian_upgrade_v1.csv` | coder |
| **P4** | Frontend: расширение `makeProcessNode`/`makeReasonNode`/`makeStakeholderNode` бейджами + модалка с кодами. CSS под бейджи. | `webBI/iata732/static/app.js`, `webBI/iata732/static/style.css` | coder |
| **P5** | Кнопка экспорта в шапке Таксономии + endpoint (или статический файл) для скачивания CSV. Переименовать существующую кнопку. | `webBI/iata732/index.html` (через Publisher!), `webBI/iata732/static/app.js` | coder + Publisher для HTML |
| **P6** | Smoke + публикация. Проверка `/info/iata732/`: бейджи видны, модалка открывается, обе кнопки скачивают разные CSV. Документация — короткий блок в `docs/CURRENT_STATE.md`. | `docs/CURRENT_STATE.md`, `docs/DECISIONS.md` (декларация о матчинге) | scribe + coder |

**Каждая phase ≤ 3 файлов, ≤ 150 строк диффа, отдельный handoff coder ↔ validator.**

---

## 8. Открытые риски и assumptions

| # | Риск/Assumption | Mitigation |
|---|---|---|
| R1 | MER-маппинг в Excel неполный для некоторых низкочастотных кодов (например, 26.1 и подобные дроби) | при сборке логируем `mer_codes_skipped`; в CSV они идут с action=`NO-CHANGE` + comment «не маппится» |
| R2 | `83.1 военные` может быть и `M`-stakeholder, и `P`-ATFM en-route — в плане оба варианта | coder выбирает по фактической частоте; решение фиксируется в DECISIONS.md одной строкой |
| R3 | UI бейджей на 553+ узлах может перегрузить дерево | бейджи рисуются лениво, по мере раскрытия родителей |
| R4 | CSV в дельта-формате может быть не сразу понятен разработчику Меридиана | в шапке CSV — комментарий-блок (`# action ADD = …` и т.д.) на 6 строк |
| R5 | Существующая кнопка «Экспорт CSV» сейчас отдаёт сырой дамп — пользователи могут спутать с новой | переименовываем подпись (`Сырой кодификатор IATA-732 (CSV)` vs `CSV для апгрейда Меридиана`) и располагаем рядом |

---

## 9. Согласование

**Готов к согласованию human после ответа на:**
- ничего, все 6 вопросов уже отвечены 2026-05-14, override и трактовки 82.1/83.1 подтверждены.

**После согласования:**
1. Передаю P1 coder'у (handoff H4 по схеме из `00_global_always.mdc`).
2. Validator проверяет каждый phase в pre-gate (план vs реализация) и post-gate (diff + smoke).
3. Scribe фиксирует DECISIONS.md по итогам реализации (override-блок, выбор для 83.1 и т.д.).

**Estimated total effort:** 6 phases × ≤3 файлов × ≤150 строк = ~900 строк кода + публикация. Реалистично 1 рабочий день одного coder'а при отсутствии блокеров.
