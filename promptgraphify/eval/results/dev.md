# Extraction evaluation: dev

Analyzer 0.1.0 · dataset sha256 `6e9aa20a57b6e453` · 24 records

> Labels were written by the assistant that built the analyzer, from the text alone and before any parser output was looked at; every record is `review_status: unreviewed` and no human has reviewed it. Results show agreement with that reading, not accuracy against independent annotators. `dev` was used to find defects; `holdout` was run once after the dev work was finished. Datasets this small give wide uncertainty: differences of a few points are not evidence.

## Deterministic layer

| metric | precision | recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| nodes (strict: type + span) | 100.0% | 100.0% | 100.0% | 120 | 0 | 0 |
| nodes (span only) | 100.0% | 100.0% | 100.0% | 120 | 0 | 0 |
| edges (scored relations) | 100.0% | 91.7% | 95.7% | 33 | 0 | 3 |

### By language (nodes, strict)

| language | precision | recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| en | 100.0% | 100.0% | 100.0% | 40 | 0 | 0 |
| ru | 100.0% | 100.0% | 100.0% | 40 | 0 | 0 |
| uz | 100.0% | 100.0% | 100.0% | 40 | 0 | 0 |

### By node type (strict)

| type | precision | recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| SystemNode | 100.0% | 100.0% | 100.0% | 24 | 0 | 0 |
| TaskNode | 100.0% | 100.0% | 100.0% | 45 | 0 | 0 |
| ContextNode | 100.0% | 100.0% | 100.0% | 12 | 0 | 0 |
| ConstraintNode | 100.0% | 100.0% | 100.0% | 30 | 0 | 0 |
| ToolNode | 100.0% | 100.0% | 100.0% | 6 | 0 | 0 |
| ExampleNode | 100.0% | 100.0% | 100.0% | 3 | 0 | 0 |

### By relation

| relation | precision | recall | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| DEPENDS_ON | 100.0% | 100.0% | 100.0% | 15 | 0 | 0 |
| CALLS_TOOL | 100.0% | 100.0% | 100.0% | 6 | 0 | 0 |
| CONFLICTS_WITH | n/a | 0.0% | n/a | 0 | 0 | 3 |
| PRECEDES | 100.0% | 100.0% | 100.0% | 9 | 0 | 0 |
| EXEMPLIFIES | 100.0% | 100.0% | 100.0% | 3 | 0 | 0 |

## LLM layer

**Not run.** Not requested (pass --llm).

## Misses and extras (deterministic)

- dev-en-08: missed edge CONFLICTS_WITH 'Always answer in formal English.' -> 'Never use formal language.'
- dev-ru-08: missed edge CONFLICTS_WITH 'Всегда отвечай официальным стилем.' -> 'Никогда не используй официальный стиль.'
- dev-uz-08: missed edge CONFLICTS_WITH 'Doimo rasmiy uslubda javob ber.' -> 'Hech qachon rasmiy uslubdan foydalanma.'
