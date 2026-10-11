# Status

Resume from this file if context is lost. Last updated: end of M6.

## Stage

| Stage | State |
|-------|-------|
| M0 Inspect | **done** |
| M1 IR and fixtures | **done** |
| M2 Vertical slice | **done** |
| M3 Full parsers and analysis | **done** |
| M4 Interfaces | **done** |
| M5 Semantic layer and hardening | **done** — Layer B + verifier, eval dataset/harness (dev + one-time holdout), scale fixes and measurements, axe in both themes, responsive checks, security matrix |
| M6 Handover | **done** — README run from a fresh clone, `.env.example`, Dockerfile (images built and run, see below), CI steps run locally, red-team, final report |

## Evidence (commands run in this session, end of M6; `scripts/ci-local.sh --skip-docker` in the working tree and again in a fresh clone)

- `uv run pytest -q` → **773 passed**, 0 failed, 0 skipped, 0 warnings (Python 3.13.16, 4 CPUs). (745 at end of M5; +2 rules-doc
  sync tests, +26 modal-opener tests. The fresh-clone run, made one commit earlier, passed 747.)
- `ruff check src tests` and `ruff format --check src tests` clean; `cd web && npx tsc --noEmit` clean; `npx vitest run` → 15 passed.
- `cd web && npx playwright test` → **63 passed** (desktop and one mobile project): core, analysis, exports, Mermaid (official
  parser), canvas (neighbour dimming, node drag), LLM layer (fake provider on loopback), accessibility (axe, both themes), responsive (6 sizes x 2 themes), performance.
- Evaluation (`eval/results/`, unreviewed labels, same author): **dev** nodes P 100 / R 100, edges P 100 / R 91.7 (tuned on this
  set; before tuning P 95.2 / R 82.5 and P 86.4 / R 52.8); **holdout, run once**: nodes P 93.9 / R 89.2 / F1 91.5, edges
  P 93.3 / R 71.8 / F1 81.2. LLM layer: **not run** (no provider or key in this environment).
- Performance (`docs/PERFORMANCE.md`): 177 nodes analysed in 0.09 s and shown in 0.8 s; 675 nodes in 0.34 s / 3.3 s; 1,333 nodes in
  0.84 s. Typing in search: 0.27 s / 0.65 s (was 1.55 s / 11.3 s).
- `npm audit --omit=dev` → 0 vulnerabilities.

## Defects found and fixed in M5 (each has a regression test)

Layer B and its tests found none (they were written first); everything below came from running real-sized or hostile input:
duplicate diagnostic ids for a tool named by several tasks (analysis raised); Markdown tool headings not recognised;
three accidentally quadratic analysis paths; quadratic placeholder scanning with 85 s on 200 KB of `{{`; search typing
rebuilt the graph layout per keystroke; Fit view did not fit a 177-node graph; a tablist holding inputs, a listbox with
non-option children, light-theme contrast 4.3:1, a squeezed icon button on phones; `analyze` treated a BOM-only file as
content; invisible bidi characters in four of our own test files; "briefly summarize ..." left uncovered (English);
Russian/Uzbek verb lists seven times thinner than English.

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

## M6 handover: what was run

- **README from a fresh clone** (`git clone` into a scratch directory, new virtual environment): `uv sync`; every CLI
  example in the README (`analyze`, `validate`, `explain`, `path`, `query`, `diff`, `openapi`, exit codes 0/1/2/3);
  `promptgraphify serve` + `npm ci` + `npm run build` + `npm run start`; a real browser then typed a random token,
  pressed Analyze Prompt, and found the token on the canvas and in the inspector. The `pip install .` route in a plain
  `python -m venv` also installed and ran. Defects found by doing this: the Playwright config assumed the sandbox's
  Chromium path and a fixed venv path (fixed, `PG_CHROMIUM` / `PG_PYTHON`); two README commands named nodes that do not
  exist or a direction with no path (corrected to commands that were executed).
- **CI steps** (`scripts/ci-local.sh --skip-docker`): ran green in a fresh clone (747 pytest, 15 vitest, 61 Playwright,
  ruff, tsc, `requirements.txt` in sync with `uv.lock`) and in the working tree after the last change (773 / 15 / 63).
  The workflow file `.github/workflows/ci.yml` itself was **never run by GitHub** (no push, by instruction); it assumes
  this folder is the root of its own repository (in this monorepo it would have to move to the repository root).
