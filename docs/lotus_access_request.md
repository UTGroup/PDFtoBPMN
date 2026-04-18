# KEEP API на dflib — нужны 3 вещи

Привет!

Чиним автосбор Word'ов из СМК через KEEP. Упёрся в три блокера, нужна твоя помощь.

## 1. ACL для service-аккаунта KEEP в `dflib` (+ `subph`, `rppnew`)

Сейчас вижу только карточки `Form="DocumentAdds"`. Открыть родителя (где attachment) — 404:

```
GET /api/v1/document/FF64182FB2FFD01B45258B430034381F?dataSource=dflib&attachments=true
→ 404 "No document you can access found"
```

Нужно: **Reader** + доступ к `Form="Document"/"DocumentReg"`, `Form="Image"`, полям `$FILE`/`$FILEDATA`/`Body`.

## 2. KEEP SCHEMA для views с образами

```
GET /api/v1/lists/(Образы документов по ParentUIN)?dataSource=dflib&key=<parentunid>&documents=true
→ 500 "Document2JsonSelected called without a field list, check your SCHEMA"
```

Нужно прописать exposed-поля для form `Image` в трёх views:
- `(Обазы документов по ParentUIN)`
- `(Обазы документов по версиям)`
- `(Обазы документов по именам)`

Минимум полей: `ParentUIN`, `FileName`, `Version`, `IsActive`, `$FILE`, `Form`, `@unid`, `@modified`.

## 3. Поиск/DQL по `DocNum`

`ftsearch`, `key+keyAllowPartial`, DQL `DocNum = '...'` — всё возвращает пусто или игнорится. Сейчас приходится тянуть всю view (1373 записи) и фильтровать локально.

Нужно: design catalog / DQL-индекс по `DocNum`, `Form`, `DocStatus` в `dflib`. И, если можно, включить `?ftsearch=` на `/api/v1/lists/(view)`.

## 4. Подскажи, где лежат:

В `dflib` не нашёл (проверял `(DocumentByNumber)` и `(DocumentByNumberForAll)`):
- **КД-РГ-148** (взаимодействие ЦУП↔ДЦ)
- **РИ-Б8.1.018** (произв. отчётность Ф1)
- **РИ-М1.016** (произв. отчётность Ф2)

`rppnew`? `subph`? архив? Или у них другой формат номера?

---

**Целевой сценарий после фикса:**
`ftsearch DocNum → parentunid → (Обазы по ParentUIN) → последний .docx по Version → /api/v1/attachment/{unid}/{file}`

Если путь неверный для нашей конфигурации — кинь эталонный, как правильно вытащить последний действующий .docx.

Логи/трассы пришлю по запросу. Спасибо!

— Будник А. Н., PDFtoBPMN
