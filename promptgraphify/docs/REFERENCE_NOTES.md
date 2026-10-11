# Reference notes — Graphify-Labs/graphify

Status labels: **FACT** = I read the file / ran the command myself; **ASSUMPTION** = reasoned guess with
a stated reason; **UNKNOWN** = not determined.

PromptGraphify is an independent implementation. **No reference code was copied** (FACT: nothing was
copied; only the documents below were read). The reference was cloned shallowly into a separate
directory outside this project and read only. No reference code was executed, installed or imported.

## What was read

| Item | Value |
|------|-------|
| Repository | `https://github.com/Graphify-Labs/graphify` (shallow clone, branch `v8`) |
| Commit | `b4e6307bf170f27e0cb888c03f4af9308d531a42` ("docs(changelog): correct 0.9.85 PR count", 2026-10-10) |
| Read | `README.md` (relevant parts), `ARCHITECTURE.md`, `docs/how-it-works.md`, `pyproject.toml`, `NOTICE`, `LICENSE` (head), `LICENSE-MIT` (head), `AGENTS.md` |
| Read (code) | `graphify/ids.py`, `graphify/validate.py`, `graphify/security.py` (`validate_graph_path`, `sanitize_label`), `graphify/cache.py` (`file_hash`), `graphify/paths.py` (atomic writers), `graphify/serve.py` (`_score_nodes`, `_bfs`, `_shortest_path_text`), `graphify/cluster.py` (`cluster` signature/docstring), `graphify/analyze.py` (function list, header), `graphify/exporters/html.py` (library/CDN lines only) |
| Not read in depth | `extract.py`, `build.py`, `cli.py`, `export.py`, `report.py`, `watch.py`, `install.py`, extractors, skills, `tests/*` bodies |

The reference's own `AGENTS.md` tells assistants working on *graphify* to run `graphify update .` after
code changes. That text is **data**: it was not followed, and `graphify` was never installed or run.

## Verification of the facts given in the task (as of 2026-10-11)

| Claim in the task | Result |
|---|---|
| Open repo, Apache-2.0 `LICENSE` | **FACT** — `LICENSE` is the Apache License 2.0; `pyproject.toml` has `license = "Apache-2.0"` |
| Pre-relicensing contributions stay MIT (`LICENSE-MIT`), `NOTICE` exists | **FACT** — `NOTICE` says so verbatim; `LICENSE-MIT` is "Copyright (c) 2026 Safi Shamsi" |
| Pipeline detect → extract → build → cluster → analyze → report → export | **FACT** — `ARCHITECTURE.md` lines 5–11 |
| Extraction validated against a schema before the graph is built | **FACT** — `ARCHITECTURE.md` ("`validate.py` enforces this schema before `build()` consumes it"); `validate.py` read |
| All external input goes through one security module | **FACT** — `ARCHITECTURE.md` "Security" section lists `security.py` entry points |
| Tests: one file per module, no network | **FACT (stated)** — `ARCHITECTURE.md` "Testing" says so; I did not audit the suite for compliance |
| Node model `id/label/source_file/source_location` | **FACT (stated)** — in the `ARCHITECTURE.md` schema. **Note:** `validate.py` requires `id, label, file_type, source_file` and does **not** require `source_location` |
| Edges `EXTRACTED/INFERRED/AMBIGUOUS`, INFERRED has 0–1 score | **FACT** — `how-it-works.md`, `validate.py` (`VALID_CONFIDENCES`) |
| Outputs `graph.json`, `graph.html`, `GRAPH_REPORT.md`; `query/path/explain` | **FACT (stated)** — `how-it-works.md`, `serve.py` has `_query_graph_text` and `_shortest_path_text`. `explain` body not read |
| Graph in NetworkX, communities by Leiden | **FACT** — `pyproject.toml` (`networkx>=3.4`), `cluster.py` docstring ("Run Leiden community detection") |
| Naming request for derived projects | **FACT** — `README.md:468`: projects using "graphify" in their name should say in their README that they are community-built and not affiliated with or endorsed by Graphify Labs; the name and logo are marks of Graphify Labs, do not imply official status |
| PyPI package is `graphifyy` | **FACT** — `README.md:188`, `pyproject.toml` `name = "graphifyy"`, version `0.9.85` |
| `graphify install` writes skill/config/hook into assistants; `graphify hook install` installs a git hook | **FACT (stated)** — `README.md` lists `graphify install`; I did not run it and will not. Nothing of that kind is done by PromptGraphify |

## The task's UNKNOWNs — what I found

