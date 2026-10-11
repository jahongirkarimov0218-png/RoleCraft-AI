# Decisions

Format: ID · decision · basis (**FACT** / **ASSUMPTION**) · reason · status.
Append-only; if a decision changes, add a new entry that supersedes the old one.

## D-001 · Location and branch
Project lives in `promptgraphify/` inside the existing repository. The existing RoleCraft AI code
(Next.js 14 app, `src/`, `test/`, `e2e/`, `.autopilot/`) is unrelated and is not modified.
Work happens on branch `ccr-63aee89f-ej0mig` (the session's designated branch, separate from `main`).
No push, no PR.
**FACT**: repo root contains a Next.js 14 app (`package.json`, `src/app`), checked with `ls`/`git log`.
Status: accepted.

## D-002 · License
MIT. Independent implementation; no reference code copied (see `REFERENCE_NOTES.md`).
**ASSUMPTION** (task default: "permissive, MIT or Apache-2.0"); MIT chosen for brevity.
README carries the community-built / not-affiliated note. Status: accepted.

## D-003 · Offset unit for spans: Unicode code points
`source_span = {start, end}` are offsets in **Unicode code points** (Python `str` indices) into the
**raw** source text as received: no newline normalisation (CRLF stays 2 code points), a leading BOM
(U+FEFF) is kept as index 0 and parsers skip it; text is decoded as UTF-8, not `utf-8-sig`.
Invariant checked by Layer C: `source[start:end] == original_text`.
The frontend converts code points ↔ UTF-16 only at the editor boundary with one tested helper.
**ASSUMPTION.** Reason: the invariant is literally true in Python, JSON stays language-neutral, the
verifier needs no conversion; the cost is one conversion function in the UI, covered by CRLF/BOM/emoji
tests. Trade-off: UTF-16 would remove that function but force conversion in every Python parser.
Status: accepted for M1; must be re-confirmed by the first e2e highlight test.

## D-004 · Node IDs are content/structure based, not offset based
`id = <type>:<structural-path>:<slug>[~<n>]` where the structural path is the section/agent/message path
(slugged), and `<slug>` is a normalised label for named things (variables, tools, agents) or a short hash
of the normalised text for free-text instructions. Identical siblings get `~2`, `~3` by document order.
Inserting a line elsewhere does not change other IDs. Editing an instruction's text changes its ID;
`diff` then reports remove+add, and a similarity pair is only labelled *probably modified*.
Normalisation follows the lesson of the reference `ids.py` (one module, casefold+NFKC fixpoint).
**ASSUMPTION**; exact recipe is frozen in M1 with tests. Status: provisional.

## D-005 · LLM layer
Layer B is optional, off by default, behind an adapter with an OpenAI-compatible implementation;
provider/model/base URL/key come from environment variables only. Every LLM-proposed node/edge goes
through the same provenance verifier. **ASSUMPTION**, from the task. Status: accepted.

## D-006 · `graph.html` has no CDN dependency
**FACT**: the reference loads vis-network from unpkg (`exporters/html.py:636`).
**ASSUMPTION**: PromptGraphify's `graph.html` is one self-contained file (inline data, inline renderer),
so it opens offline from `file://`. Details and the renderer choice are decided in M4.
Status: provisional.

## D-007 · Frontend/backend library versions
Pinned from the *installed* versions and their docs in M2, not from memory.
**FACT** (npm/uv registry, 2026-10-11): next 16.4.0, tailwindcss 4.3.3, @xyflow/react 12.12.0,
shadcn 4.21.4, @playwright/test 1.64.0; fastapi 0.143.0, pydantic 2.14.0, networkx 3.7, uvicorn 0.54.0,
pytest 9.1.1, hypothesis 6.169.0, ruff 0.17.0. Status: pending (M2).

## D-008 · Environment constraints that change what can be verified
**FACT** (commands run in M0): Python 3.13.16, uv 0.11.32, Node v22.22.0, npm 10.9.4, Chromium 141 at
`/opt/pw-browsers/chromium-1194/chrome-linux/chrome`, Python `sqlite3` 3.45.1, PyPI and npm reachable.
Docker CLI 29.8.2 exists but the daemon is **not reachable** (`/var/run/docker.sock` missing) →
`docker build` is **NOT VERIFIED** unless a daemon can be started inside the allowed scope (M6).
No `ai-engineer-roadmap` plugin is installed (`ListPlugins` → empty) → that report line is N/A.
Status: accepted.

## D-009 · Python floor 3.12
**FACT**: `uv sync` with `requires-python >=3.11` failed because networkx 3.7 requires Python ≥ 3.12
(`<3.14.1 | >3.14.1`). Floor raised to 3.12; the lockfile pins networkx 3.7, pydantic 2.14.0,
fastapi 0.143.0, uvicorn 0.54.0, pyyaml 6.0.3. Tested only on CPython 3.13.16. Status: accepted.

## D-010 · Fixture expectations: what is exact, what is not
Nodes and edges are compared as exact sets; diagnostics are non-exhaustive (listed ones must appear
with the stated node set, `absent_rules` must not fire); `uncovered` is exact. Reason: granularity and
edges are the bottleneck and must not drift; diagnostic completeness is covered by per-rule positive and
negative analyzer tests in M3. Expectations were written from the fixture text and `ANALYSIS_SPEC.md`
before any parser existed. The labels are `review_status: unreviewed` — I wrote them, nobody else has
checked them. Status: accepted.

## D-011 · Classification priority (sentence level)
Prohibition > strict task verb > limit/format/style signal > other task verb > uncovered
(ANALYSIS_SPEC §3.5). Chosen so "Reply in a polite tone." is a constraint while "Answer the question
using the knowledge base." and "Break the goal into at most 5 subtasks." are tasks. **ASSUMPTION**:
verb lists in `signals/*.json` are incomplete by nature; unknown verbs lead to *uncovered*, never to a
guessed node. Status: accepted, to be re-checked against real-world prompts in M5.

## D-012 · Global constraints are not materialised as edges
A constraint whose scope is the document root or a message-role container applies to everything; it
carries `metadata.scope = "global"` and queries add it with the label "global scope". Reason: C
constraints × T tasks edges make 100+ node graphs unreadable and add no information. Status: accepted.

## D-013 · Self-reference and loops
`metadata.loop = true` marks deliberate repetition (excluded from cycle detection; needs a stop
condition, otherwise `loop.no_stop_condition`). `metadata.self_reference = true` marks a unit that
depends on itself (always a cycle of length 1). Status: accepted.

## D-014 · Editor: CodeMirror 6 instead of Monaco
The task asks for a "Monaco-style" editor. **FACT** (design reasoning, not measured): Monaco needs its own
worker/loader setup and by default loads from a CDN, which breaks the offline/local requirement and
complicates the Next.js bundle. CodeMirror 6 gives what the UI needs (line numbers, selection, range
decorations, scroll-to, ARIA attributes, keymaps) and bundles offline. Offsets are UTF-16 in CodeMirror;
`web/src/lib/offsets.ts` converts at that single boundary (D-003). Status: accepted.

## D-015 · Variables and tools live in one global namespace
IDs of variables and tools are `ctx:-:<name>` / `tool:-:<name>` regardless of file or section: a variable
declared in one file and used in another is one node. Reason: prompt chains pass values between files;
per-file duplicates would raise false `variable.undeclared`. Created nodes (undeclared variable,
undefined tool) inherit the role/agent of the unit that first mentions them. Status: accepted.

## D-016 · Every IR field is required
All Pydantic IR models have no field defaults (nullable fields are required-but-nullable). Reason: the
generated OpenAPI/TypeScript types then have no optional fields; `tests/test_openapi_contract.py` enforces
it. The size limit (`max_input_chars`) is a runtime guard, not part of the analysis config, so it never
changes `graph_id`. Status: accepted.

## D-017 · Web stack versions (FACT, `npm view` on 2026-10-11, pinned by `web/package-lock.json`)
Next.js 16.4.0 (Turbopack), React 19.3.0, Tailwind CSS 4.3.3 (`@tailwindcss/postcss`), @xyflow/react
12.12.0, @dagrejs/dagre 3.1.1, CodeMirror 6, Vitest 5.0.3, Playwright 1.64.0, TypeScript **5.9.3** (not 7.0.2:
`openapi-typescript` 7.13 declares a peer dependency on TypeScript 5). shadcn/ui: components are
hand-written in `web/src/components/ui/` (cva + Radix) because the shadcn CLI would fetch from a registry;
they follow the shadcn conventions but were not generated by its CLI. `next.config.ts` sets
`agentRules: false` so `next dev` does not write assistant instruction files into the repository.
Next.js APIs used were checked against the docs shipped in `node_modules/next/dist/docs`.

## D-018 · graph.html is one offline file with a hash-pinned CSP
`graph.html` has no CDN, font or fetch (FACT: opened from `file://` in Chromium, only the file itself was
requested, `tests`/`e2e/exports.spec.ts`). The graph is drawn as SVG by Python (all text escaped there); the
data block is JSON with `<`, `>`, `&` and every non-ASCII character escaped; the viewer script uses
`textContent` only. The CSP is `default-src 'none'` plus the SHA-256 of the one inline script and the one
inline style, so a modified script does not run at all (FACT: a variant with a changed script never became
ready in a mutation check). Colours that would need `style=""` attributes use attribute selectors instead.
No graph library is bundled: pan/zoom/inspect are ~150 lines of vanilla JS. Reason: "serversiz, bitta fayl" and
no dependency to audit. Status: accepted.

## D-019 · XML 1.0 cannot carry every character; exports replace and count
SVG and GraphML are XML. Controls, lone surrogates and U+FFFE/FFFF are not allowed there. Decision:
replace them with U+FFFD and store the number in the GraphML graph attribute `xml_replaced_chars`; `graph.json`
keeps the original text. (Found by feeding hostile text to every exporter; the first version produced
ill-formed XML.) A lone UTF-16 surrogate in *input* is rejected by `analyze()` with `invalid_text` (HTTP 422):
it is not valid Unicode text and used to crash hashing. Status: accepted.

## D-020 · DAG-view arrows are labelled by what they mean
Arrows of the Execution DAG point prerequisite → dependent, so a reversed relation (`DEPENDS_ON`) is labelled
"needed by" in SVG/Mermaid DAG views, and several knowledge-graph edges that project to the same ordered pair
are drawn once with a joined label (the DAG metric `arrow_count` already counts distinct pairs).
Status: accepted.

## D-021 · CLI contract
Exit codes: 0 ok · 1 findings (`validate` at `--fail-on` severity, `analyze --fail-on`) or `diff` found
differences · 2 usage or input error (unreadable, unsafe, oversized input; bad flags) · 3 not resolved (name
matched nothing or several nodes, no path) · 4 unsupported or invalid graph file · 5 internal error (type
name only, no internals). Query-like commands read `--graph FILE`, else analyse `PATH...`, else
`./promptgraphify-out/graph.json` (the default output of `analyze`). `diff` takes files, directories or
graph.json for either side; a `.json` with `graph_id`, `nodes` and `edges` is treated as a graph and read
strictly (a wrong `schema_version` is exit 4, never silently analysed as a prompt). File collection
(`collect.py`): symlinks inside a directory are skipped and reported, an explicit symlink must stay inside its
own directory, only regular files are opened (never a FIFO), limits are errors not silent cuts, files must be
strict UTF-8 without NUL, an output file never overwrites an input. `serve` binds 127.0.0.1 by default.
Reason: scripts and CI need stable codes; "never guess a name" is the spec. Status: accepted.
