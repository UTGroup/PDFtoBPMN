# TASK-013: синхронизация cup_overlay с matching.json (SSOT)

## Контекст и цель
- В дашборде `/info/iata732/` вкладки **Таксономия** и **Структура** работают на разных pipeline:
  - Таксономия — бейджи матчинга из `matching.json` (TASK-012, expert + override).
  - Структура — overlay из `cup_overlay.json` (TASK-011, наивный word-match).
- Из-за этого узлы `G7/Z/*` (ATFM) в Sankey отображаются как uncovered, хотя в Таксономии у них уже стоят бейджи матчинга (MER 83 «Временный режим а/п назнач.» → G7/Z/B/Q и т.д.).
- Дополнительно: catch-all stakeholder Z (not attributable) в overlay получает 8 ЦУП-кодов из M/У+ПРЧ+СБОЙ, которые семантически должны были быть в S:K (aircraft) / S:L (aircraft maintenance) / S:N (flight ops). Это ложно-положительные в Z и ложно-отрицательные в K/L/N.

**Цель**: переключить `build_cup_overlay_json.py` на чтение `matching.json:by_iata732_node` как **единственный источник истины**. Дерево Таксономии и Sankey Структуры должны показывать одни и те же бейджи/coverage на одних и тех же узлах.

## Не входит в scope
- Не править логику матчинга в `matching.json` (TASK-012 уже корректен).
- Не менять UI / app.js / index.html, кроме копии regenerated JSON.
- Не запускать batch processing / Claude API.
- Не трогать `build_cup_to_732_mapping.py`, `build_cup_lineage_json.py`.

## Источники данных
- **SSOT**: `output/cup_codifier/matching.json` (TASK-012).
  - `by_iata732_node[code]` — для 4-знаковых IATA-732 кодов вида `G{n}/{P}/{R}/{S}` (либо `G{n}/{P}/{R}/{Sub}` для PRa).
    - `mer` — список MER expert-маппингов с полями `code`, `name_ru`, `mer_group`, `confidence`, `note`.
    - `cup` — список ЦУП-источников с `code`, `confidence`, `source`.
    - `match_status` — итоговый.
  - `by_mer_code[code]` — обратный индекс MER → IATA-732 targets.
  - `by_cup_code[code]` — обратный индекс ЦУП → IATA-732 targets.
- **Структура осей** (общая со structure.json):
  - Колонки overlay: `G:G{n}`, `P:G{n}/{P}`, `S:{S}`, `U:{Sub}` — 4 оси.
- **Reason-уровень (L3)**: в overlay reason-колонка отсутствует (D-031), но reason-буква `{R}` входит как 3-й символ кода и доступна через drill-down. Reason agregation для overlay не нужен.

## Логика covered/uncovered (вариант A)
Для каждого узла overlay (G, P, S, U):
1. Узел `covered`, если в `matching.json:by_iata732_node` существует ХОТЯ БЫ ОДИН 4-знаковый код с этой осью, у которого `mer != []` ИЛИ `cup != []`.
2. Узел `uncovered`, если все 4-знаковые коды с этой осью имеют пустые `mer` и `cup`.

### Сбор данных для covered-узла
- `cup_codes` — объединение всех ЦУП-кодов из `cup` массивов всех 4-знаковых кодов под этим узлом (дедуп по code).
- `cup_mer_groups` — уникальные MER-группы из ЦУП-источников + из MER expert-маппингов.
- `cup_examples` — до 8 примеров строк ЦУП с приоритетом: `expert_iata` > `expert_internal` > `override_shifted` > `word_match` (по полю `source` в matching.json). Из `by_cup_code` достаём конкретные строки.
- `mer_experts` — НОВОЕ поле: список MER expert-маппингов (для тултипа «через какие AHM-коды попало»). Поля: `mer_code`, `name_ru`, `confidence`, `note`, `via` (например `AHM 730 AE`).
- `confidence` — `high`, если есть expert-маппинг; `medium`, если только override; `low`, если только word-match.

## Ожидаемый эффект
После перегенерации:
- `G:G7` covered (через AHM 730 ATFM-коды и РЖМ 82/83 + 82.1/83.1).
- `P:G7/Z` covered (через AHM 730 AT/AX/AE/AW/AM/AS и оба INTERNAL_UTAIR).
- `S:O` covered (MER 89 «Ограничения в а/п вылета» + INTERNAL_UTAIR 83.1).
- `S:Q` covered (MER 83 «Временный режим а/п назнач.»).
- `S:T` covered (INTERNAL_UTAIR 82.1 «Ковёр»).
- `S:S` covered (INTERNAL_UTAIR 82.1 alt).
- `S:Z` — остаются только реально-неклассифицированные ЦУП-коды (или 0, если все эти 8 кодов есть в matching.json с другими таргетами).
- `S:I/K/L/M/N/R/X` — останутся uncovered ровно в том объёме, в котором в Таксономии нет бейджей (честный GAP по Rule 0).

## Реализация (coder)
- Файл: `output/cup_codifier/build_cup_overlay_json.py`.
- Точки врезки:
  - Заменить чтение `cup_to_732_mapping.json` на чтение `matching.json`.
  - Переписать функцию агрегации по осям через `by_iata732_node`.
  - Сохранить выходную JSON-схему: `version`, `principle`, `source_files`, `kpi`, `summary_by_axis`, `overlay`. Добавить опциональное поле `mer_experts` в узлах overlay (для тултипа).
- Не менять имена существующих полей (`status`, `cup_rows`, `cup_mer_count`, `cup_mer_groups`, `cup_examples`, `confidence`).
- KPI пересчитать: `coverage_pct = covered_nodes / total_nodes_732 * 100`.

## Smoke (≥4 проверки)
1. `python3 output/cup_codifier/build_cup_overlay_json.py` отработал без ошибок.
2. `coverage_pct` ≥ 60% (было 60.7%, должно подрасти).
3. `overlay['G:G7']['status'] == 'covered'`.
4. `overlay['P:G7/Z']['status'] == 'covered'`.
5. `overlay['S:Q']['status'] == 'covered'` (через MER 83).
6. Узел `S:I` (passenger) остаётся `uncovered` (нет expert-маппинга в matching.json по пассажирам в G7).
7. `cup_overlay.json` валидный JSON, копия в `todo/webBI/iata732/static/cup_overlay.json` синхронизирована (минификация).

## Risks
- В `matching.json` reason-буква входит в код 4 символами, но overlay использует 4-колоночную ось (без reason). Нужно правильно проецировать (фильтровать по позиции в коде, не по reason).
- Sub-airline (PRa-коды) в `matching.json` могут лежать как 4-й символ `a` вместо stakeholder. Проверить, как matching.json кодирует PRa vs PRS, и не смешать.
- Если matching.json не покрывает какой-то узел структуры, который в старом overlay был covered через word-match — это регрессия. Нужно сравнить и обсудить, если такие есть. Эти случаи лучше обозначить как «честный gap» по Rule 0, а не имитировать word-match'ем.

## Affected
- `output/cup_codifier/build_cup_overlay_json.py` (rewrite ~50–60% кода).
- `output/cup_codifier/cup_overlay.json` (regenerate).
- `todo/webBI/iata732/static/cup_overlay.json` (copy minified).
- `docs/DECISIONS.md` — добавить D-037 о единой SSOT через matching.json.
- `docs/CURRENT_STATE.md` — обновить блок TASK-012 пометкой о синхронизации.

## Цикл
- 1 итерация. Если smoke падает — fix-up в той же итерации.
- Git commit: только после "PASS smoke" + явного OK от human.
