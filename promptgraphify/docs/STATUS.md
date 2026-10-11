# Status

Resume from this file if context is lost. Last updated: end of M1.

## Stage

| Stage | State |
|-------|-------|
| M0 Inspect | **done** |
| M1 IR and fixtures | **done** |
| M2 Vertical slice | **done** |
| M3 Full parsers and analysis | **done** — YAML/JSON, Execution DAG, 21 analyzer rules, 8 queries, DAG tab, diagnostics, queries panel, multi-file |
| M4 Interfaces | in progress: SQLite store + 5 of 6 API endpoints done; CLI, `/api/diff`, diff, exports (graph.html, GRAPH_REPORT.md, Mermaid, GraphML, SVG/PNG) still open |
| M5 Semantic layer and hardening | not started |
| M6 Handover | not started |

## Evidence (commands run in this session)

- `.venv/bin/python -m pytest -q` → 414 passed (fixtures: nodes, edges, diagnostics, DAG all match; per-rule
  positive+negative tests; property tests for spans/determinism; YAML/JSON hostile inputs; API; SQLite).
- `cd web && npx vitest run` → 15 passed; `npx tsc --noEmit` clean.
- `cd web && npx playwright test` → 21 desktop + 1 mobile passed (Playwright starts the backend and the
  production build itself and refuses to reuse a stale server unless `PG_REUSE_SERVER=1`).

## What exists now

- Core: `markup` / `text` / `classify` / `placeholders` / `extract` / `relations`; YAML+JSON front-ends
  (`yamlscan`, `jsonscan`, `structured`); `dag`; `analyzer`; `queries`; `storage`; `graphjson`; `validate` (Layer C incl. DAG).
- API: `POST /api/analyze|validate`, `GET /api/graph/{id}`, `/node/{id}`, `/path`, `/query/{name}`, `/api/queries`, `/api/health`.
- Web: Knowledge Graph + Execution DAG tabs, diagnostics, queries, node list, inspector, multi-file tabs.

## Next action (M4)

1. `diff.py` (stable-ID matching, six change kinds, "probably modified" by similarity) + `POST /api/diff`.
2. CLI (`analyze`, `explain`, `path`, `validate`, `diff`) with documented exit codes.
3. Exports: graph.html (offline, no CDN), GRAPH_REPORT.md, Mermaid, GraphML, SVG/PNG.

## Known limitations so far (honest list)

- Classification is signal-word based; fixtures were written by the same author as the rules, so the
  sentence-classification match proves consistency, not accuracy. An evaluation set comes in M5.
  Verbs outside the word lists (`data/signals/*.json`) leave a sentence *uncovered* (reported, never guessed).
- Tone adjectives without a format/limit word ("Be kind to every user") are not classified.
- `OVERRIDES` from role precedence alone, `PRODUCES` for output files and tools given as a JSON array of
  strings are not implemented. XML `<step>` ordering is not interpreted.
- Mobile layout is verified by one Playwright test (Pixel 5 viewport) and one screenshot, not a full audit.

## Known blockers / NOT VERIFIED so far

- Docker daemon unreachable → Docker build NOT VERIFIED (see D-008).
- Acceptance criteria 3–5, 7 are verified for text/MD/XML only; 6, 8–11 still open (M3/M4).
- Tooling note: the file-writing tool decodes `\uXXXX` escapes in file content; write invisible or
  special characters (BOM, bidi marks) via a script using `chr()`, then check the bytes.
