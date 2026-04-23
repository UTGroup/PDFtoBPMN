# Каталог источников данных ЦУП (AS-IS)

> **Версия 2.1** — синхронизирована с §10 файла `input2/ЦУП_md/ANALYSIS_AS-IS_RCA_и_Сбойные.md`.
> Артефакт §7.1 шага 2 из аналитики AS-IS RCA/Оперативное управление регулярностью.
> Цель: единый реестр data sources, которые сходятся в decision points ЦУП, с оценкой пригодности для подключения ИИ-ассистента.
> В v2.1 добавлены источники из `КД-РД-Б1.041-04 (изм.32 от 24.04.2026)`: АСБ Leonardo (DEGR/CVIP/PDTS), DCS Astra, сервис KYFO, префикс `t/t*` в Meridian.OPS.

## Условные обозначения

- **Тип**: `system` (ИС с собственным БД), `feed` (поток сообщений), `doc` (документ/форма), `voice` (голос), `manual` (ручная запись)
- **Машиночитаемость (MR)**: `S` — структурирован, `SS` — полу-структурирован, `U` — неструктурирован
- **Доступ**: `API`, `DB`, `MQ` (очередь), `file`, `email`, `voice`, `paper`
- **Готовность для ИИ**:
  - `green` — можно подключать без донастройки
  - `yellow` — нужен парсер/нормализация
  - `red` — нужен новый контур сбора (запись, OCR, voice-to-text)

---

## 1. Системы (system)

| ID | Источник | Владелец | Содержание | Формат | MR | Доступ | Период | Готовность | DP |
|---|---|---|---|---|---|---|---|---|---|
| `SYS-MER-NET` | Meridian.Net | вендор / ИТ ЮТэйр | Расписание, СПП, организационное обеспечение полётов | RDBMS / web | S | DB read-only / API | real-time | green | A1, A2, B1, B2, B3 |
| `SYS-MER-OPS` | Meridian.Ops | вендор / ИТ ЮТэйр | Предварительный план, оперативное управление, расстановка ВС | RDBMS / web | S | DB read-only / API | real-time | green | A1, A2, B1, B2, B3 |
| `SYS-MER-NAV` | Meridian.Nav | вендор / ИТ ЮТэйр | Полётная информация, штурманский расчёт, топливо, запасные а/д | RDBMS | S | DB read-only / API | event-driven | green | B2 (топливо/маршрут) |
| `SYS-MER-CREW` | Meridian.Crew/Sal | СПиОУ ЛД, ИТ | Экипажи, рабочее время, резерв, медотстранения | RDBMS | S | DB read-only / API | real-time | green | B2, B3 |
| `SYS-MER-WEB` | Meridian.Web | ИТ ЮТэйр | Web-портал для ЛС и сотрудников | web | SS | scrape / API | real-time | yellow | A1 (контекст) |
| `SYS-PROD-REP` | ИС «Производственная отчётность» | ОПиАА (РИ-М1.016 §6) | Регулярность, отчёт UT-DSP.1-06 (21 категория задержек), UT-DSP.1-01.1 | XLS / web | S | API / file | сутки/неделя/месяц | green | A3, A4 |
| `SYS-CBRS` | ЦБРС / ГЦ ЕС ОрВД | внешний (ФГУП «Госкорпорация по ОрВД») | Слоты, расписание, режимы аэропортов | AFTN-msg / file | S | feed (РСП/ОКР) | event-driven | green | B2 |
| `SYS-LOTUS` | Lotus Notes | ИТ ЮТэйр | Корпоративная почта смены, журналы рассылок | mail | SS | IMAP / EWS-like | real-time | yellow | A2, A3 |
| `SYS-OPS-MOD` | Модуль OPS у Ю-Ти-Джи (Внуково) | АО «Ю-Ти-Джи» (148-08) | Сообщения о ходе ТГО, неисправностях, опозданиях паксов | web-form / mail | SS | export / mail | event-driven | yellow | A1, B2 |
| `SYS-LEONARDO` *(v2.1)* | АСБ Leonardo | КЦ / коммерч. блок | Бронирование, ремарки приоритетов **DEGR / CVIP / PDTS**, статусы пакса | RDBMS / API | S | API / push | real-time | green | **B2 (изм.32)** |
| `SYS-DCS-ASTRA` *(v2.1)* | DCS Astra | ОКР / аэропорт | Регистрация, факт. число чек-инов, закрытие рейса | RDBMS / API | S | API | real-time | green | **B2 (изм.32)** |
| `SYS-KYFO` *(v2.1)* | Сервис KYFO | КЦ / ДОНО | Автоматизированное оформление услуг по ФАП-82 (питание, гостиница, трансфер) | service / API | S | API / push | event-driven | green | **B2 (изм.32)** |
| `SYS-MER-OPS-TT` *(v2.1)* | Префикс `t / t*` в Meridian.OPS | КЦУТО ВС / КАЭ / КЛО | Машиночитаемая отметка ВС с ограничениями двигателей по высоте / температуре наружного воздуха | flag in OPS | S | DB read-only | event-driven | green | **B2 (фильтр подмены ВС)** |

