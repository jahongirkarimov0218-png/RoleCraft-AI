# PromptGraphify

A local, open-source **static analyzer and graph visualizer for LLM prompts**. Give it a prompt (text, Markdown,
XML-tagged, YAML or JSON; one file or a directory) and it returns:

* a **knowledge graph** of what the prompt contains: 6 node types (`SystemNode`, `TaskNode`, `ContextNode`,
  `ConstraintNode`, `ToolNode`, `ExampleNode`) joined by 11 relations (`DEPENDS_ON`, `CONSTRAINS`, `PROVIDES_CONTEXT`,
  `CALLS_TOOL`, `PRODUCES`, `REFERENCES`, `OVERRIDES`, `CONFLICTS_WITH`, `PRECEDES`, `EXEMPLIFIES`,
  `CONDITIONALLY_EXECUTES`);
* an **execution DAG** with topological order, critical path, unresolved dependencies and cycles;
* **diagnostics** (21 rules: undeclared variables, circular steps, undefined tools, conflicting constraints,
  injection phrases in data blocks, ...), each with the exact source text that triggered it;
* exports: `graph.json`, a self-contained `graph.html`, `GRAPH_REPORT.md`, Mermaid, GraphML and SVG.

Every node and edge points back to character offsets in your source text, and every edge says whether it was read
from an explicit reference (`EXTRACTED`) or inferred (`INFERRED`/`AMBIGUOUS`). Nothing is guessed silently: text the
analyzer does not understand is reported as *uncovered*, not turned into a node.

