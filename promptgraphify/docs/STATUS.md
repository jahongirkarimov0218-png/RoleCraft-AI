# Status

Resume from this file if context is lost. Last updated: end of M1.

## Stage

| Stage | State |
|-------|-------|
| M0 Inspect | **done** |
| M1 IR and fixtures | **done** — 136 tests pass (`.venv/bin/python -m pytest -q`): ontology, spans (emoji/CRLF/BOM), ids, Layer C validator, coverage, 33 fixtures with hand-written expectations |
| M2 Vertical slice | next |
| M3 Full parsers and analysis | not started |
| M4 Interfaces | not started |
| M5 Semantic layer and hardening | not started |
| M6 Handover | not started |

## What exists (M1)

- `src/promptgraphify/`: `ontology.py` (6 node types, 11 relations, endpoint table, DAG projection),
  `spans.py`, `ids.py`, `ir.py` (Pydantic IR + `GraphDocument`), `validate.py` (Layer C), `coverage.py`,
  `security.py` (`sanitize_label`), `rules.py` (21 analyzer rules, mirrors spec §7).
- `docs/ANALYSIS_SPEC.md` — the contract for parsers, edges, DAG, diagnostics, IDs, fixture format.
- `tests/fixtures/NN_*/` — 33 fixtures (en/ru/uz; text, MD, XML, YAML, JSON, multi-file, BOM+CRLF+emoji,
  empty, malformed XML/templates, cycles, loops, injection …) with `expected.json` written before any parser.
  `tests/test_fixtures_wellformed.py` checks the expectations against the spec; `tests/dag_model.py`
  re-derives the hand-written DAG orders independently.

## Next action (M2)

Layer A for plain text / Markdown / XML → builder → `POST /api/analyze` → Next.js UI (editor, Analyze,
Knowledge Graph, inspector, span highlight) → e2e with a random unique token. The first parser test
must be the fixtures: `tests/test_fixtures_parser.py` compares parser output with `expected.json`
(nodes and edges exact; diagnostics non-exhaustive). Do not change an expectation to match the parser
without a reason written into `DECISIONS.md`.

## Known blockers / NOT VERIFIED so far

- Docker daemon unreachable → Docker build NOT VERIFIED (see D-008).
- No parser, API or UI yet; acceptance criteria 1–12 are all still unverified.
- Tooling note: the file-writing tool decodes `\uXXXX` escapes in file content; write invisible or
  special characters (BOM, bidi marks) via a script using `chr()`, then check the bytes.