## 2. Потоки сообщений (feed)

| ID | Источник | Владелец | Содержание | MR | Доступ | Период | Готовность | DP |
|---|---|---|---|---|---|---|---|---|
| `FEED-AFTN-MVT` | AFTN MVT/MVT-OUT | внешний (Государственная сеть AFTN) | Факт. вылет/посадка/задержка | S | gateway → MQ | real-time | green | A1 (факт), B1 (триггер) |
| `FEED-AFTN-RSP` | AFTN RSP/OKR | ЦБРС | Подтверждение/отказ слота | S | gateway → MQ | event-driven | green | B2 |
| `FEED-SITA` | SITA / SITATEX | внешний | Депеши хэндл-агентов | S | gateway → MQ | real-time | green | A1 |
| `FEED-METEO` | Метео/НОТАМ | НС ОПДО САОП ЛД, внешние источники | Прогноз, фактическая погода, ограничения | S | API / file | event-driven | green | B2 |
| `FEED-SMS-2H` | СМС-рассылка «>2 ч» | ЦУП | Уведомления стейкхолдеров о задержках >2 ч | SS | log / API оператора | event-driven | yellow | B2 (исполнение) |
| `FEED-SMS-VIP` | СМС-рассылка «ВИП» | ЦУП | Уведомления по VIP/ПК | SS | log / API оператора | event-driven | yellow | B2 |
| `FEED-LEO-PUSH` *(v2.1)* | Push-уведомления АСБ Leonardo о ремарках DEGR/CVIP/PDTS | КЦ | Сигнал о расстановке приоритетов за -6 ч до СОВ | S | webhook / push | event-driven | green | **B2 (T-6ч)** |
| `FEED-KYFO-PUSH` *(v2.1)* | Push-уведомления KYFO о факте предоставления услуг ФАП-82 | КЦ / ДОНО | Контроль качества и SLA-соблюдения | S | webhook / push | event-driven | green | **B2 (T+1ч)** |

## 3. Документы и формы (doc)

| ID | Источник | Владелец | Содержание | Формат | MR | Готовность | DP |
|---|---|---|---|---|---|---|---|
| `DOC-UT-DSP-101` | Отчёт по рейсам UT-DSP.1-01.1 | НС ЦУП → ЛД, ТД, ДОНО | Сменный отчёт (2 раза/сутки 04:00, 16:00 МСК) | XLS/PDF | S | green | A3 |
| `DOC-UT-DSP-106` | Отчёт UT-DSP.1-06 «Регулярность» | ОПиАА | Месячная/годовая регулярность по 21 категории задержек | XLS | S | green | A4 |
| `DOC-ACT-DELAY` | Акт на задержку | ПДС аэропорта (ГПО) | Фиксация причин и виновников задержки | PDF/scan/paper | U/SS | red — нужен OCR | A3 |
| `DOC-FLT-PLAN` | Полётный план / штурм. расчёт | ОПДО САОП ЛД | Маршрут, топливо, запасные а/д | XML/PDF | S/SS | green | B2 |
| `DOC-NOTOC` | NOTOC | ДОНО / агенты | Опасные грузы | формализован (IATA) | S | green | B2 |
| `DOC-MEL` | MEL/CDL | ЦУТО ВС / ТД | Допуски на эксплуатацию ВС с отказами | PDF | SS | yellow | B2 |
| `DOC-ERP-CARDS` | Карты действий (Annex 6/7/13/15/16) | РГ-128 контур | Действия в кризисе/ЧП/АНВ | PDF/paper | U | red | B4 |
| `DOC-TRANSFER-LIST` *(v2.1)* | Лист трансферных пассажиров | ОКР по запросу из АСБ + DCS | Перечень трансферных паксов, статусы | XLS/JSON | S/SS | yellow — выгрузка ручная | **B2 (T-3ч/-2ч)** |
| `DOC-KYFO-LOG` *(v2.1)* | Журнал сервиса KYFO | КЦ / ДОНО | История оказанных услуг ФАП-82 (питание, гостиница, трансфер) с timestamps | JSON / API | S | green | **B2 (контроль)** |
| `DOC-FLEET-STATE` *(v2.1)* | Отчёт «Состояние парка ВС» | ЦУТО ВС | Ежедневная сводка готовности парка | PDF/XLS | S | yellow — нужен парсер | **B2** |

## 4. Голосовые и неструктурированные каналы (voice/manual)

