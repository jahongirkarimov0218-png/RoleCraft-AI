# Status

Resume from this file if context is lost. Last updated: end of M4.

## Stage

| Stage | State |
|-------|-------|
| M0 Inspect | **done** |
| M1 IR and fixtures | **done** |
| M2 Vertical slice | **done** |
| M3 Full parsers and analysis | **done** |
| M4 Interfaces | **done** — CLI (7 commands), 8 API endpoints incl. `/api/diff` and `/export/{format}`, SQLite, six exports, diff, Export menu in the UI |
| M5 Semantic layer and hardening | **next** — LLM adapter + provenance verifier, eval dataset/harness, security matrix, 150+ node performance, accessibility, responsive/theme checks |
| M6 Handover | not started — README, `.env.example`, Dockerfile, CI, fresh-clone verification, red-team, final report |

## Evidence (commands run in this session, end of M4)

- `cd promptgraphify && uv run pytest -q` → **535 passed**, 0 failed, 0 skipped (1 third-party deprecation warning from
  Starlette's TestClient asking for `httpx2`).
- `ruff check src tests` and `ruff format --check src tests` clean.
- `cd web && npx tsc --noEmit` clean; `npx vitest run` → 15 passed.
- `cd web && npx playwright test` → **39 passed** (38 desktop incl. exports and Mermaid, 1 mobile). Playwright starts
  the backend and the production build itself and refuses to reuse a stale server unless `PG_REUSE_SERVER=1`.
- `npm audit --omit=dev` → 0 vulnerabilities; `npm audit` (with dev tools, mainly Mermaid used only by a test) → 2 low.
- Mermaid exports (graph and DAG views, six prompts incl. hostile and cyclic) are accepted by the official
  Mermaid 11.17.2 parser and render without script elements; the parser rejects an invalid diagram (negative control).
- `graph.html` downloaded through the UI opens from `file://` with no network request and no CSP violation; a
  hostile prompt does not execute (premise asserted: payload text is displayed). A mutation check showed the
  probe detects a viewer without CSP that uses `innerHTML`.
- Real CLI run in a scratch directory: `analyze`, `explain`, `path`, `query`, `validate`, `diff` gave the documented
  exit codes (0, 3 for an ambiguous name, 1 for differences, 2 for a missing file, 4 for a non-graph `--graph`).

## What exists now

- Core: `markup` / `text` / `classify` / `placeholders` / `extract` / `relations`; YAML+JSON front-ends
  (`yamlscan`, `jsonscan`, `structured`); `dag`; `analyzer` (21 rules); `queries` (8); `storage`; `graphjson`;
  `validate` (Layer C incl. DAG); `diff`; `collect` (safe file reading); `exporters/` (html, report, svg,
  mermaid, graphml, registry).
- CLI: `analyze`, `validate`, `explain`, `path`, `query`, `diff`, `serve`, `openapi` (D-021).
- API: `POST /api/analyze|validate|diff`, `GET /api/graph/{id}`, `/node/{id}`, `/path`, `/query/{name}`,
  `/export/{format}`, `/api/queries`, `/api/health`.
- Web: Knowledge Graph + Execution DAG tabs, diagnostics, queries, node list, inspector, multi-file tabs, Export menu.

## Bugs found by this stage's own tests (kept as regression tests)

- SVG/GraphML were ill-formed XML for characters XML cannot carry (D-019).
- A lone surrogate in the input crashed `analyze()` (now `invalid_text`).
- The DAG-view arrows used the stored relation name against their direction (D-020).
- `diff` reported a changed sequence when only a step on the critical path was reworded.
- A report without an inventory never mentioned nodes that had no edges.
- Hostile-text tests could pass vacuously (payload on an unrecognised line): premise assertions added.

## Next action (M5)

1. Layer B: provider-agnostic adapter (OpenAI-compatible, env-configured, off by default), response schema,
   provenance verifier, fallback with warning, fake-adapter contract tests, key masking in logs.
2. Eval dataset (`review_status: unreviewed`) with dev/holdout split, precision/recall for the deterministic layer;
   real-LLM evaluation reported "not run" unless a key is given.
3. Security matrix test, 150+ node timings (analysis and UI), accessibility (axe, keyboard), responsive and theme checks,
   source-hygiene test for invisible characters.

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
- The `ai-engineer-roadmap` plugin does not exist in this session (`ListPlugins` returned no results) and no TDD /
  debugging / review skills are listed (`ListSkills`): the final-report item for it is N/A.
- Acceptance criteria 1 (fresh clone from README) and 12 (final counts) are re-verified in M6.
- Tooling note: the file-writing tool decodes `\uXXXX` escapes in file content; write invisible or
  special characters (BOM, bidi marks) via a script using `chr()`, then check the bytes.
