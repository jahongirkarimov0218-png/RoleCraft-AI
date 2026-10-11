# Performance (measured)

All numbers were measured in this sandbox: **4 CPUs, Python 3.13.16, Linux 6.18, headless Chromium (software
rendering)**. They are one machine's numbers, not guarantees; scripts and thresholds are in the repository so they
can be re-measured: `python -m tests.measure_perf` (backend) and `npx playwright test e2e/perf.spec.ts` (UI).
The input is a deterministic synthetic prompt (`tests/synthetic.py`, mirrored in `web/e2e/synthetic.ts`): plain
prompt text with identity, six tool definitions, sections of eight dependent numbered steps, constraints, and an
example block every third section. Every node and edge comes from the real analysis.

## Analysis (backend), best of 3, seconds

| prompt units | chars | nodes | edges | DAG vertices | analyze | validate | graph.json | graph.html | report | svg | graphml | graph.json size |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 60 | 3,783 | 75 | 200 | 60 | 0.041 | 0.001 | 0.003 | 0.008 | 0.001 | 0.003 | 0.014 | 0.31 MB |
| **150** | 8,797 | **177** | 500 | 141 | **0.092** | 0.002 | 0.008 | 0.020 | 0.002 | 0.006 | 0.038 | 0.76 MB |
| 300 | 17,152 | 347 | 1,000 | 276 | 0.220 | 0.005 | 0.016 | 0.043 | 0.004 | 0.015 | 0.084 | 1.51 MB |
| 600 | 33,310 | 675 | 1,966 | 537 | 0.344 | 0.010 | 0.038 | 0.079 | 0.009 | 0.027 | 0.149 | 3.16 MB |
| 1,200 | 65,709 | 1,333 | 3,900 | 1,059 | 0.837 | 0.027 | 0.071 | 0.181 | 0.016 | 0.054 | 0.321 | 6.18 MB |

Near the 500,000-character input limit: 14,500 sentences on one line (511k chars) → 5.3 s; a structured prompt of 488k
chars with 9,878 nodes → 12.5 s (the API timeout is 30 s).

### What the measurement found and fixed

The first synthetic prompt failed validation (duplicate diagnostic ids, `tool.undefined` once per mention) and Markdown
`### tool_name` headings were not recognised as tool definitions (documented in the spec, not implemented): both fixed.
Profiling then showed three accidentally quadratic paths:

| path | before | after |
|---|---|---|
| line splitting rescanned the whole file for every unit | 600 units 1.97 s, 1,200 units 6.60 s | 0.34 s, 0.84 s |
| sentence-boundary regex rescanned the whole line for every period | 3,000 sentences on one line 9.6 s | 0.84 s |
| conflict search compared every pair of units | ~0.4 s of 2.8 s at 600 units | only opposite-polarity pairs |

Each replacement has a differential test against the code it replaced (`tests/test_pipeline_properties.py`), the
evaluation results are byte-identical before and after, and `tests/test_scale.py` guards against the regression with a
loose ratio check (4x input must not take more than 10x time).

## User interface (Playwright, real backend, production build)

| | 177 nodes (150 units) | 675 nodes (600 units) |
|---|---|---|
| response size of `POST /api/analyze` | 523 KB | 2,177 KB |
| click Analyze → response received | 0.19 s | 0.62 s |
| click Analyze → graph visible | 0.81 s | 3.3 s |
| nodes in the DOM (only visible ones are rendered above 60) | 177 | 370 |
| click a node → inspector shown | 0.41 s | 0.55 s |
| type 7 characters into search | 0.27 s | 0.65 s |
| search applied to the graph (dimming) | 0.38 s | 1.06 s |
| zoom, 60 animation frames: average / worst | 16.5 / 16.8 ms | 17.3 / 33.4 ms |
| pan, 60 animation frames: average / 95th percentile | 22.9 / 66.7 ms | 45.4 / 216.6 ms |
| Fit view | 0.14 s | 0.38 s |
| switch to the Execution DAG tab | 0.52 s | 1.63 s |

Headless Chromium paints in software, so frame times are pessimistic compared with a GPU browser. Panning a 675-node
graph is visibly less smooth than panning 177 nodes (95th percentile 217 ms); that is a known limitation, see below.

### What the measurement found and fixed

* **Fit view did not fit** a 177-node graph: the layout is taller than the screen and the zoom was clamped at 0.1, so
  nodes ended up under the filter bar. The minimum zoom is now 0.02.
* **Typing in the search box rebuilt the graph layout on every keystroke.** The view arrays depended on the whole
  filter object, so each key re-ran the dagre layout. Seven keystrokes took 1.55 s at 177 nodes and 11.3 s at 675
  nodes; now 0.27 s and 0.65 s. Search only dims nodes, so only the type/status sets decide which nodes exist.

## Known limits

* Analysis of very large inputs is superlinear (roughly n^1.3 on these prompts); at the 500k-character limit it takes
  5–13 s.
* Graph layout and rendering above ~600 nodes are slow to open (3.3 s) and pan unevenly; the minimap and node list are
  the intended way to move around a graph that size. Layout runs on the main thread (no web worker).
* Timings of the optional LLM layer depend on the provider and are not measured here (no provider in this sandbox).
