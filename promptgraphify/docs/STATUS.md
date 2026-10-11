# Status

Resume from this file if context is lost. Last updated: end of M1.

## Stage

| Stage | State |
|-------|-------|
| M0 Inspect | **done** |
| M1 IR and fixtures | **done** |
| M2 Vertical slice | **done** (text / Markdown / XML) — see evidence below |
| M3 Full parsers and analysis | next: YAML/JSON/messages front-ends, DAG, analyzer rules, query engine, DAG tab, diagnostics sidebar |
| M4 Interfaces | not started: CLI, remaining API endpoints, SQLite, exports, diff |
| M5 Semantic layer and hardening | not started |
| M6 Handover | not started |

## Evidence for M2 (commands run in this session)

- `.venv/bin/python -m pytest -q` → 243 passed, 2 skipped (YAML/JSON fixtures wait for M3).
- `cd web && npx vitest run` → 13 passed. `npx tsc --noEmit` → clean.
- `cd web && npx playwright test` → 13 passed (12 desktop, 1 mobile Pixel 5): unique-token flow, two prompts
  → two graphs, emoji offsets, edge rationale + evidence highlight, search/filter, editor-click selection,
  keyboard list, markup not executed, stale banner, error recovery, theme/privacy badge, Ctrl+Enter, mobile.
- The 31 text/MD/XML fixtures match their hand-written expectations (nodes and edges exact).

## What exists now

- Core: scanner (`markup.py`), sentence splitter (`text.py`), classifier, placeholders, extraction,
  relations, `analyze()`, `graphjson.py`; signal words in `signals/*.json`.
- API: `POST /api/analyze`, `GET /api/health`, OpenAPI → `web/openapi.json` → `web/src/lib/api-types.ts`.
- Web: Next.js workbench (CodeMirror editor, React Flow graph, node list, inspector, filters, theme).

## Next action (M3)

1. `yaml`/`json` front-ends (string values keep exact spans; escapes → `decoded_text`), un-skip fixtures 06/07.
2. Execution DAG (`dag.py`), diagnostics (`analyzer.py`, each rule with a positive and a negative test),
   `tests/test_fixtures_analysis.py` (diagnostics + DAG expectations), query engine (8 queries).
3. UI: DAG tab, diagnostics sidebar, edge evidence polish.

## Known limitations so far (honest list)

- Classification is signal-word based; the fixtures were written by the same author as the rules, so the
  86/86 sentence-classification match proves consistency, not accuracy. A separate evaluation set comes in M5.
- Tone adjectives without a format/limit word ("Be kind to every user") are not classified: they stay
  *uncovered* (reported, never guessed).
- `OVERRIDES` from role precedence alone, `PRODUCES` for output files, and multi-tool JSON arrays are not implemented.

## Known blockers / NOT VERIFIED so far

- Docker daemon unreachable → Docker build NOT VERIFIED (see D-008).
- Acceptance criteria 3–5, 7 are verified for text/MD/XML only; 6, 8–11 still open (M3/M4).
- Tooling note: the file-writing tool decodes `\uXXXX` escapes in file content; write invisible or
  special characters (BOM, bidi marks) via a script using `chr()`, then check the bytes.