- **Docker**: a throw-away daemon was started inside the sandbox (vfs storage, no bridge network). `--target api`
  (155 MB) and `--target web` (939 MB) built from the Dockerfile; both containers started (`--network=host`) and reported healthy;
  42 browser tests (the core, analysis, exports, Mermaid and axe specs, desktop project) passed against the pair. Caveats: the sandbox's TLS-intercepting proxy required a CA
  shim, applied to a scratch copy of the Dockerfile only (the committed Dockerfile has none); `docker compose up` was
  **NOT run** (no bridge network; `docker compose config` validates the file). The daemon and its files were removed.
- **Red-team** (D-025): odd inputs (mixed languages, duplicate tool names, nested templates, self-dependency, a 320 KB
  single line, bidi/NUL/script text, BOM-only) all analysed without error; the probe found that common English
  openers ("You must ...", "Your task is to ...") left instructions uncovered; fixed with tests. The evaluation
  could not have found it (48 records, same author), which is stated in `eval/README.md`'s caveats and D-025.

## Known limitations (honest list)

Measured on the one-time holdout run (`eval/results/holdout.md`) and not fixed afterwards, so the recorded numbers stay valid:

- **A response verb plus a style word reads as a constraint**: "Write a short email to the employee." (Uzbek),
  "Explain each concept step by step ... with one short question." (Russian) become `ConstraintNode`; a strict verb wins
  ("Briefly summarize ..." is a task), a response verb with a tone/format word does not.
- **"Keep X unchanged" / "as is" / "verbatim"** (preservation constraints) is not a constraint signal in any language.
- **Vocabulary gaps** remain whenever a prompt uses a verb outside the lists (found: `примени`, `изложи` as a task);
  such a sentence is reported as uncovered, never guessed. English is at 97.5 % node F1 on holdout, Russian 86.8 %, Uzbek 89.7 %.
- **Morphology**: Russian tool mentions need the nominative ("инструмент X"; "с помощью инструмента X" is missed);
  Uzbek negative imperatives are recognised for a list of stems, not for every verb ("topma" is missed); handoff
  targets with Uzbek suffixes ("To'lov agentiga") are not resolved.
- **Modal openers are English only** (D-025): "Ты должен ..." and "Siz ... kerak" stay uncovered because the Russian/Uzbek
  verb lists hold imperatives, not infinitives or verbal nouns. Sentences without a task verb after the opener are
  uncovered by design ("You must be kind.").
- **A line-initial tag inside a sentence** ("<document> teglari orasidagi matnni ..." in Uzbek word order) is read as a
  container opener, which splits the sentence.
- **`CONFLICTS_WITH`** needs near-identical wording: "Always answer in formal English" vs "Never use formal language" is not
  found (3 of 3 such pairs missed on dev). The optional LLM layer is the intended tool; it was not evaluated.
- **Evaluation**: 48 records, labels unreviewed and written by the analyzer's author; the LLM layer's precision/recall is
  **not run**. Scores are agreement with one annotator, not accuracy.
- `OVERRIDES` from role precedence alone, `PRODUCES` for output files and tools given as a JSON array of strings are not
  implemented. XML `<step>` ordering is not interpreted.
- Accessibility: automated (axe) and keyboard tests only; no test with a real screen reader. The graph canvas is reachable
  by keyboard through the node list.
- Large graphs (> ~600 nodes) open in seconds and pan unevenly (95th-percentile frame 217 ms at 675 nodes, software
  rendering); layout runs on the main thread.

## NOT VERIFIED / not available

- The GitHub Actions workflow has not run on GitHub. `docker compose up` was not run. Docker builds were verified only
  with the sandbox CA shim (scratch copy of the Dockerfile).
- LLM layer against a real model: **not run** (no provider or key); only the fake provider on loopback.
- Evaluation labels are unreviewed and written by the analyzer's author.
- Screen reader: not tested. Real-device mobile: not tested (emulated Pixel 5 and five other sizes only).
- The `ai-engineer-roadmap` plugin does not exist in this session (`ListPlugins` returned no results) and no TDD /
  debugging / review skills are listed (`ListSkills`): the final-report item for it is N/A.
- Tooling note: the file-writing tool decodes `\uXXXX` escapes in file content; write invisible or
  special characters (BOM, bidi marks) via a script using `chr()`, then check the bytes.
