# TASK-003: Поведенческие гард-рейлы (Karpathy-skills интеграция)

## Цель
Интегрировать в правила и `.md` агентов 4 поведенческих принципа из репозитория
`forrestchang/andrej-karpathy-skills` (Think Before Coding, Simplicity First,
Surgical Changes, Goal-Driven Execution) — без введения новых агентов, новых
файлов правил и без изменения handoff-графа H1–H9.

Это **поведенческий слой**, дополняющий уже существующий **процессный слой**.
Никакая логика хуков, ownership и retry не меняется.

## Контекст
- Репозиторий-источник: https://github.com/forrestchang/andrej-karpathy-skills
- Это всего один файл `CLAUDE.md` с 4 правилами поведения LLM-кодера.
- В проекте сильно покрыт *процесс* (план/scope/non-goals/gates), слабо —
  *поведение внутри scope* (как именно думать, насколько коротко писать,
  что делать при неоднозначности).

## Scope

### Файлы: ИЗМЕНИТЬ
- `.cursor/rules/00_global_always.mdc` — добавить блок «Поведенческие принципы»
  между секциями «Процесс» и «Handoff-цепочка». ~10 строк.
- `.cursor/agents/orchestrator.md`:
  - в шаблон плана добавить поля «Допущения» и формат «Критерии успеха» как
    `step → verify`. ~12 строк.
  - в секцию Fast-track добавить условие автоматической отмены при >1 интерпретации
    или >30 строк. ~3 строки.
- `.cursor/agents/coder.md`:
  - добавить секцию «Принципы исполнения» (4 пункта). ~6 строк.
  - в payload H5 добавить ключ `diff_trace` с привязкой строк к пунктам плана. ~5 строк.
- `.cursor/agents/validator.md`:
  - в таблицу проверок post-gate `code` добавить две строки:
    `scope_creep` (FAIL) и `simplicity` (warning, не блокирующий). ~3 строки.
- `.cursor/agents/extractor.md`:
  - в секцию «Принципы извлечения» добавить пункт про неоднозначные фразы
    (выдавать оба варианта с `ambiguous: true`, не выбирать молча). ~2 строки.

### Файлы: НОВЫЙ
- (нет)

### ТЕСТЫ
- Эти файлы — конфиг агентов и markdown rules, не Python-код.
- Проверки: `head -1 .cursor/rules/00_global_always.mdc` — frontmatter не сломан.
- Все 6 тестов `tests/test_dev_graph.py` должны по-прежнему проходить (никакой
  Python не менялся).

## Non-goals
- НЕ создавать новый файл `.cursor/rules/60_behavior.mdc` (источник истины
  должен оставаться в `00_global_always.mdc`).
- НЕ создавать корневой `CLAUDE.md` (D-005 / D-011: модульные правила в
  `.cursor/rules/*.mdc`).
- НЕ менять handoff-цепочку H1–H9, только обогатить payload.
- НЕ менять hooks (`.cursor/hooks/*.py`).
- НЕ вводить нового агента «reviewer».
- НЕ менять `core/`, `scripts/`, `poc/`, `tests/`.

## Инварианты
- Все 11 решений в `docs/DECISIONS.md` остаются в силе.
- Hooks (`check_handoff`, `block_orchestrator_code`, `check_ownership`,
  `record_stop`) — не трогаются.
- LangGraph state схема не меняется.
- Существующие планы TASK-001/TASK-002 не затрагиваются.
- Передача `diff_trace` в H5 — необязательное поле (новый ключ payload),
  старые dispatch'и без него остаются валидными.

## Критерии успеха (step → verify)
1. `00_global_always.mdc` содержит секцию `## Поведенческие принципы`
   → verify: `rg "Поведенческие принципы" .cursor/rules/00_global_always.mdc` даёт 1 хит.
2. Шаблон плана в `orchestrator.md` содержит `## Допущения (assumptions)` и
   `step → verify` пример
   → verify: `rg "Допущения \(assumptions\)" .cursor/agents/orchestrator.md`,
   `rg "step → verify" .cursor/agents/orchestrator.md`.
3. `coder.md` содержит секцию `## Принципы исполнения` и `diff_trace` в payload H5
   → verify: `rg "Принципы исполнения" .cursor/agents/coder.md`,
   `rg "diff_trace" .cursor/agents/coder.md`.
4. `validator.md` содержит проверки `scope_creep` и `simplicity`
   → verify: `rg "scope_creep|simplicity" .cursor/agents/validator.md` — 2 хита.
5. `extractor.md` содержит фразу про `ambiguous`
   → verify: `rg "ambiguous" .cursor/agents/extractor.md`.
6. Все existing тесты по-прежнему зелёные
   → verify: `pytest tests/test_dev_graph.py -v` — 6/6 pass.

## Ownership
- В обычном цикле H1→H9 правки в `.cursor/rules/**` делает только human.
- Эта задача согласована устно human'ом (см. диалог), реализация — единичный
  PR без gates по согласию автора правил.

## Риски
1. Линтер frontmatter `.mdc` может ругнуться, если случайно сломать YAML —
   LOW. Митигация: правки только в теле, frontmatter не трогаем.
2. Дублирование смысла «не лезть в соседний код» (есть и в coder.md, и в
   00_global_always) — ACCEPTED. Сознательное дублирование, чтобы coder
   видел принцип в своём конфиге, а cross-agent правило — в global.
3. Несогласованные термины (`assumption` vs `допущение`) — LOW. Митигация:
   используем русские термины (`допущения`), английский — только в коде поля.

## Будущее (НЕ в этом TASK, отдельный план)
- Опциональный hook `diff_size_warn` (не блокирующий, после `afterFileEdit`):
  warn если суммарный diff текущей задачи >150 строк / >3 файлов.
  Требует tracking diff через state — нетривиально, отдельный план.
- Автоматическая проверка `diff_trace` в validator (сейчас — глазами по таблице).
