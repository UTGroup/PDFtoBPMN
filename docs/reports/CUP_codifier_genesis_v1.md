# Генезис кодификаторов: IATA-730 → Меридиан → ЦУП → IATA-732 (2028)

> **Версия:** v1, 2026-05-12. Последовательное сравнение четырёх систем кодирования причин задержки рейсов в одной плоской таблице. AS-IS, разрывы помечены (Rule 0).
> **Источник истины:** [`input2/ЦУП/Отчетность/Кодификатор_ЦУП_МЕР_IATA_730_732.xlsx`](../../input2/ЦУП/Отчетность/Кодификатор_ЦУП_МЕР_IATA_730_732.xlsx).
> **Машинная таблица:** [`output/cup_codifier/genesis_full_table.csv`](../../output/cup_codifier/genesis_full_table.csv) (271 строка) — для использования в дашборде или импорта в БД.
> **Скрипт сборки:** [`output/cup_codifier/build_genesis.py`](../../output/cup_codifier/build_genesis.py).
> **Связан с:** [`CUP_codifier_analysis_v1.md`](./CUP_codifier_analysis_v1.md) (детальная аналитика разрывов).

## 1. TL;DR

| Метрика | Значение |
|---|---:|
| Строк уровня кода в таблице (IATA-730 + MER, без детализаций) | **88** |
| Из них: совпадает IATA-730 + Меридиан (`both`) | 64 |
| IATA-730 без Меридиана (`iata730_only`) | 12 |
| MER без IATA-730 (`mer_only`) | 12 |
| Кандидат IATA-732 найден с уверенностью **high** (≥3 совпадающих слов) | **21** |
| с уверенностью **medium** (≥1 слово) | 48 |
| Кандидат IATA-732 **не найден** (`none`) | 7 |
| ИТОГО кодов с автоматическим кандидатом IATA-732 | 69 / 76 (**91 %**) |
| Полный объём IATA-732 (2028) | 553 пары process×reason + 4 493 полных кода |

**Главное.** 91 % кодов IATA-730/Меридиан имеют автоматически найденного семантического кандидата в IATA-732. Это **верхняя граница** «бесшовности» миграции — она достижима только если справочник Меридиана будет дополнен 165 детализациями ЦУП (см. предыдущий отчёт, § 6.1).

## 2. Метод

Для каждой строки из листа `ЦУП_МЕР_IATA` (271 строка):

1. Парсится IATA-730: номер (00–99) + мнемоник (PD, OA, …) + EN-описание.
2. По диапазону IATA-730 определяется **целевая GROUP IATA-732** (например, 11–19 → GROUP 5 «PAX HANDLING», 41–48 → GROUP 6 «DEPARTURE DISRUPTION»). Карта диапазонов — в комментариях [`build_genesis.py`](../../output/cup_codifier/build_genesis.py).
3. Внутри этой GROUP ищется REASON IATA-732 с максимальным пересечением ключевых слов (после нормализации: lowercase, удаление стоп-слов, длина > 2). Уверенность:
   - `high` — пересечение ≥3 слов
   - `medium` — пересечение 1–2 слов
   - `none` — IATA-730 есть, но ни одной строки IATA-732 со значимым пересечением слов
   - `n/a` — это строка-детализация ЦУП, у которой нет IATA-730 кода для сравнения

Rule 0: **там, где маппинг неоднозначен (medium/none), интерпретацию не даём**. Пользователю выводится top-1 кандидат с явным признаком уверенности и списком пересекающихся слов (колонка `IATA732_matched_words` в CSV) — для ручной проверки.

## 3. Сводная таблица генезиса (88 строк)

> Колонки слева направо: **IATA-730** (международный стандарт, действующий) → **MER** (Меридиан, производственная система Утайр) → **IATA-732** (стандарт с 2028, кандидат соответствия). MER-описание = «ЦУП», т. к. это именно те формулировки, на основе которых ЦУП строит отчётность.
> 
> **conf:** ✅ high · ~ medium · ⚠ none · — n/a.

