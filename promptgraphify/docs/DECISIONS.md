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