| ID | Источник | Владелец | Содержание | MR | Готовность | DP |
|---|---|---|---|---|---|---|
| `VOICE-PHONE` | Телефон / ГГС / радиосвязь | ЦУП ↔ КВС, супервайзеры, диспетчеры | Уточнения по статусу ВС, экипажа, пассажиров | U | red — нужен voice-to-text + capture | A1, A2 |
| `VOICE-RADIO` | Радиосвязь экипаж ↔ ОПДО | ОПДО | Подтверждение готовности | U | red | A1 |
| `MSG-WA-148` | WhatsApp по 148-08 | АО «Ю-Ти-Джи» ↔ ЦУП | Оперативные сообщения по обслуживанию | SS | yellow — есть жёсткая адресация, но free-text тело | A1, B2 |
| `MAN-LOG-SHIFT` | Журнал приёма-передачи смены | НС ЦУП | Сменный журнал (бумажный) | U | red | A2 |
| `MAN-LOG-REQ` | Журнал регистрации заявок | ООП ЦУП | Внешние заявки от заказчиков | U/SS | yellow | B2 (входы) |

## 5. Внешний контур (external)

| ID | Источник | Владелец | Содержание | Канал | Готовность |
|---|---|---|---|---|---|
| `EXT-MTU-RA` | МТУ Росавиации | Росавиация | Уведомления о задержках >2 ч / >6 ч | РД (служебная радиограмма) | yellow |
| `EXT-FAVT` | ФАВТ | Росавиация | Контроль ERP (RG-128) | бумага/email | red |
| `EXT-MAK` | МАК | МАК | Расследование инцидентов | бумага/email | red |

---

## 6. Карта «source → DP»

```text
A1 (диспетчер)   ← FEED-AFTN-MVT, FEED-SITA, SYS-OPS-MOD, VOICE-PHONE, MSG-WA-148, SYS-MER-OPS
A2 (НС ЦУП)      ← все вышеперечисленное + SYS-LOTUS, MAN-LOG-SHIFT, классификатор IATA AHM 730
A3 (нач. ЦУП)    ← DOC-UT-DSP-101, DOC-ACT-DELAY, отчёт представителя
A4 (ген.дир.)    ← DOC-UT-DSP-106 (агрегаты), SYS-PROD-REP

B1 (диспетчер ЦУП + смежные дежурные) ← FEED-AFTN-MVT, FEED-METEO, FEED-SITA, SYS-MER-OPS (триггер: каждое отклонение в ПП)
B2 (НС ЦУП)      ← SYS-MER-NET/OPS/NAV/CREW, ЦУТО ВС, СПиОУ, FEED-METEO, SYS-CBRS, ДУТиЗ, MSG-WA-148, VOICE-PHONE
                  ← *(v2.1, изм.32 КД-РД-Б1.041-04)* SYS-LEONARDO (DEGR/CVIP/PDTS), SYS-DCS-ASTRA, SYS-KYFO,
                                                     SYS-MER-OPS-TT (t/t*), DOC-TRANSFER-LIST, DOC-KYFO-LOG, DOC-FLEET-STATE,
                                                     FEED-LEO-PUSH, FEED-KYFO-PUSH
B3 (исполнители) ← SYS-MER-NET/OPS, FEED-AFTN-MVT (подтверждения), Lotus, тел./ГГС, СМС
B4 (нач. ЦУП / нач. ЛД) ← телефонная эскалация по §14.1.4 (вне ERP-контура)
```

## 7. Приоритизация подключения (для MVP ИИ-ассистента)

**Phase 0 (read-only подключение, 0–2 нед.):**
`SYS-MER-OPS`, `SYS-MER-NET`, `SYS-MER-NAV`, `SYS-MER-CREW`, `FEED-AFTN-MVT`, `FEED-SITA`, `FEED-METEO`, `SYS-PROD-REP`.
**+ v2.1 обязательно для PoC «Co-pilot НС ЦУП по B2»:** `SYS-LEONARDO` (включая `FEED-LEO-PUSH`), `SYS-DCS-ASTRA`, `SYS-KYFO` (включая `FEED-KYFO-PUSH`), `SYS-MER-OPS-TT` (флаг `t/t*`).

**Phase 1 (yellow → green, 2–6 нед.):**
- Парсер `SYS-OPS-MOD` (Модуль OPS Ю-Ти-Джи) → структурный JSON.
- Нормализатор `SYS-LOTUS` (extract по предметам/тегам).
- Парсер MEL/CDL.
- Парсер `DOC-FLEET-STATE` (отчёт «Состояние парка ВС»).
- *(v2.1)* Контур синхронизации **АСБ Leonardo ↔ DCS Astra ↔ Meridian.OPS** при изменении времени рейса (CDC или event-bus) — расшивка `gap-06`.

**Phase 2 (red, 1–6 мес.):**
- OCR-приёмник для `DOC-ACT-DELAY` от разных аэропортов.
- Voice capture для `VOICE-PHONE` (политически согласовать с РД-М1.014, юристами).
- Захват `MAN-LOG-SHIFT` через структурную форму в Meridian.Web.

---

_Поддерживается совместно с `knowledge_gaps_TsUP.md` и `ontology_TsUP.yaml`._