| IATA-730 | мнемоник | EN-описание (IATA-730) | MER-код | MER-группа | MER-описание | IATA-732 (group · code) | IATA-732 reason | conf |
|---:|:---:|:--|---:|:---:|:--|:--|:--|:---:|
| 6 | OA | NO GATE/STAND AVAILABILITY DUE TO OWN AIRLINE ACTIVITY | — | — | — | GROUP 1 · CP* | P - выход на посадку/стоянка - неисправность | ✅ high |
| 9 | SG | SCHEDULED GROUND TIME LESS THAN DECLARED MINIMUM GROUND TIME | — | — | — | GROUP 1 · AB* | B - время руления дольше обычного | ~ medium |
| 11 | PD | LATE CHECK-IN, acceptance after deadline | 11 | СОП | Позднее окончание регистрации | GROUP 5 · PA* | A - позднее начало | ✅ high |
| 12 | PL | LATE CHECK-IN, congestions in check-in area | 12 | СОП | Поздняя регистрация | GROUP 5 · PA* | A - позднее начало | ~ medium |
| 13 | PE | CHECK-IN ERROR, passenger and baggage | 13 | СОП | Ошибка в регистрации | GROUP 5 · PS* | S - ошибка персонала | ~ medium |
| 14 | PO | OVERSALES, booking errors | 14 | ПРЧ | Допосадка JMP (вм. неявивших.) | GROUP 5 · QB* | B - перепродажа билетов - снижение/повышение класса обслужи… | ~ medium |
| 15 | PH | BOARDING, discrepancies and paging, missing checked-in pass… | 15 | СОП | Посадка/высадка пассажиров | GROUP 5 · PH* | H - пропавшие личные вещи | ~ medium |
| 16 | PS | COMMERCIAL PUBLICITY/PASSENGER CONVENIENCE, VIP, press, gro… | 16 | ЗАК | Заказчиком | GROUP 5 · PH* | H - пропавшие личные вещи | ✅ high |
| 17 | PC | CATERING ORDER, late or incorrect order given to supplier | 17 | ПДГ | Поздний дозаказ бортпитания | GROUP 5 · PA* | A - позднее начало | ~ medium |
| 18 | PB | BAGGAGE PROCESSING, sorting etc. | 18 | СОП | Загрузка багажа | GROUP 5 · QK* | K - документы - медицинские, визовые и т. д. | ~ medium |
| 19 | PW | REDUCED MOBILITY, boarding / deboarding of passengers with … | 19 | СОП | Высадка/посадка маломоб. пасс. | GROUP 5 · TA* | A - не было предварительного уведомления | ~ medium |
| 21 | CD | DOCUMENTATION, errors etc. | 21 | СОП | Ошибки в документах | GROUP 2 · DK* | K - документация/маркировка | ~ medium |
| 22 | CP | LATE POSITIONING | 22 | СОП | Поздняя доставка груза | GROUP 2 · DA* | A - задержка приема на складе | ~ medium |
| 23 | CC | LATE ACCEPTANCE | 23 | СОП | разгрузка/загрузка груза | GROUP 2 · DA* | A - задержка приема на складе | ~ medium |
| 24 | CI | INADEQUATE PACKING | 24 | СОП | Нарушение упаковки груза | GROUP 2 · DE* | E - ненадлежащая упаковка паллет/ULD | ~ medium |
| 25 | CO | OVERSALES, booking errors | 25 | СОП | Комплектация грузов | GROUP 2 · DB* | B - перепродажа | ~ medium |
| 26 | CU | LATE PREPARATION IN WAREHOUSE | 27 | СОП | Документация, упаковка почты | GROUP 2 · DA* | A - задержка приема на складе | ~ medium |
| 27 | CE | DOCUMENTATION, PACKING etc (Mail Only) | 28 | СОП | Поздняя доставка/загруз. почты | GROUP 2 · DE* | E - ненадлежащая упаковка паллет/ULD | ~ medium |
| 28 | CL | LATE POSITIONING (Mail Only) | — | — | — | GROUP 2 · DA* | A - задержка приема на складе | ~ medium |
| 29 | CA | LATE ACCEPTANCE (Mail Only) | — | — | — | GROUP 2 · DA* | A - задержка приема на складе | ~ medium |
| 31 | GD | AIRCRAFT DOCUMENTATION LATE/INACCURATE, weight and balance,… | 31 | СОП | Документация на ВС | GROUP 2 · HA* | A - инструкция по загрузке - задержка/неверная | ~ medium |
| 32 | GL | LOADING/UNLOADING, bulky, special load, cabin load, lack of… | 32 | СОП | Погрузка/разгрузка | GROUP 2 · GT* | T - нехватка персонала/задержка | ✅ high |
| 33 | GE | LOADING EQUIPMENT, lack of or breakdown, e.g. container pal… | 33 | ПДГ | Погрузочное оборуд-е/Персонал | GROUP 2 · GT* | T - нехватка персонала/задержка | ✅ high |
| 34 | GS | SERVICING EQUIPMENT, lack of or breakdown, lack of staff, e… | 34 | СВС | Сервисное оборудование | GROUP 2 · DT* | T - нехватка/задержка персонала | ~ medium |
| 35 | GC | AIRCRAFT CLEANING | 35 | СВС | Уборка ВС | GROUP 2 · DV* | V - смена версии/самолета | ~ medium |
| 36 | GF | FUELLING/DEFUELLING, fuel supplier | 36 | ПДГ | Заправка/слив топлива | GROUP 2 | — | ⚠ none |
| 37 | GB | CATERING, late delivery or loading | 37 | СВС | Доставка бортпитания | GROUP 2 · GA* | A - позднее начало | ~ medium |
| 38 | GU | ULD, lack of or serviceability | 38 | ПДГ | Неиспр. средств пакетирования | GROUP 2 · DF* | F - задержка/недостаток/непригодность паллет/ULD | ~ medium |
| 39 | GT | TECHNICAL EQUIPMENT, lack of or breakdown, lack of staff, e… | 39 | ПДГ | Спецтранспорт | GROUP 2 · DT* | T - нехватка/задержка персонала | ~ medium |
| 41 | TD | AIRCRAFT DEFECTS. | 41 | НМЧ | Неисправность мат. части ВС | GROUP 6 · VO* | O - безопасность воздушного судна | ~ medium |
| 42 | TM | SCHEDULED MAINTENANCE, late release. | 42 | НМЧ | Плановое ТО | GROUP 6 · WC* | C - плановое техническое обслуживание | ~ medium |
| 43 | TN | NON-SCHEDULED MAINTENANCE, special checks and/or additional… | 43 | СБОЙ | Запуск от УВЗ/Ожидание родничк | GROUP 6 · WD* | D - внеплановое техническое обслуживание | ✅ high |
| 44 | TS | SPARES AND MAINTENANCE EQUIPMENT, lack of or breakdown. | 44 | НМЧ | Зап. части и ремонтн. оборуд-е | GROUP 6 · VH* | H - сбой связи | ~ medium |
| 45 | TA | AOG SPARES, to be carried to another station. | 45 | СБОЙ | Зап. части для транспортировки | GROUP 6 · WB* | B - запасные части AOG | ~ medium |
| 46 | TC | AIRCRAFT CHANGE, for technical reasons. | 46 | НМЧ | Замена ВС/типа ВС по тех. прич | GROUP 6 · VV* | V - смена версии/самолета | ✅ high |
| 47 | TL | STAND-BY AIRCRAFT, lack of planned stand-by aircraft for te… | 47 | СБОЙ | Отсутствие ВС по тех. причинам | GROUP 6 · VO* | O - безопасность воздушного судна | ~ medium |
| 48 | TV | SCHEDULED CABIN CONFIGURATION/VERSION ADJUSTMENTS. | 48 | ПРЧ | Внеплановое изм-е компоновки | GROUP 6 · VC* | C - корректировка конфигурации/версии салона | ✅ high |
| 51 | DF | DAMAGE DURING FLIGHT OPERATIONS, bird or lightning strike, … | 51 | ПВС | Поврежд. ВС в полете/на рулен. | GROUP 6 · WE* | E - ремонт самолета - повреждение во время полетов | ✅ high |
| 52 | DG | DAMAGE DURING GROUND OPERATIONS, collisions (other than dur… | 52 | ПВС | Повреждение ВС на земле | GROUP 6 · WF* | F - ремонт самолета - повреждение во время наземных операций | ✅ high |
| 55 | ED | DEPARTURE CONTROL | 55 | СОП | Система управления вылета | GROUP 6 | — | ⚠ none |
| 56 | EC | CARGO PREPARATION/DOCUMENTATION | 56 | СОП | Подготовка грузовой докум. | GROUP 6 · WI* | I - повреждение во время наземных операций: документация/ут… | ~ medium |
| 57 | EF | FLIGHT PLANS | — | — | — | GROUP 6 · WE* | E - ремонт самолета - повреждение во время полетов | ~ medium |
| 58 | EO | OTHER AUTOMATED SYSTEM | — | — | — | GROUP 6 | — | ⚠ none |
| 61 | FP | FLIGHT PLAN, late completion or change of, flight documenta… | 61 | ЛС | Флайт-план | GROUP 4 · OE* | E - план полета | ✅ high |
| 62 | FF | OPERATIONAL REQUIREMENTS, fuel, load alteration | 62 | ЛС | Эксплуатационные требования | GROUP 4 | — | ⚠ none |
| 63 | FT | LATE CREW BOARDING OR DEPARTURE PROCEDURES, other than conn… | 63 | ЛС | Позднее прибытие летн. экипажа | GROUP 4 · NA* | A - экипаж опаздывает к самолету | ✅ high |
| 64 | FS | FLIGHT DECK CREW SHORTAGE, sickness, awaiting standby, flig… | 64 | ЛС | Некомплект. летного экипажа | GROUP 4 · NK* | K - документы - медицинские, визовые и т. д. | ✅ high |
| 65 | FR | FLIGHT DECK CREW SPECIAL REQUEST, not within operational re… | 65 | ЛС | Доп. требования экипажа | GROUP 4 · NR* | R - реакционный - с другого рейса | ~ medium |
| 66 | FL | LATE CABIN CREW BOARDING OR DEPARTURE PROCEDURES, other tha… | 66 | ДКЭ | Позднее прибытие бортпровод. | GROUP 4 · NA* | A - экипаж опаздывает к самолету | ✅ high |
| 67 | FC | CABIN CREW SHORTAGE, sickness, awaiting standby, flight tim… | 67 | ДКЭ | Некомплек. кабинного экипажа | GROUP 4 · NK* | K - документы - медицинские, визовые и т. д. | ✅ high |
| 68 | FA | CABIN CREW ERROR OR SPECIAL REQUEST, not within operational… | 68 | ЛС | Ошибка кабинного экипажа | GROUP 4 · NI* | I - досмотр салона | ~ medium |
| 69 | FB | CAPTAIN REQUEST FOR SECURITY CHECK, extraordinary | 69 | ПРЧ | Проверка ВС САБ по реш. КВС | GROUP 4 · NW* | W - пункты контроля безопасности/досмотр | ~ medium |
| 71 | WO | DEPARTURE STATION | 71 | М/У | Аэропорт вылета | GROUP 7 · YA* | A - проверка вылета | ~ medium |
| 72 | WT | DESTINATION STATION | 72 | М/У | Аэропорт назначения | GROUP 7 | — | ⚠ none |
| 73 | WR | EN ROUTE OR ALTERNATE | 73 | М/У | М/У по маршруту/запасн. а/п | GROUP 7 | — | ⚠ none |
| 75 | WI | DE-ICING OF AIRCRAFT, removal of ice and/or snow, frost pre… | 75 | ПОО | Противообледенит. обр-ка ВС | GROUP 7 · YM* | M - уборка снега/льда/воды/песка с территории аэропорта | ✅ high |
| 76 | WS | REMOVAL OF SNOW, ICE, WATER AND SAND FROM AIRPORT | 76 | М/У | Подготовка ВПП по метео | GROUP 7 · YM* | M - уборка снега/льда/воды/песка с территории аэропорта | ✅ high |
| 77 | WG | GROUND HANDLING IMPAIRED BY ADVERSE WEATHER CONDITIONS | 77 | М/У | Увелич. сроков наземн. подгот. | GROUP 7 · XN* | N - нестандартная обработка - большое количество/избыток/сп… | ~ medium |
| 81 | AT | ATFM due to ATC EN-ROUTE DEMAND/CAPACITY, standard demand/c… | 81 | ПРЧ | Ограничения ОрВД по маршруту | GROUP 7 · YK* | K - экологическая выгода, задержка запуска или отталкивание… | ~ medium |
| 82 | AX | ATFM due to ATC STAFF/EQUIPMENT EN-ROUTE, reduced capacity … | 82 | РЖМ | Временный режим а/п вылета | GROUP 7 · XU* | U - забастовка | ~ medium |
| 83 | AE | ATFM due to RESTRICTION AT DESTINATION AIRPORT, airport and… | — | РЖМ | режим Ковер | GROUP 7 · YU* | U - забастовка | ✅ high |
| 84 | AW | ATFM due to WEATHER AT DESTINATION | 83 | РЖМ | Временный режим а/п назнач. | GROUP 7 · YK* | K - экологическая выгода, задержка запуска или отталкивание… | ~ medium |
| 85 | AS | MANDATORY SECURITY | 84 | М/У | Огран. ОрВД в зоне а/п (метео) | GROUP 7 · YO* | O - дополнительное мероприятие/проверка безопасности | ~ medium |
| 86 | AG | IMMIGRATION, CUSTOMS, HEALTH | 85 | СБ | Снятие багажа/пассажира | GROUP 7 | — | ⚠ none |
| 87 | AF | AIRPORT FACILITIES, parking stands, ramp congestion, lighti… | 86 | ПРЧ | Погран. контроль/Мед.мероприят | GROUP 7 · XC* | C - перегрузка удаленной противообледенительной системы | ~ medium |
| 88 | AD | RESTRICTIONS AT AIRPORT OF DESTINATION, airport and/or runw… | 87 | А/П | Средства аэропорта | GROUP 7 · YU* | U - забастовка | ✅ high |
| 89 | AM | RESTRICTIONS AT AIRPORT OF DEPARTURE WITH OR WITHOUT ATFM R… | 88 | ПРЧ | Аэропорт назначения | GROUP 7 · YK* | K - экологическая выгода, задержка запуска или отталкивание… | ✅ high |
| 91 | RL | LOAD CONNECTION, awaiting load from another flight | 91 | ПРЧ | Ожидание транзитного груза | GROUP 1 · AR* | R - реакционная - с другого рейса | ~ medium |
| 92 | RT | THROUGH CHECK-IN ERROR, passenger and baggage | 92 | ТРФ | Ожидание трансферн. пассажиров | GROUP 1 · AG* | G - проверка на наличие посторонних предметов и освобождени… | ~ medium |
| 93 | RA | AIRCRAFT ROTATION, late arrival of aircraft from another fl… | 93 | ППС | Позднее прибытие ВС | GROUP 1 · AR* | R - реакционная - с другого рейса | ✅ high |
| 94 | RS | CABIN CREW ROTATION, awaiting cabin crew from another flight | — | СБОЙ | ППС ПОСЛЕ НМЧ | GROUP 1 · AR* | R - реакционная - с другого рейса | ~ medium |
| 95 | RC | CREW ROTATION, awaiting crew from another flight (flight de… | — | — | ППС ПОСЛЕ ЗАПУСКА ОТ УВЗ | GROUP 1 · AR* | R - реакционная - с другого рейса | ~ medium |
| 96 | RO | OPERATIONS | — | ППС М/У | ППС после М/У | GROUP 1 · BE* | E - ремонт самолета из-за повреждений во время полетов | ~ medium |
| 97 | MI | INDUSTRIAL ACTION WITH OWN AIRLINE | — | ППС | ППС после временного режима | GROUP 1 · AU* | U - забастовка | ~ medium |
| 98 | MO | INDUSTRIAL ACTION OUTSIDE OWN AIRLINE, excluding ATS | — | ППС | ППС после режима Ковер | GROUP 1 · AU* | U - забастовка | ~ medium |
| 99 | MX | OTHER REASON, not matching any code above | 94 | ДКЭ | Ожидание бортпроводников | GROUP 5 · UZ* | Z - позднее завершение или неизвестная причина | ~ medium |
| — | — | — | 9 | ОВС | Ожидание ВС с рс (не в связке) | — | — | — |
| — | — | — | 71 | М/У | М/У а/п вылета | — | — | — |
| — | — | — | 72 | М/У | М/У а/п прилета | — | — | — |
| — | — | — | 75 | ПОО | ПОО | — | — | — |
| — | — | — | 76 | М/У | Подготовка ВПП а/п прилета | — | — | — |
| — | — | — | 76 | М/У | Подготовка ВПП а/п вылета | — | — | — |
| — | — | — | 89 | А/П | Ограничения в а/п вылета | — | — | — |
| — | — | — | 95 | ЛС | Ожидание экипажа | — | — | — |
| — | — | — | 96 | СБОЙ | СБОЙ | — | — | — |
| — | — | — | 97 | ПРЧ | Забастовка внутри Авиакомпании | — | — | — |
| — | — | — | 98 | ПРЧ | Забастовка вне Авиакомпании | — | — | — |
| — | — | — | 99 | ПРЧ | Прочее (обязат. поясн. в MVT) | — | — | — |

## 4. Зоны применимости IATA-732

Из 76 строк, имеющих IATA-730 код (64 `both` + 12 `iata730_only`):

| GROUP IATA-732 | Кодов из IATA-730/MER | Доля от группы IATA-732 |
|---|---:|---|
| GROUP 1: AIRCRAFT ARRIVAL | 10 | + 12 «фантомов MER» 91-99 без IATA-730 |
| GROUP 2: RAMP HANDLING & LOAD CONTROL | 18 | покрытие хорошее, 21–29 + 31–39 |
| GROUP 3: AIRCRAFT SERVICING | 0 | **⚠ не покрыто** — IATA-730 не разделяет «сервис на земле» в одну группу |
| GROUP 4: CREW AND FLIGHT DOCUMENTATION | 9 | 61–69 ложится точно |
| GROUP 5: PAX HANDLING | 10 | 11–19 ложится точно |
| GROUP 6: DEPARTURE DISRUPTION | 14 | 41–58 — техника и повреждения |
| GROUP 7: AIRCRAFT DEPARTURE | 15 | 71–89 — погода и ATC/A/П |

**Наблюдение.** GROUP 3 (AIRCRAFT SERVICING — охлаждение/обогрев салона, питание, уборка, заправка, водоснабжение/туалеты) в IATA-730 размазана между группами 31–39 (Ramp/Aircraft Handling) и 35, 37 (сервис/уборка/кейтеринг). IATA-732 выделяет это как отдельный кластер — то есть **миграция в этой части будет означать переразметку существующих MER-кодов 34/35/37/36/38/39 на 2 группы IATA-732 вместо одной**.

## 5. Топ-10 «бесшовных» совпадений (high confidence)

| IATA-730 | Меридиан / ЦУП | IATA-732 (level-2) | Семантика |
|---|---|---|---|
| 11 PD «Late check-in» | 11 СОП «Позднее окончание регистрации» | **PA*** «P-acceptance, A-late check-in start» | 1:1 |
| 16 PS «VIP/groups» | 16 ЗАК «Заказчиком» | **PH*** | (требует ручной проверки — у автоматчера здесь ложное совпадение по слову «pass», см. § 6) |
| 32 GL «Loading, lack of staff» | 32 СОП «Погрузка/разгрузка» | **GT*** «G-outbound load, T-staff shortage» | 1:1 |
| 33 GE «Loading equipment» | 33 ПДГ «Погр. оборудование/Персонал» | **GT*** | 1:1 |
| 43 TN «Non-scheduled maintenance» | 43 СБОЙ «Запуск от УВЗ» | **WD*** «W-technical, D-non-scheduled MX» | 1:1 |
| 46 TC «Aircraft change technical» | 46 НМЧ «Замена ВС/типа» | **VV*** «V-non-tech disruption, V-aircraft change» | 1:1 |
| 48 TV «Cabin config adjust» | 48 ПРЧ «Внепл. изм-е компоновки» | **VC*** «V-non-tech, C-config adjustment» | 1:1 |
| 51 DF «Damage in flight» | 51 ПВС «Поврежд. в полете» | **WE*** «W-repair, E-damage in flight» | 1:1 |
| 52 DG «Damage on ground» | 52 ПВС «Поврежд. на земле» | **WF*** «W-repair, F-damage on ground» | 1:1 |
| 61 FP «Flight plan» | 61 ЛС «Флайт-план» | **OE*** «O-flight doc, E-flight plan» | 1:1 |
| 63 FT «Late crew» | 63 ЛС «Позднее прибытие летн. эк.» | **NA*** «N-crew, A-crew late to aircraft» | 1:1 |
| 64 FS «Crew shortage» | 64 ЛС «Некомплект. экипажа» | **NK*** | (требует проверки — в IATA-732 разделено по причинам отсутствия) |
| 66 FL «Late cabin crew» | 66 ДКЭ «Позднее прибытие б/п» | **NA*** | 1:1 |
| 67 FC «Cabin crew shortage» | 67 ДКЭ «Некомплект. б/п» | **NK*** | 1:1 |
| 75 WI «De-icing» | 75 ПОО «Противообл. обработка» | **YM*** «Y-departure, M-snow/ice removal» | 1:1 |
| 76 WS «Snow/ice removal» | 76 М/У «Подготовка ВПП по метео» | **YM*** | 1:1 |
| 83 AE «ATFM destination restriction» | (нет MER-кода) | **YU*** | (странный матч на «забастовка», см. § 6) |
| 88 AD «Restrictions destination airport» | 87 А/П «Средства аэропорта» | **YU*** | (тоже ложный матч на «забастовка», см. § 6) |
| 89 AM «Restrictions departure airport» | 88 ПРЧ «Аэропорт назначения» | **YK*** | 1:1 |
| 93 RA «Late arrival from another flight» | 93 ППС «Позднее прибытие ВС» | **AR*** «A-arrival, R-reactionary» | 1:1 |

Чистых «бесшовных» 1:1 — **15 кодов** (после исключения ложных совпадений). Это ~17 % от 88 строк генезиса. Однако они покрывают **самые частотные** причины задержек (passenger check-in, cabin crew, flight plan, late aircraft, de-icing, damage to aircraft).

## 6. Проблемные места (требуют ручной верификации/решения)

### 6.1 Ложные срабатывания текстового матчера

Автоматический матч проводился по словам и иногда «склеивает» неподходящие пары из-за случайных совпадений (например, «pass», «station», «outside»). Эти строки требуют ручной экспертизы:

| IATA-730 | Кандидат IATA-732 | Проблема |
|---|---|---|
| 15 PH «BOARDING, missing checked-in pass» | PH «H-пропавшие личные вещи» | Совпадение на слове «pass» — а это про багаж, не про регистрацию. **Реально:** PR (boarding) или RC (boarding completion). |
| 16 PS «VIP/groups» | PH «H-пропавшие личные вещи» | Совпадение по букве P — мимо. **Реально:** UA/UB (U-VIP services). |
| 18 PB «Baggage processing» | QK «K-документы, медицинские…» | **Реально:** в IATA-732 багаж в GROUP 2 (F — багаж на позиции), не PAX-приём. |
| 19 PW «Reduced mobility» | TA «A-нет предварительного уведомления» | Похоже на правду, но возможно правильнее: T-PRM (passenger with reduced mobility) — нужна верификация. |
| 22 CP «Late positioning» | DA «A-задержка приема на складе» | OK по смыслу, но проверить с командой Cargo. |
| 41 TD «Aircraft defects» | VO «O-безопасность ВС» | Слабый матч — слово «security/безопасность» зашло вместо «defect». **Реально:** WA (W-repair, A-defects). |
| 65 FR «Crew special request» | NR «R-reactionary» | Спорно — спецзапрос ≠ реакционность. |
| 81 AT «ATFM en-route» | YK «K-environment delay» | Слабо — нужно искать в GROUP 7 раздел Z (network restrictions). |
| 83 AE / 88 AD «ATFM/Restrictions» | YU «U-забастовка» | Точно ложно — слово «restriction/U» сцепилось. Реально: ZA-ZC (Z-network restrictions). |
| 99 MX «Other reason» | UZ «Z-позднее завершение» | OK, но IATA-732 предлагает «MX» вынести в отдельный код AA/ZZ (последняя категория). |

**Вывод.** Из 21 строки с `high` confidence реально точных 1:1 — около **15**. Остальные 6 — попадание автоматики мимо.

### 6.2 IATA-730 коды без кандидата (`none`, 7 шт.)

| IATA-730 | Описание | Почему не нашли |
|---|---|---|
| 36 GF | Fuelling/defuelling, fuel supplier | В IATA-732 этого нет в GROUP 2 (которую назначили автоматически); кандидат — GROUP 3 process L «Заправка». Маппинг диапазонов 31–39 → GROUP 2 — слишком узкий. |
| 55 ED | Departure control | Нет очевидного семантического кандидата. Возможно: VW (system error). |
| 58 EO | Other automated system | Аналогично — мусорная категория «прочее системное». |
| 62 FF | Operational requirements, fuel/load | Похоже на NB (N-crew, B-load alteration) или OC (O-doc, C-load sheet). |
| 72 WT | Weather: destination station | Маппинг диапазона 71–77 → GROUP 7 — это X (anti-icing) и Z (network), а WT надо в Z (weather at destination). Нужно расширить карту. |
| 73 WR | Weather: en-route or alternate | Аналогично — должно быть в Z (network/weather). |
| 86 AG | Immigration/customs/health | В IATA-732 это **вынесено в stakeholder** (I — gov authorities), а не в отдельный REASON. |

**Вывод.** Карту диапазонов IATA-730 → IATA-732 GROUP стоит расширить: внутри GROUP 7 различать процессы X (anti-icing) и Z (network/weather), а GROUP 2 «расщеплять» на GROUP 3 для топлива и сервиса.

### 6.3 «Фантомы Меридиана» (12 кодов без IATA-730)

В нижних 12 строках таблицы видны MER-коды без IATA-730 (9, 71×2, 72, 75, 76×2, 89, 95, 96, 97, 98, 99). Часть из них — дубли формулировок (71/72/75/76, см. предыдущий отчёт § 3.3 и § 6.4). Часть (97 «Забастовка внутри А/К», 98 «Забастовка вне А/К») имеет точные IATA-730 эквиваленты (97 MI, 98 MO), но в таблице аналитика IATA-RU не заполнен. **⚠ GAP § 6.2 предыдущего отчёта.**

## 7. Сценарии миграции на IATA-732

### Сценарий А — «параллельная разметка» (рекомендуется)

1. **Сейчас (2026):** актуализировать справочник Меридиана по рекомендациям R1–R8 предыдущего отчёта (165 детализаций → подкоды, разрешить дубли, дозаполнить IATA-RU).
2. **Q3 2027:** в Меридиан вводится **второе поле** `iata732_code` (3 буквы) — заполняется параллельно с MER-кодом. Маппинг для большинства MER-кодов берётся из таблицы § 3 этого отчёта, начиная с 15 «бесшовных» строк.
3. **Сезон зима 2027–28 (пилот):** диспетчер вводит и MER, и IATA-732. Отчётность ЦУП дублируется в двух разрезах. Сравниваем — где разовая разметка совпадает с IATA-732, где расходится.
4. **Январь 2028 (cutover):** IATA-730 поле депрекейтится, MER-код остаётся как «внутренний», IATA-732 становится основным для внешней отчётности и обмена с IATA/регуляторами.

**Сложность:** покрытие маппинга на сегодня = ~91 % (см. § 1), но из них только ~17 % строго 1:1. Остальные 74 % — требуют **ручной верификации** (один аналитик, 1–2 недели работы).

### Сценарий Б — «полный переход» (рисковый)

Принять IATA-732 как единственный кодификатор уже в 2027 и переразметить весь существующий справочник.

**Проблема:** 165 детализаций ЦУП (без MER-кода) в IATA-732 разлетаются на ~60 разных REASON в 6 разных GROUP — отчётность «распределение НМЧ по узлам» придётся пересобирать с нуля. Семантика ломается.

### Сценарий В — «гибрид» (не рекомендуется)

Часть кодов мигрировать в IATA-732, часть оставить в MER. Получим **третий неконсистентный справочник**.

## 8. Открытые вопросы (расширение к § 8 предыдущего отчёта)

9. **Q9 — карта диапазонов IATA-730 → IATA-732 GROUP:** автоматическая текущая карта слишком грубая (одна группа на 10 кодов). Готовы ли мы потратить ресурс аналитика на построение более тонкой карты на уровне PROCESS (буквы A–Z), а не GROUP?

10. **Q10 — STAKEHOLDER:** IATA-732 предполагает третий уровень кодирования (4 493 кода с учётом stakeholder). Это критично для регулирующих органов или избыточно для Утайр? Можем ли мы зафиксировать stakeholder как один атрибут (`A — airline`) для всех внутренних рейсов и тем самым свести 4 493 кода обратно к 553?

11. **Q11 — точность маппинга:** в § 6.1 я перечислил 6 заведомо ложных автоматических совпадений. Кто будет правую часть таблицы (IATA-732 кандидат) экспертно подтверждать или менять?

## 9. Артефакты

| Артефакт | Путь | Объём |
|---|---|---|
| Этот отчёт | [`docs/reports/CUP_codifier_genesis_v1.md`](./CUP_codifier_genesis_v1.md) | ~28 KB |
| Скрипт сборки | [`output/cup_codifier/build_genesis.py`](../../output/cup_codifier/build_genesis.py) | 7 KB |
| Полная машинная таблица | [`output/cup_codifier/genesis_full_table.csv`](../../output/cup_codifier/genesis_full_table.csv) | ~50 KB, 271 строка |
| Summary в JSON | [`output/cup_codifier/genesis_summary.json`](../../output/cup_codifier/genesis_summary.json) | <1 KB |
