"""TASK-014 follow-up: для каждой строки `by_mer_code` из matching.json
(71 iata_aligned + 9 прочих = 80 MER) указать **AMOS-источник** в формате
«цепочка от ВС → дефект → ATA → причина».

Это аналитический справочник, **физически данные AMOS не подтягиваются**.
Каждая запись содержит:
  * `mer_code` / `mer_name_ru` / `iata730_code` — точная цитата.
  * `amos_relevant` — bool. True если MER семантически отражает
    отказ / повреждение / ТО / замену ВС / запчасти.
  * `amos_chain` — цепочка от Aircraft к причине отказа (см. ANCHOR_CHAIN).
  * `amos_primary_apn` / `amos_primary_table` / `amos_field_hint`.
  * `note` — Rule 0 пояснение, если применимо.

Источник логики «от ВС»: amos-db-explorer.html (модули `aircraft`, `ac`, `wo`,
`mel`, `rm`, `moc`, `spec2k`).  APN — каталог
[`output/amos_layer/amos_apn_catalog.json`](output/amos_layer/amos_apn_catalog.json).

Выход:
  output/amos_layer/mer_amos_sources.json
  output/amos_layer/mer_amos_sources.csv
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path("/home/budnik_an/Obligations")
MATCHING = ROOT / "output" / "cup_codifier" / "matching.json"
OUT_DIR = ROOT / "output" / "amos_layer"
OUT_JSON = OUT_DIR / "mer_amos_sources.json"
OUT_CSV = OUT_DIR / "mer_amos_sources.csv"


# ---------- Aircraft-centric цепочка AMOS-обращения ------------------------ #

# Стандартная цепочка lookup'а от неисправного ВС к причине.  Используется
# как общий "anchor chain" — в записях MER указывается, до какого шага доходит
# конкретный случай.

ANCHOR_CHAIN = [
    {
        "step": 1,
        "node": "aircraft",
        "apn": "0308",
        "apn_name": "Aircraft Administration",
        "table_hint": "ac.aircraft, ac.ac_registr",
        "field_hint": "ac_registr / ac_typ / msn",
        "purpose": "вход в AMOS по хвостовому номеру ВС",
    },
    {
        "step": 2,
        "node": "workorder",
        "apn": "1418",
        "apn_name": "Workorder",
        "table_hint": "wo.wo_header, wo.wo_event_chain, jc.jc_header",
        "field_hint": "wo_no / short_text / defect_desc / status",
        "purpose": "перечень нарядов (snags/defects/scheduled) по ВС",
    },
    {
        "step": 3,
        "node": "ata_chapter",
        "apn": "—",
        "apn_name": "spec2k lookup",
        "table_hint": "spec2k.* + wo.wo_header.ata_chapter",
        "field_hint": "ata_chapter / subchapter",
        "purpose": "классификация неисправности по ATA chapter",
    },
    {
        "step": 4,
        "node": "defect_cause",
        "apn": "0354",
        "apn_name": "Failure Confirmation",
        "table_hint": "rm.failure_*, moc.moc_case",
        "field_hint": "failure_code / confirmation_status / pilot_report",
        "purpose": "подтверждённая причина (BITE / pirep / inspection)",
    },
    {
        "step": 5,
        "node": "deferral_or_close",
        "apn": "0273",
        "apn_name": "MEL Manual Administration",
        "table_hint": "mel.mel_*, wo.wo_header (deferral_link)",
        "field_hint": "mel_code / cat / open_date / deferral_ref",
        "purpose": "(опционально) отложен по MEL или сразу закрыт",
    },
    {
        "step": 6,
        "node": "reliability_aggregation",
        "apn": "0399",
        "apn_name": "Systems Reliability",
        "table_hint": "rm.*",
        "field_hint": "ATA / MTBF / removal_count / occurrence_rate",
        "purpose": "(опционально) агрегация надёжности по ATA",
    },
]


# ---------- Hardcoded роутинг MER → шаги цепочки -------------------------- #
# `chain_steps_used` — каких шагов цепочки достаточно для этого MER.
# Если `amos_relevant=False`, AMOS не источник — указано в `not_amos_reason`.

# Дефолт: операционка / handling / pax / cargo / atfm — не AMOS.
NOT_AMOS_REASON = {
    "passenger_flow": "пассажирский поток (handling / DCS), источник — IATA-732 process G5/P",
    "cargo_mail": "грузо-почтовый поток, источник — IATA-732 process G2/D",
    "ground_handling": "наземное обслуживание, источник — IATA-732 process G3/H",
    "crew_ops": "лётный/кабинный экипаж, источник — IATA-732 process G4/N или S:N",
    "atfm_airport": "ATFM/режимы а/п, источник — IATA-732 process G7/Z",
    "weather": "метеоусловия, источник — IATA-732 process G6/W",
    "catering": "бортпитание, источник — IATA-732 process G4/L",
    "documents": "документы/admin, источник — IATA-732 process G1/A",
    "fuelling": "заправка топливом — handling, source IATA-732 process G3/E",
    "deicing": "противообл. обработка — handling, source IATA-732 process G6/W",
    "ppx": "post-causal segment ППС — derived",
    "security": "САБ / security, source S:S",
    "airline_internal": "внутренний код ЮТэйр без IATA-эквивалента",
    "transit": "транзит/трансфер пассажиров, источник — IATA-732 process G5/P",
}


# Карта `mer_code (str)` → роутинг.  Поля:
#   amos_relevant: bool
#   primary_apn / primary_apn_name / primary_table / primary_field
#   chain_steps_used: list[int] из ANCHOR_CHAIN
#   note (опционально)
#   not_amos_reason (опционально, если amos_relevant=False)

MER_AMOS_ROUTING: dict[str, dict] = {
    # ---- AMOS-источники: отказы / тех. причины ВС ----
    "41": {  # Неисправность мат. части ВС
        "amos_relevant": True,
        "primary_apn": "1418",
        "primary_apn_name": "Workorder",
        "primary_table": "wo.wo_header",
        "primary_field": "defect_desc / ata_chapter / status",
        "chain_steps_used": [1, 2, 3, 4, 5, 6],
        "note": "ключевой AMOS-кейс: snag/defect ВС, разворачивается через всю цепочку",
    },
    "42": {  # Плановое ТО
        "amos_relevant": True,
        "primary_apn": "1844",
        "primary_apn_name": "Maintenance Forecast",
        "primary_table": "mevt.*, msc.*",
        "primary_field": "task / interval / due_date / aircraft / ata",
        "chain_steps_used": [1, 2, 3],
        "note": "плановое ТО — APN 1844 + Maintenance Event (APN 2151)",
    },
    "44": {  # Зап. части и ремонтн. оборудование
        "amos_relevant": True,
        "primary_apn": "0204",
        "primary_apn_name": "Parts Consumption Forecast",
        "primary_table": "part.*, od.*",
        "primary_field": "part_no / status / location",
        "chain_steps_used": [1, 2, 3],
        "note": "связь с APN 1208 Shipment Tracking при ожидании поставки",
    },
    "46": {  # Замена ВС/типа ВС по тех. причине
        "amos_relevant": True,
        "primary_apn": "0308",
        "primary_apn_name": "Aircraft Administration",
        "primary_table": "ac.aircraft, wo.wo_header",
        "primary_field": "ac_status / linked_wo / replacement_ac_registr",
        "chain_steps_used": [1, 2, 3, 4],
        "note": "swap борта вследствие AMOS-инцидента; AMOS — источник причины",
    },
    "47": {  # Отсутствие ВС по тех. причинам
        "amos_relevant": True,
        "primary_apn": "1683",
        "primary_apn_name": "Technical Availability Performance",
        "primary_table": "ac.aircraft, mevt.*, wo.wo_header",
        "primary_field": "downtime / aog_status / ata",
        "chain_steps_used": [1, 2, 3, 4],
        "note": "AOG / unscheduled grounding — состояние ac.aircraft + Reliability",
    },
    "48": {  # Внеплановое изменение компоновки
        "amos_relevant": True,
        "primary_apn": "0308",
        "primary_apn_name": "Aircraft Administration",
        "primary_table": "cm.*, ac.aircraft",
        "primary_field": "config / cabin_layout / change_date",
        "chain_steps_used": [1, 2],
        "note": "Configuration Management (модуль `cm` в db-explorer)",
    },
    "51": {  # Поврежд. ВС в полете/на руле
        "amos_relevant": True,
        "primary_apn": "1418",
        "primary_apn_name": "Workorder",
        "primary_table": "wo.wo_header, moc.moc_case",
        "primary_field": "damage_desc / inspection / ata",
        "chain_steps_used": [1, 2, 3, 4],
        "note": "повреждение ВС — fresh defect + APN 0354 Failure Confirmation",
    },
    "52": {  # Повреждение ВС на земле
        "amos_relevant": True,
        "primary_apn": "1418",
        "primary_apn_name": "Workorder",
        "primary_table": "wo.wo_header, moc.moc_case",
        "primary_field": "damage_desc / inspection / ata",
        "chain_steps_used": [1, 2, 3, 4],
        "note": "ground damage — отдельный snag, обычно с инвестигацией QA (`qa.*`)",
    },
    # ---- Косвенно AMOS (но первичный источник — handling) ----
    "43": {  # Запуск от УВЗ/Ожидание роднички
        "amos_relevant": False,
        "not_amos_reason": "GPU/ground power unit — это GSE handling; AMOS может зафиксировать как ATA-49/24 servicing, но первичная регистрация — handler",
        "primary_apn": "1418",
        "primary_apn_name": "Workorder (если квалифицируется как ATA-24/49)",
        "primary_table": "wo.wo_header",
        "primary_field": "ata=24/49",
        "chain_steps_used": [],
        "note": "пограничный — handling/GSE; AMOS не основной источник",
    },
    "45": {  # Зап. части для транспортировки
        "amos_relevant": True,
        "primary_apn": "1208",
        "primary_apn_name": "Shipment Tracking",
        "primary_table": "od.*, sh.*",
        "primary_field": "shipment_status / required_date / component",
        "chain_steps_used": [1, 2],
        "note": "ожидание поставки запчастей; цепочка не доходит до ATA chapter в самом AMOS",
    },
    # ---- Operations: handling / DCS / paх / cargo / crew / atfm / weather ----
    "9":   {"amos_relevant": False, "not_amos_reason": NOT_AMOS_REASON["airline_internal"], "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "11":  {"amos_relevant": False, "not_amos_reason": NOT_AMOS_REASON["passenger_flow"], "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "12":  {"amos_relevant": False, "not_amos_reason": NOT_AMOS_REASON["passenger_flow"], "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "13":  {"amos_relevant": False, "not_amos_reason": NOT_AMOS_REASON["passenger_flow"], "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "14":  {"amos_relevant": False, "not_amos_reason": NOT_AMOS_REASON["passenger_flow"], "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "15":  {"amos_relevant": False, "not_amos_reason": NOT_AMOS_REASON["passenger_flow"], "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "16":  {"amos_relevant": False, "not_amos_reason": "коммерческое решение заказчика (chartered)", "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "17":  {"amos_relevant": False, "not_amos_reason": NOT_AMOS_REASON["catering"], "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "18":  {"amos_relevant": False, "not_amos_reason": NOT_AMOS_REASON["passenger_flow"], "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "19":  {"amos_relevant": False, "not_amos_reason": NOT_AMOS_REASON["passenger_flow"], "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "21":  {"amos_relevant": False, "not_amos_reason": NOT_AMOS_REASON["cargo_mail"], "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "22":  {"amos_relevant": False, "not_amos_reason": NOT_AMOS_REASON["cargo_mail"], "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "23":  {"amos_relevant": False, "not_amos_reason": NOT_AMOS_REASON["cargo_mail"], "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "24":  {"amos_relevant": False, "not_amos_reason": NOT_AMOS_REASON["cargo_mail"], "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "25":  {"amos_relevant": False, "not_amos_reason": NOT_AMOS_REASON["cargo_mail"], "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "27":  {"amos_relevant": False, "not_amos_reason": NOT_AMOS_REASON["cargo_mail"], "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "28":  {"amos_relevant": False, "not_amos_reason": NOT_AMOS_REASON["cargo_mail"], "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "31":  {"amos_relevant": False, "not_amos_reason": NOT_AMOS_REASON["documents"], "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "32":  {"amos_relevant": False, "not_amos_reason": NOT_AMOS_REASON["cargo_mail"], "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "33":  {"amos_relevant": False, "not_amos_reason": NOT_AMOS_REASON["ground_handling"], "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "34":  {"amos_relevant": False, "not_amos_reason": NOT_AMOS_REASON["ground_handling"], "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "35":  {"amos_relevant": False, "not_amos_reason": NOT_AMOS_REASON["ground_handling"], "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "36":  {"amos_relevant": False, "not_amos_reason": NOT_AMOS_REASON["fuelling"], "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "37":  {"amos_relevant": False, "not_amos_reason": NOT_AMOS_REASON["catering"], "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "38":  {"amos_relevant": False, "not_amos_reason": NOT_AMOS_REASON["ground_handling"], "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "39":  {"amos_relevant": False, "not_amos_reason": NOT_AMOS_REASON["ground_handling"], "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "55":  {"amos_relevant": False, "not_amos_reason": NOT_AMOS_REASON["passenger_flow"], "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "56":  {"amos_relevant": False, "not_amos_reason": NOT_AMOS_REASON["cargo_mail"], "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "61":  {"amos_relevant": False, "not_amos_reason": NOT_AMOS_REASON["crew_ops"], "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "62":  {"amos_relevant": False, "not_amos_reason": NOT_AMOS_REASON["crew_ops"], "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "63":  {"amos_relevant": False, "not_amos_reason": NOT_AMOS_REASON["crew_ops"], "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "64":  {"amos_relevant": False, "not_amos_reason": NOT_AMOS_REASON["crew_ops"], "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "65":  {"amos_relevant": False, "not_amos_reason": NOT_AMOS_REASON["crew_ops"], "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "66":  {"amos_relevant": False, "not_amos_reason": NOT_AMOS_REASON["crew_ops"], "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "67":  {"amos_relevant": False, "not_amos_reason": NOT_AMOS_REASON["crew_ops"], "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "68":  {"amos_relevant": False, "not_amos_reason": NOT_AMOS_REASON["crew_ops"], "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "69":  {"amos_relevant": False, "not_amos_reason": NOT_AMOS_REASON["security"], "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "71":  {"amos_relevant": False, "not_amos_reason": NOT_AMOS_REASON["weather"], "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "72":  {"amos_relevant": False, "not_amos_reason": NOT_AMOS_REASON["weather"], "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "73":  {"amos_relevant": False, "not_amos_reason": NOT_AMOS_REASON["weather"], "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "75":  {"amos_relevant": False, "not_amos_reason": NOT_AMOS_REASON["deicing"], "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "76":  {"amos_relevant": False, "not_amos_reason": NOT_AMOS_REASON["weather"], "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "77":  {"amos_relevant": False, "not_amos_reason": NOT_AMOS_REASON["weather"], "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "81":  {"amos_relevant": False, "not_amos_reason": NOT_AMOS_REASON["atfm_airport"], "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "82":  {"amos_relevant": False, "not_amos_reason": NOT_AMOS_REASON["atfm_airport"], "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "83":  {"amos_relevant": False, "not_amos_reason": NOT_AMOS_REASON["atfm_airport"], "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "84":  {"amos_relevant": False, "not_amos_reason": NOT_AMOS_REASON["atfm_airport"], "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "85":  {"amos_relevant": False, "not_amos_reason": NOT_AMOS_REASON["security"], "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "86":  {"amos_relevant": False, "not_amos_reason": "регуляторный (погран./мед.) — S:G", "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "87":  {"amos_relevant": False, "not_amos_reason": NOT_AMOS_REASON["atfm_airport"], "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "88":  {"amos_relevant": False, "not_amos_reason": NOT_AMOS_REASON["atfm_airport"], "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "89":  {"amos_relevant": False, "not_amos_reason": NOT_AMOS_REASON["atfm_airport"], "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "91":  {"amos_relevant": False, "not_amos_reason": NOT_AMOS_REASON["transit"], "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "92":  {"amos_relevant": False, "not_amos_reason": NOT_AMOS_REASON["transit"], "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "93":  {"amos_relevant": False, "not_amos_reason": NOT_AMOS_REASON["ppx"], "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "93.1": {"amos_relevant": False, "not_amos_reason": NOT_AMOS_REASON["ppx"], "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "93.2": {"amos_relevant": False, "not_amos_reason": NOT_AMOS_REASON["ppx"], "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "93.3": {"amos_relevant": False, "not_amos_reason": NOT_AMOS_REASON["ppx"], "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "93.5": {"amos_relevant": False, "not_amos_reason": NOT_AMOS_REASON["ppx"], "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "93.6": {"amos_relevant": False, "not_amos_reason": NOT_AMOS_REASON["ppx"], "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "94":  {"amos_relevant": False, "not_amos_reason": NOT_AMOS_REASON["crew_ops"], "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    # ---- internal_utair / gap MER из matching.json ----
    "82.1": {"amos_relevant": False, "not_amos_reason": "режим Ковер — угроза дронов / военные риски, источник IATA-732 process G7/Z (ATFM)", "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "83.1": {"amos_relevant": False, "not_amos_reason": "правительственные ограничения (govt flights), источник IATA-732 process G7/Z (ATFM)", "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "93.4": {"amos_relevant": False, "not_amos_reason": NOT_AMOS_REASON["ppx"], "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "95":   {"amos_relevant": False, "not_amos_reason": NOT_AMOS_REASON["crew_ops"], "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "96":   {"amos_relevant": False, "not_amos_reason": "общая категория «СБОЙ» — раскрывается через дочерние коды зоны 2", "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "97":   {"amos_relevant": False, "not_amos_reason": "забастовка персонала ЮТэйр — HR/operations, не AMOS", "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "98":   {"amos_relevant": False, "not_amos_reason": "забастовка вне Авиакомпании — внешний фактор, S:G/S:A", "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "99":   {"amos_relevant": False, "not_amos_reason": "«прочее» — нет привязки, требуется MVT для уточнения", "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
    "Столбец1": {"amos_relevant": False, "not_amos_reason": "артефакт Excel (заголовок столбца) — не валидный MER-код", "chain_steps_used": [], "primary_apn": None, "primary_apn_name": None, "primary_table": None, "primary_field": None},
}


# ---------- main ----------------------------------------------------------- #

def main() -> None:
    m = json.loads(MATCHING.read_text(encoding="utf-8"))
    by_mer = m.get("by_mer_code", {})
    print(f"MER codes in matching.json: {len(by_mer)}")

    records: list[dict[str, Any]] = []
    unrouted: list[str] = []
    for code, v in by_mer.items():
        rule = MER_AMOS_ROUTING.get(code)
        if rule is None:
            # default for unknown — пометим как not_amos с пометкой
            rule = {
                "amos_relevant": False,
                "not_amos_reason": "не размечено вручную — требуется ревью",
                "chain_steps_used": [],
                "primary_apn": None,
                "primary_apn_name": None,
                "primary_table": None,
                "primary_field": None,
            }
            unrouted.append(code)

        chain_resolved = [ANCHOR_CHAIN[i - 1] for i in rule["chain_steps_used"]]

        records.append({
            "mer_code": code,
            "mer_name_ru": v.get("mer_name_ru", ""),
            "mer_group": v.get("mer_group", ""),
            "iata730_code": v.get("iata730_code", ""),
            "iata730_name_en": v.get("iata730_name_en", ""),
            "matching_kind": v.get("kind"),
            "matching_has_targets": bool(v.get("iata732_targets")),
            "matching_atfm_fallback": v.get("_atfm_fallback", False),
            "amos_relevant": rule["amos_relevant"],
            "amos_primary_apn": rule.get("primary_apn"),
            "amos_primary_apn_name": rule.get("primary_apn_name"),
            "amos_primary_table": rule.get("primary_table"),
            "amos_primary_field": rule.get("primary_field"),
            "amos_chain_steps": rule["chain_steps_used"],
            "amos_chain_resolved": [
                {"step": s["step"], "node": s["node"], "apn": s["apn"], "table_hint": s["table_hint"]}
                for s in chain_resolved
            ],
            "amos_note": rule.get("note", ""),
            "not_amos_reason": rule.get("not_amos_reason"),
        })

    records.sort(key=lambda r: (float(r["mer_code"]) if r["mer_code"].replace(".", "").isdigit() else 999.0))

    from collections import Counter
    cnt_rel = Counter(r["amos_relevant"] for r in records)
    cnt_apn = Counter(r["amos_primary_apn"] for r in records if r["amos_primary_apn"])
    print(f"AMOS-relevant: {cnt_rel[True]} | not-AMOS: {cnt_rel[False]}")
    print(f"Primary APN distribution: {dict(cnt_apn.most_common())}")
    if unrouted:
        print(f"WARNING — unrouted MER (нужно ревью): {unrouted}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps({
        "version": "v1",
        "task": "TASK-014",
        "source": str(MATCHING),
        "doc": "Aircraft-centric AMOS lookup chain для каждой MER-строки из matching.json",
        "anchor_chain": ANCHOR_CHAIN,
        "stats": {
            "total_mer": len(records),
            "amos_relevant": cnt_rel[True],
            "not_amos": cnt_rel[False],
            "primary_apn_distribution": dict(cnt_apn.most_common()),
        },
        "records": records,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"written {OUT_JSON} ({OUT_JSON.stat().st_size} bytes)")

    cols = [
        "mer_code", "mer_group", "mer_name_ru",
        "iata730_code", "iata730_name_en",
        "matching_kind", "matching_has_targets", "matching_atfm_fallback",
        "amos_relevant", "amos_primary_apn", "amos_primary_apn_name",
        "amos_primary_table", "amos_primary_field",
        "amos_chain_steps", "amos_note", "not_amos_reason",
    ]
    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in records:
            r_csv = dict(r)
            r_csv["amos_chain_steps"] = ",".join(str(x) for x in r["amos_chain_steps"])
            w.writerow(r_csv)
    print(f"written {OUT_CSV} ({OUT_CSV.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