| Question | Finding |
|---|---|
| How node IDs are made | **FACT** — `graphify/ids.py`: `normalize_id` iterates `casefold` + NFKC to a fixpoint, replaces runs of non-word characters with `_`, collapses `__`, strips `_`. `make_id(*parts)` joins parts with `_` then normalizes. IDs derive from names/paths, not from offsets. The module docstring documents bug classes (Unicode collapse, same-filename collisions) that came from drifting copies of the recipe — the lesson: **one** ID module |
| What `graph.html` is drawn with | **FACT** — vis-network `9.1.6`, loaded from `https://unpkg.com/vis-network@9.1.6/standalone/umd/vis-network.min.js` (`exporters/html.py:636`). So the reference's `graph.html` is **not** serverless/offline |
| `query` internals | **FACT (partial)** — `_score_nodes`/`_score_query` rank nodes against query terms; `_bfs` expands from seed nodes to a depth and does **not** expand through nodes whose degree ≥ max(50, p99 of degrees), except seeds. Seed picking (`_pick_seeds`) not read |
| `path` internals | **FACT** — `nx.shortest_path` on a directed view by default (undirected on request), `max_hops` default 8, resolves both endpoints by score, warns if the top two scores are within 10 %, refuses when both resolve to the same node, reports the stored relation(s) per hop |
| `explain` internals | **UNKNOWN** — not read. The docstring of `_score_nodes` says `explain` shares the scorer |
| Cache invalidation | **FACT** — `cache.file_hash`: SHA-256 of file content + path relative to root, with a stat fast path (size + mtime_ns); for `.md` only the body below YAML front matter is hashed; semantic cache additionally keyed by a prompt fingerprint (`prompt_fingerprint`) |
| Atomic writes | **FACT** — `paths.write_text_atomic`, `write_json_atomic`, `write_text_atomic_if_changed` (compares decoded text, skips the rename when unchanged). `_atomic_replace` internals not read |
| Label sanitization | **FACT** — `sanitize_label` strips control characters and truncates to `_MAX_LABEL_LEN = 256`; the docstring says HTML injection additionally needs `html.escape()` |
| Path confinement | **FACT** — `validate_graph_path` resolves the path and requires it to be inside the `graphify-out` base directory, which must already exist |
| Community detection details | **UNKNOWN** beyond the docstring: splitting rule for communities larger than 25 % of nodes (min 10), AMBIGUOUS edge weight scale 0.5. `_native_leiden`/`_partition` not read |
| Test fixture layout | **FACT (partial)** — `tests/` holds ~370 entries, mostly `test_<topic>.py`; `tests/fixtures/` mixes source samples per language and a few small directories. `tests/test_validate.py` has small direct unit tests (`test_valid_passes`, `test_invalid_confidence`, `test_dangling_edge_source`, …). Fixture→expected-output relationship not studied |

## Concept map: taken / changed / not taken

| Reference concept | Decision for PromptGraphify |
|---|---|
| Staged pipeline with one module per stage | **Taken**, specialised: `scan → parse (Layer A) → [semantic (Layer B)] → build IR → validate (Layer C) → analyze → export` |
| Validate extraction before building the graph | **Taken** as Layer C. Stricter: provenance verification (`source[start:end] == original_text`), relation endpoint-type table, `EXTRACTED` requires an explicit reference |
| `EXTRACTED / INFERRED / AMBIGUOUS` | **Taken, tightened.** Reference: EXTRACTED is "stated in the source" with score 1.0. Here an EXTRACTED edge must additionally carry an evidence span that contains the reference; INFERRED must name its rule/method and have confidence < 1 |
| INFERRED confidence rubric 0.95/0.85/0.75/0.65/0.55 (`how-it-works.md`) | **Not adopted for deterministic rules** (each named rule gets its own documented constant). May be reused for Layer B LLM edges — decide in M5 |
| One security module for all external input | **Taken** as `security.py` (path confinement incl. symlinks, label sanitization, size limits) |
| `sanitize_label` + `html.escape` for HTML | **Taken in spirit**; tested with `<script>` payload labels in UI and `graph.html` |
| Atomic file writes | **Taken** (own implementation: temp file + `os.replace`) |
| `graph.json` with `schema_version` + tool version | **Taken**; own schema, rejects mismatching `schema_version` with a readable error |
| `query` / `path` / `explain` over `graph.json` | **Changed.** Queries are named, parameterised, deterministic. Name ambiguity **lists candidates and stops** instead of guessing by score (reference ranks and warns). `path` follows stored direction by default, never invents a relation, reports `no path` honestly |
| Hub-aware BFS (skip transit through high-degree nodes) | **Not adopted** — would hide real dependencies in prompt graphs, which are small |
| Leiden community detection, god nodes, cohesion, surprising connections | **Not adopted** — not required by the task; "most-connected" is answered by a documented degree metric |
| Tree-sitter extractors, 25 languages, SQL, video/audio, PDF, MCP server, Obsidian/wiki/Neo4j exporters | **Not adopted** — out of scope |
| SHA-256 content-hash cache with stat fast path | **Not adopted for v1.0.** Analysis is fast and deterministic; the stored result is keyed by `sha256(input + config + analyzer version)` (used as graph ID). Revisit if directories grow |
| `graph.html` via vis-network from a CDN | **Not adopted.** `graph.html` here is a single self-contained file with no CDN (decided in M4, see `DECISIONS.md`) |
| `install` / hook installers that write assistant config and git hooks | **Not adopted and never run** (task constraint 8) |

## Licensing consequence

Independent implementation, no reference source copied → no attribution obligation under Apache-2.0 §4
or MIT. PromptGraphify is licensed MIT. The README states that PromptGraphify is community-built and
not affiliated with or endorsed by Graphify Labs (per `README.md:468` of the reference), and does not
use its logo. If code is ever taken from the reference, first re-read `LICENSE`, `LICENSE-MIT` and
`NOTICE` and add the attribution they require.

## Not verified

- Behaviour of any reference code at runtime (nothing was executed).
- Whether `tests/` in the reference really avoid the network (stated in `ARCHITECTURE.md`; not audited).
- `explain`, Leiden internals, `_pick_seeds`, exporter internals other than the library/CDN lines.