The analysis is deterministic and needs **no network and no API key**. An optional LLM layer exists and is **off by
default** (see [Optional LLM layer](#optional-llm-layer)).

> **Community-built.** PromptGraphify is an independent project. It is not affiliated with or endorsed by Graphify
> Labs, and it does not use their logo or marks. It was inspired by the architecture of
> [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) (see `docs/REFERENCE_NOTES.md`); no code was
> copied.

Prompts you analyse are treated as **data**: they are parsed, never executed, and instructions inside them are never
obeyed.

## Requirements

| Tool | Version | Needed for |
|------|---------|------------|
| Python | 3.12 or newer | the analyzer, CLI and API |
| [uv](https://docs.astral.sh/uv/) | any recent version | recommended installer (`pip` works too, see below) |
| Node.js | 20.9 or newer (developed and tested with 22) | the web UI only |

The UI tests also need a Chromium that Playwright can find (`npx playwright install chromium`); running the UI
does not.

## Install and run

```bash
git clone <repository-url>
cd <repository>/promptgraphify        # the folder that holds pyproject.toml, web/ and Dockerfile

uv sync                       # creates .venv and installs the locked dependencies
```

Without uv: `python3 -m venv .venv && . .venv/bin/activate && pip install .` (the `promptgraphify` command is then on your path;
below, drop the `uv run` prefix).

### Web UI

Two processes: the API on port 8000 and the UI on port 3000.

```bash
# terminal 1: API
uv run promptgraphify serve                   # http://127.0.0.1:8000  (docs at /docs)

# terminal 2: UI
cd web
npm ci
npm run build
npm run start                                 # http://localhost:3000
```

Open <http://localhost:3000>, type or paste a prompt into the editor (**Load example** fills in a sample; **+** adds
more files, each its own tab), and press **Analyze Prompt** (Ctrl/Cmd+Enter). The UI proxies `/api/*` to the
API on `127.0.0.1:8000`. If your API runs elsewhere, set `PROMPTGRAPHIFY_API_URL` **before `npm run build`**: Next.js
bakes the rewrite into the build.

You can pan, zoom and drag the knowledge graph, search and filter nodes, highlight a node's neighbours, and open the
inspector. Selecting a node highlights its exact span in the editor; selecting an edge shows the rationale and the
evidence text. The second tab shows the execution DAG (topological order, critical path, unresolved dependencies,
cycles). **Export** downloads any of the formats below.

For development (hot reload): `npm run dev` in `web/` instead of `build` + `start`.

### Command line

```bash
# analyse a file or a directory; writes graph.json, graph.html, GRAPH_REPORT.md (default) to ./promptgraphify-out
uv run promptgraphify analyze path/to/prompt.md
uv run promptgraphify analyze prompts/ --out out --format all        # + mermaid, graphml, svg
uv run promptgraphify analyze prompt.md --fail-on error              # exit 1 if an error-level diagnostic exists

uv run promptgraphify validate prompt.md                             # list diagnostics; exit 1 on errors
uv run promptgraphify validate --graph out/graph.json                # check a graph.json against the invariants
uv run promptgraphify explain invoice_text prompt.md                 # one node, all its edges and their evidence
uv run promptgraphify path "Compare the order total" invoice_text prompt.md   # shortest directed path (--undirected to ignore direction)
uv run promptgraphify query --list                                   # the 8 named queries
uv run promptgraphify query execution_bottleneck prompt.md
uv run promptgraphify diff old_prompt.md new_prompt.md               # six kinds of change; exit 1 if different
uv run promptgraphify openapi > openapi.json                         # the OpenAPI document of the API
```

Most commands take `--json` for machine-readable output and `--graph FILE` to reuse an existing `graph.json`.

Exit codes: `0` ok · `1` findings or differences · `2` usage or input error (unreadable, oversized, unsafe path) ·
`3` not resolved (name matched nothing or several things, no path) · `4` unsupported or invalid graph file ·
`5` internal error.

Input limits (override with flags): 200 files, 1,000,000 bytes per file, 500,000 characters in total. Files must be
valid UTF-8 without NUL bytes. Symlinks found inside a directory are skipped; only regular files are read.

### HTTP API

`promptgraphify serve` (default `127.0.0.1:8000`; **no authentication**, so keep it on a local or trusted network):

| Method and path | Purpose |
|-----------------|---------|
| `POST /api/analyze` | analyse files, store and return the graph |
| `POST /api/validate` | schema invariants plus analyzer diagnostics |
| `POST /api/diff` | compare two prompt versions |
| `GET /api/graph/{id}` | a stored graph |
| `GET /api/graph/{id}/node/{node_id}` | one node with its edges and diagnostics |
| `GET /api/graph/{id}/path?source=&target=` | shortest path |
| `GET /api/graph/{id}/query/{name}` | a named query |
| `GET /api/graph/{id}/export/{fmt}` | `json`, `html`, `report`, `mermaid`, `graphml`, `svg` |
| `GET /api/queries`, `GET /api/health` | list queries, health |

Interactive documentation is served at `/docs`; the machine-readable contract is `promptgraphify openapi`. Graphs are
stored in a SQLite file (`PROMPTGRAPHIFY_DB`, default `./promptgraphify-out/graphs.sqlite3`).

### Docker

```bash
docker compose up --build        # UI on http://localhost:3000 (bound to 127.0.0.1); the API is not published to the host
```

The two images (`--target api`, `--target web` in the `Dockerfile`) were built and run in the development sandbox. The
compose file's own `up` was **not** run there (no bridge network available): see `docs/STATUS.md`. If your network
inserts its own TLS certificate, the in-image `pip install` / `npm ci` steps need that CA; this is a property of your
network, not of the project.

## Optional LLM layer

The deterministic analysis covers what it can prove from the text. A second, optional layer ("Layer B") can propose
extra nodes and edges for text the rules left uncovered (for example contradictions phrased differently). It is **off
unless you configure it** and **a request asks for it** (`analyze --llm`, or the "Use LLM layer" switch in the UI).

* **Your prompt text is sent to the endpoint you configure.** Use a local server (Ollama, LM Studio) if that matters.
* The model proposes *quotes*, never offsets or statuses. A proposal is kept only if its quote occurs exactly once in
  text the rules did not cover, its node type and relation are in the closed ontology, and its endpoints are allowed by
  the relation table. Kept items are marked `llm:...`, never `EXTRACTED`, and carry confidence below 1. Anything else is
  dropped and listed in `warnings`.
* On any failure (timeout, bad JSON, HTTP error) you get the deterministic result plus a warning.
* The key is read from the environment only, masked in logs, and never written to `graph.json`.

```bash
export PROMPTGRAPHIFY_LLM_PROVIDER=openai-compatible
export PROMPTGRAPHIFY_LLM_MODEL=<model name>
export PROMPTGRAPHIFY_LLM_BASE_URL=https://api.openai.com/v1      # any OpenAI-compatible /chat/completions
export PROMPTGRAPHIFY_LLM_API_KEY=<key>                            # not needed for most local servers
uv run promptgraphify analyze prompt.md --llm
```

The layer is tested against a fake local provider. Its precision and recall against real models were **not measured**
(no provider was available); see `eval/README.md`. All variables are in `.env.example`.

## Limits and honesty notes

* This is a **static, rule-based** reader of prompt structure, not an understanding of meaning. It will miss implied
  dependencies and paraphrased contradictions; it will not invent them. The full list of known limits is in
  `docs/STATUS.md`; each diagnostic rule's false-positive and false-negative notes are in `docs/RULES.md`.
* Extraction was measured on a small, hand-labelled dataset written by the same author as the analyzer
  (`eval/`, labels `unreviewed`). The scores are agreement with that annotator, not accuracy. English is the best
  covered language; Russian and Uzbek are supported with thinner vocabulary.
* Large graphs (more than about 600 nodes) open in seconds and pan unevenly. Numbers: `docs/PERFORMANCE.md`.
* Accessibility is checked with axe and keyboard tests only, not with a screen reader.

## Security notes

* Input is never executed. Labels and texts are rendered as text (no `innerHTML`); the exported `graph.html` has a
  Content-Security-Policy that blocks all network access and any script but its own.
* The CLI reads only regular files: symlinks found inside a directory are skipped, a symlink you name yourself must
  resolve inside its own directory, and oversized, NUL-containing or non-UTF-8 files are rejected with a clear error
  (exit 2).
* The API enforces a request-size limit, an input-size limit and a time limit (`.env.example`).
* The API has no authentication by design (local tool). Do not expose it to an untrusted network.

## Development

```bash
uv run pytest -q                                   # backend tests
uv run ruff check src tests && uv run ruff format --check src tests
cd web && npx tsc --noEmit && npx vitest run       # UI unit tests
cd web && npx playwright install chromium && npx playwright test    # end-to-end tests (builds and starts both servers)
scripts/ci-local.sh                                # the steps of the CI workflow, in order
uv run python -m promptgraphify.evalkit --split dev       # extraction evaluation (eval/README.md)
uv run python -m tests.measure_perf                       # backend timings (docs/PERFORMANCE.md)
```

The end-to-end tests start their own servers (API on 8000, UI on 3100, a fake LLM provider on 8002), so stop a running
`promptgraphify serve` first. They expect the virtual environment that `uv sync` creates (`PG_PYTHON` points at another
interpreter) and use Playwright's Chromium (`PG_CHROMIUM` names a different binary).

If you change the API, regenerate the typed client: `uv run promptgraphify openapi > web/openapi.json && cd web && npm run gen:api`.

### Layout

```
src/promptgraphify/   analyzer library (markup, classify, relations, dag, analyzer, queries, diff, exporters/, llm, layer_b, ...)
  api/                FastAPI app, schemas, OpenAPI builder
  cli.py              the command line
  signals/            signal words per language (en, ru, uz) as data
tests/                pytest suite and tests/fixtures/ (15 annotated prompts)
web/                  Next.js + React Flow UI, unit tests, Playwright end-to-end tests (web/e2e)
eval/                 hand-labelled dataset, harness results
docs/                 ANALYSIS_SPEC, RULES, DECISIONS, STATUS, PERFORMANCE, REFERENCE_NOTES
Dockerfile, docker-compose.yml, scripts/ci-local.sh
../.github/workflows/promptgraphify-ci.yml   CI (at the repository root; every step runs in promptgraphify/)
```

Documents worth reading first: `docs/ANALYSIS_SPEC.md` (what counts as a node, an edge, a span), `docs/DECISIONS.md`
(why), `docs/STATUS.md` (what is verified and what is not).

## License

MIT. See `LICENSE`.
