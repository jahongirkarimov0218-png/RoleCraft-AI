# Extraction evaluation: dev

Analyzer 0.1.0 · dataset sha256 `6e9aa20a57b6e453` · 24 records

> Labels were written by the assistant that built the analyzer, from the text alone and before any parser output was looked at; every record is `review_status: unreviewed` and no human has reviewed it. Results show agreement with that reading, not accuracy against independent annotators. `dev` was used to find defects; `holdout` was run once after the dev work was finished. Datasets this small give wide uncertainty: differences of a few points are not evidence.

## Deterministic layer

| metric | precision | recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| nodes (strict: type + span) | 95.2% | 82.5% | 88.4% | 99 | 5 | 21 |
| nodes (span only) | 100.0% | 86.7% | 92.9% | 104 | 0 | 16 |
| edges (scored relations) | 86.4% | 52.8% | 65.5% | 19 | 3 | 17 |

### By language (nodes, strict)

| language | precision | recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| en | 100.0% | 97.5% | 98.7% | 39 | 0 | 1 |
| ru | 91.4% | 80.0% | 85.3% | 32 | 3 | 8 |
| uz | 93.3% | 70.0% | 80.0% | 28 | 2 | 12 |

### By node type (strict)

| type | precision | recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| SystemNode | 100.0% | 100.0% | 100.0% | 24 | 0 | 0 |
| TaskNode | 94.3% | 73.3% | 82.5% | 33 | 2 | 12 |
| ContextNode | 100.0% | 100.0% | 100.0% | 12 | 0 | 0 |
| ConstraintNode | 88.5% | 76.7% | 82.1% | 23 | 3 | 7 |
| ToolNode | 100.0% | 66.7% | 80.0% | 4 | 0 | 2 |
| ExampleNode | 100.0% | 100.0% | 100.0% | 3 | 0 | 0 |

### By relation

| relation | precision | recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| DEPENDS_ON | 100.0% | 66.7% | 80.0% | 10 | 0 | 5 |
| CALLS_TOOL | 100.0% | 66.7% | 80.0% | 4 | 0 | 2 |
| CONFLICTS_WITH | n/a | 0.0% | n/a | 0 | 0 | 3 |
| PRECEDES | 100.0% | 55.6% | 71.4% | 5 | 0 | 4 |
| EXEMPLIFIES | 0.0% | 0.0% | 0.0% | 0 | 3 | 3 |

## LLM layer

**Not run.** Not requested (pass --llm).

## Misses and extras (deterministic)

- dev-en-04: missed TaskNode 'Point out bugs and unclear names.'
- dev-en-06: missed edge EXEMPLIFIES 'Review: The battery died after a day.\nLabel: negative' -> 'Classify each review as positive, negative or neutral.'
- dev-en-06: extra edge EXEMPLIFIES 'Review: The battery died after a day.\nLabel: negative' -> 'Output only the label.'
- dev-en-08: missed edge CONFLICTS_WITH 'Always answer in formal English.' -> 'Never use formal language.'
- dev-ru-01: missed ConstraintNode 'Ответ должен быть не длиннее 100 слов.'
- dev-ru-02: missed TaskNode 'Сверь сумму из шага 1 с заказом на закупку.'
- dev-ru-02: missed TaskNode 'Кратко опиши расхождения, найденные на шаге 2.'
- dev-ru-02: extra ConstraintNode 'Кратко опиши расхождения, найденные на шаге 2.'
- dev-ru-02: missed edge DEPENDS_ON 'Кратко опиши расхождения, найденные на шаге 2.' -> 'Сверь сумму из шага 1 с заказом на закупку.'
- dev-ru-02: missed edge DEPENDS_ON 'Сверь сумму из шага 1 с заказом на закупку.' -> 'Извлеки номер счёта и сумму из {{invoice_text}}.'
- dev-ru-02: missed edge PRECEDES 'Извлеки номер счёта и сумму из {{invoice_text}}.' -> 'Сверь сумму из шага 1 с заказом на закупку.'
- dev-ru-02: missed edge PRECEDES 'Сверь сумму из шага 1 с заказом на закупку.' -> 'Кратко опиши расхождения, найденные на шаге 2.'
- dev-ru-04: missed ConstraintNode 'Пиши вежливо.'
- dev-ru-05: missed TaskNode 'Перескажи договор простым языком.'
- dev-ru-05: extra ConstraintNode 'Перескажи договор простым языком.'
- dev-ru-06: missed edge EXEMPLIFIES 'Отзыв: Батарея села за один день.\nМетка: отрицательная' -> 'Определи тональность каждого отзыва: положительная, отрицательная или нейтральная.'
- dev-ru-06: extra edge EXEMPLIFIES 'Отзыв: Батарея села за один день.\nМетка: отрицательная' -> 'Выводи только метку.'
- dev-ru-07: missed TaskNode 'Продолжай просить номер заказа, пока пользователь его не назовёт.'
- dev-ru-08: missed ConstraintNode 'Всегда отвечай официальным стилем.'
- dev-ru-08: missed TaskNode 'Перепиши текст пользователя яснее.'
- dev-ru-08: extra TaskNode 'Всегда отвечай официальным стилем.'
- dev-ru-08: missed edge CONFLICTS_WITH 'Всегда отвечай официальным стилем.' -> 'Никогда не используй официальный стиль.'
- dev-uz-01: missed ConstraintNode "Har bir javob 100 so'zdan oshmasin."
- dev-uz-02: missed TaskNode '{{invoice_text}} dan hisob-faktura raqami va summasini ajratib ol.'
- dev-uz-02: missed edge DEPENDS_ON '1-qadamdagi summani xaridga buyurtma bilan solishtir.' -> '{{invoice_text}} dan hisob-faktura raqami va summasini ajratib ol.'
- dev-uz-02: missed edge DEPENDS_ON '2-qadamda topilgan nomuvofiqliklarni qisqacha tasvirlab ber.' -> '1-qadamdagi summani xaridga buyurtma bilan solishtir.'
- dev-uz-02: missed edge DEPENDS_ON '{{invoice_text}} dan hisob-faktura raqami va summasini ajratib ol.' -> '{{invoice_text}}'
- dev-uz-02: missed edge PRECEDES '{{invoice_text}} dan hisob-faktura raqami va summasini ajratib ol.' -> '1-qadamdagi summani xaridga buyurtma bilan solishtir.'
- dev-uz-03: missed ToolNode 'search_flights'
- dev-uz-03: missed TaskNode 'Keyin eng arzon variant uchun book_hotel ni chaqir.'
- dev-uz-03: missed ToolNode 'book_hotel'
- dev-uz-03: missed edge CALLS_TOOL 'Keyin eng arzon variant uchun book_hotel ni chaqir.' -> 'book_hotel'
- dev-uz-03: missed edge CALLS_TOOL '{{trip_dates}} sanalari uchun reyslarni topishda search_flights vositasidan foydalan.' -> 'search_flights'
- dev-uz-03: missed edge PRECEDES '{{trip_dates}} sanalari uchun reyslarni topishda search_flights vositasidan foydalan.' -> 'Keyin eng arzon variant uchun book_hotel ni chaqir.'
- dev-uz-04: missed TaskNode "Xatolar va tushunarsiz nomlarni ko'rsat."
- dev-uz-04: missed ConstraintNode "Faylni to'liq qayta yozma."
- dev-uz-04: missed ConstraintNode 'Xushmuomala ohangda yoz.'
- dev-uz-04: extra TaskNode 'Xushmuomala ohangda yoz.'
- dev-uz-05: missed TaskNode 'Shartnomani oddiy tilda bayon qil.'
- dev-uz-05: missed ConstraintNode 'Huquqiy maslahat berma.'
- dev-uz-05: extra ConstraintNode 'Shartnomani oddiy tilda bayon qil.'
- dev-uz-06: missed TaskNode 'Har bir sharhni ijobiy, salbiy yoki neytral deb tasniflang.'
- dev-uz-06: missed edge EXEMPLIFIES 'Sharh: Batareya bir kunda tugadi.\nYorliq: salbiy' -> 'Har bir sharhni ijobiy, salbiy yoki neytral deb tasniflang.'
- dev-uz-06: extra edge EXEMPLIFIES 'Sharh: Batareya bir kunda tugadi.\nYorliq: salbiy' -> 'Faqat yorliqni chiqaring.'
- dev-uz-07: missed TaskNode "Foydalanuvchi buyurtma raqamini aytmaguncha uni so'rashda davom et."
- dev-uz-08: missed edge CONFLICTS_WITH 'Doimo rasmiy uslubda javob ber.' -> 'Hech qachon rasmiy uslubdan foydalanma.'
