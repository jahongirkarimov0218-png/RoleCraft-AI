# Analysis specification (v1.0)

This is the contract the deterministic layer (Layer A), validation (Layer C) and the fixtures'
hand-written expectations are written against. If a parser disagrees with a fixture, one of the two
is wrong — decide by this document, not by copying the parser's output.

Labels: **[D]** deterministic rule, **[H]** heuristic rule (signal words / patterns), **[LLM]** only with
the optional Layer B. Signal words live in `src/promptgraphify/signals/{en,ru,uz}.json`, never in code.

## 1. Text, offsets, spans

- Source text is decoded as UTF-8 and never normalised: CRLF stays two code points, a leading BOM
  (U+FEFF) stays at index 0, emoji are one code point. Parsers skip the BOM, they do not remove it.
- Offsets are Unicode **code points** (`str` indices), half-open `[start, end)` (decision D-003).
- `original_text == source[start:end]` for every node and every evidence item (Layer C invariant).
- A node whose exact text cannot be recovered (e.g. text inside an escaped JSON string) takes the
  smallest enclosing span and sets `metadata.span_precision = "enclosing"`; otherwise `"exact"`.
  The decoded view (escapes opened, indentation stripped) goes into `decoded_text`, never into
  `original_text`.
- A node's span never includes list markers (`-`, `*`, `•`, `1.`, `2)`), heading hashes, or XML
  delimiters. It starts at the first and ends at the last non-whitespace code point of the unit.

## 2. Units (granularity)

A node is the smallest independently checkable unit. Containers (sections, tags, agents, messages,
YAML/JSON keys) are **not** nodes; they live in `metadata.section_path` and `role_scope`.

| Source shape | Unit |
|---|---|
| Markdown bullet / numbered item | one unit per item; nested items are separate units |
| Lead-in line ending with `:` before a list | structural (container label), copied into children as `metadata.lead_in` |
| Prose paragraph | one unit per sentence (abbreviations, decimals, `e.g.`, ellipses and list numbers do not end a sentence) |
| Heading line | structural |
| Tool definition (JSON/YAML/XML/Markdown signature) | one ToolNode per tool, span = the whole definition |
| Example block (`<example>…</example>`, `Example:` + body, fenced example) | one ExampleNode per block, span = body of the block; inner user/assistant turns are not separate nodes |
| Variable | one ContextNode per **root variable name** (`{{user.name}}` → `user`), see §4 |
| Context block (`<context>`, `<documents>`, `Context:` section, user-data block) | one ContextNode per block |
| YAML/JSON prompt | the string value is parsed with the same rules as prose/Markdown; the key path goes to `metadata.section_path` |

Coverage per source file: every non-whitespace code point is exactly one of
**covered** (inside a node), **structural** (recognised syntax: headings, tags, markers, fences,
keys, separators) or **uncovered** (prose the deterministic layer did not turn into a node).
`covered + structural + uncovered = all non-whitespace code points`. Uncovered spans are reported.

## 3. Node type decision (Layer A)

Applied top to bottom; the first match wins; `confidence` is the rule's documented constant.

1. Inside a tool definition → **ToolNode**. [D] (JSON `name`+`parameters`/`input_schema`, YAML `tools:`,
   XML `<tool>`, Markdown `### tool_name` under a tools heading, `name(arg, …)` signature lists)
2. Inside an example container or after an example marker (`Example:`, `Пример:`, `Misol:`,
   `<example>`) → **ExampleNode**. [D]
3. Variable declaration (`variables:` / `<variables>` / `Inputs:` list item `- name: description`) →
   **ContextNode** (declared). [D]
4. Context / data container (`<context>`, `<document(s)>`, `<user_input>`, heading `Context`,
   `Контекст`, `Kontekst`, `Retrieved documents`) → **ContextNode**. [D]
5. Sentence-level, by signals [H]; first match wins:
   a. identity / role / hierarchy (`You are …`, `Act as`, `Your role is`, `Sen … san`, `Ты — …`,
      "takes precedence over") → **SystemNode**
   b. prohibition signal (`never`, `do not`, `must not`, `нельзя`, `никогда не`, `hech qachon`,
      `mumkin emas`, `-ma` imperative with `hech`) → **ConstraintNode** (a prohibition beats any verb)
   c. an imperative from the **task-verb list** that is also in the **strict** subset (`extract`,
      `summarize`, `classify`, `translate`, `compare`, `check`, `verify`, `search`, `collect`, `split`,
      `send`, `pass`, `escalate`, `fetch`, `review`, `draft`, `greet`, `list`, `repeat`, …) →
      **TaskNode**; limit/format words in the same sentence are kept in `metadata.embedded_signals`
   d. limit (`at most`, `no more than`, `under N words`, `only`, `не более`, `только`, `faqat`,
      `ko'pi bilan`), format/style/safety (`tone`, `format`, `JSON`, `markdown`, `bullet`, `concise`,
      `brief`, language names, `confidential`) → **ConstraintNode**
   e. any other imperative / obligation with a task verb (`answer`, `reply`, `write`, `use`, `follow`,
      `provide`, `javob ber`, `ответь`, …) → **TaskNode**
   f. none of the above → not a node; the sentence is **uncovered** and reported as such.
   (Strict verbs describe *what to do*; response verbs describe *how to answer*, so
   "Reply in a polite tone." is a constraint but "Answer the question using the knowledge base." is a
   task. Mixed sentences are not split in v1; they get `metadata.mixed = true` and confidence 0.6.)
6. A unit that contains an explicit condition (`if`, `when`, `unless`, `если`, `agar`) keeps its type
   and gets `metadata.condition` = the condition clause. A unit with a loop marker (`repeat`,
   `keep … -ing`, `until`, `повторяй`, `takrorla`) gets `metadata.loop = {"stop_condition": text|null}`.
7. XML-like tags. A tag is **syntax** (structural, opens a container) only when it starts a line
   (indentation ignored) or forms a matched pair inside one unit (`<rule>…</rule>`). A tag in the
   middle of a sentence ("between the <document> tags") is **text** and stays inside the sentence.
   Unclosed tags are recovered to the end of their parent/line and reported as `parse.malformed`.
   Role containers (`<system>`, `<developer>`, `<user>`, `<assistant>`, headings `System`, JSON/YAML
   `role` keys) set `role_scope.role`; headings of the form `Agent: <name>` set `role_scope.agent`.

Node `confidence`: 1.0 for syntactic extraction (rules 1–4 with explicit syntax, variables,
declared tools); 0.8 for signal-based sentence classification with one unambiguous signal;
0.6 when the sentence is mixed or matched through a weak signal.
`validation_status`: `verified` after Layer C span verification, `downgraded` if a check lowered
the confidence, `unverified` only before Layer C.

## 4. Variables and templates

- Recognised placeholders: `{{ name }}` (spaces optional), `${name}`, and `{name}` **only** in prose
  outside code fences and outside JSON/YAML syntax. Dotted paths (`{{user.name}}`) and filters
  (`{{ name | upper }}`) resolve to the root name (`user`, `name`).
- `declared` = introduced by a declaration (rule 3 in §3), a YAML/JSON `variables`/`inputs` key, or
  assigned by a task (`save the result as {{x}}`, PRODUCES) — all three count as *defined* for
  `variable.undeclared`.
  A variable that is only used has a ContextNode with `metadata.declared = false`; its span is the
  first use. A declared one has the declaration as span and every use as an evidence span on its
  edges. `metadata.usage_spans` lists all uses.
- Nested or unbalanced templates (`{{ {{x}} }}`, `{{ x`) → diagnostic `template.malformed`; the inner
  well-formed placeholder is still extracted; the malformed outer one produces no node.

## 5. Edges

Direction and allowed types are the table in `src/promptgraphify/ontology.py` (checked by Layer C).
Status rules: **EXTRACTED** only if the edge carries `reference`, a literal text that occurs inside one
of its evidence spans (a name, a placeholder, a step marker). **INFERRED** needs a named `rule` and
`confidence < 1`. **AMBIGUOUS** is used for several plausible targets or an unresolved reference
(candidates in `metadata.candidates`).

| Relation | Deterministic rule (edge) | Status |
|---|---|---|
| DEPENDS_ON Task→Context | task text contains the variable's placeholder; `reference` = placeholder | EXTRACTED |
| DEPENDS_ON Task→Task | task text names another step (`step 2`, `шаг 2`, `2-qadam`, `result of <label>`); target missing → no edge, diagnostic `dependency.unresolved` | EXTRACTED |
| PRECEDES Task→Task | consecutive items of one numbered list; `reference` = the later item's marker (`2.`) | EXTRACTED |
| PRECEDES Task→Task | sequence word at the start of a unit (`then`, `затем`, `keyin`) linking it to the previous unit | INFERRED `sequence.word` 0.7 |
| PRECEDES (loop back) | text says to return to a named step (`go back to step 1`) → edge with `metadata.loop = true` | EXTRACTED |
| CALLS_TOOL Task→Tool | task text contains a defined tool's name token; `reference` = name | EXTRACTED |
| CALLS_TOOL Task→Tool (unresolved) | task text has a call signal + identifier but no definition; creates ToolNode with `metadata.defined = false` | AMBIGUOUS |
| CONSTRAINS Constraint→Task/Tool/Context/System | constraint text names the target (tool name, variable, step) | EXTRACTED |
| CONSTRAINS Constraint→Task | no name: constraint and task share the innermost section | INFERRED `scope.section` 0.8 |
| CONSTRAINS (global) | constraint outside any section / in system scope: **not materialised** as edges; queries add them with the label "global scope" | — |
| PROVIDES_CONTEXT Context→Task/Tool | task names the context block (tag name, heading, variable) | EXTRACTED |
| PROVIDES_CONTEXT Context→Task | context block and task share the innermost section | INFERRED `scope.section` 0.7 |
| PRODUCES Task→Context | task text assigns an output to a variable (`save as {{x}}`, `сохрани как`, `… sifatida saqlang`) | EXTRACTED |
| REFERENCES any→any | text names another node's label/section/tag (`see "Rules"`, `as in <policy>`) | EXTRACTED |
| OVERRIDES | text says it takes precedence over / replaces a **named** target | EXTRACTED |
| CONFLICTS_WITH (symmetric; source = earlier span) | same predicate with opposite polarity (`always X` / `never X`) | INFERRED `conflict.polarity` 0.7, or AMBIGUOUS on partial lexical overlap |
| EXEMPLIFIES Example→Task/Constraint/Tool | example block names its target (`<example for="…">`, `Example of rule 2`) | EXTRACTED |
| EXEMPLIFIES Example→Task/Constraint | nearest preceding **TaskNode** in the same container; only if no task precedes it, the nearest preceding constraint (D-022) | INFERRED `proximity.preceding` 0.55 |
| CONDITIONALLY_EXECUTES Context/Task→Task | the unit has an explicit condition (`if`, `когда`, `agar`); the condition mentions a variable (→ that Context) or a step (→ that Task); `metadata.condition` = the condition text; conditions that name nothing leave only `metadata.condition` on the node | EXTRACTED |

**Scope.** A constraint's *scope container* is its nearest ancestor container that is not a
*constraint group* (container names from the `constraint_groups` signal list: rules, constraints,
guidelines, safety, style rules, ограничения, правила, cheklovlar, qoidalar, `output`). If that scope is
the document root or a message-role container, the constraint is **global** (`metadata.scope =
"global"`); otherwise `scope.section` edges go to every TaskNode inside the scope container's subtree.
**Handoff.** `pass/send … to the <Agent|file>` where the name resolves to an `Agent:` section or an
input file → PRECEDES from that unit to the first TaskNode of the target, INFERRED `handoff.first_task`
0.75, evidence = the handoff unit and the target unit.
**Otherwise.** A unit starting with `otherwise`/`else`/`иначе`/`aks holda` directly after a conditional
unit gets CONDITIONALLY_EXECUTES from the same gate, INFERRED `condition.otherwise` 0.8,
`metadata.condition` = `not (<previous condition>)`.
**Most specific relation wins.** A mention that yields DEPENDS_ON / PROVIDES_CONTEXT / CALLS_TOOL /
CONSTRAINS / OVERRIDES does not also yield REFERENCES. REFERENCES is for a unit that names a
section/tag/rule of another unit (`Follow the "Safety" section`) when no stronger relation applies.
**Loops.** `repeat step N` / `go back to step N` → PRECEDES from the repeating unit to step N,
EXTRACTED, `metadata = {loop: true, stop_condition: <until-clause or null>}`. A loop marker inside one
unit without a step reference is only node metadata.

Self-loops are forbidden except `metadata.loop = true` (deliberate repetition) and
`metadata.self_reference = true` (a unit that depends on itself; always reported as `dependency.cycle`). Two nodes may have several relations;
the same (relation, source, target) with different evidence gets one edge per distinct evidence.

## 6. Execution DAG projection

Same analysis result, second view. Vertices: Task nodes, plus Tool and Context nodes that touch at
least one included edge. Included edges and the execution arrow (u → v = u finishes before v starts):

| Graph edge | DAG arrow |
|---|---|
| PRECEDES a→b | a → b |
| DEPENDS_ON a→b (a depends on b) | b → a (**reversed**) |
| CALLS_TOOL task→tool | task → tool |
| PRODUCES task→ctx | task → ctx |
| CONDITIONALLY_EXECUTES gate→task | gate → task, `conditional = true` |

Not projected: CONSTRAINS, PROVIDES_CONTEXT, REFERENCES, OVERRIDES, CONFLICTS_WITH, EXEMPLIFIES
(they carry no ordering). Loop-marked edges are excluded from cycle detection and listed separately.
A self-reference counts as a cycle of length 1. Cycle found → the DAG is **blocked**: the result lists the strongly connected components, the edges
and their evidence spans, plus an optional `acyclic_subgraph` (cycle edges with the lowest
confidence removed, every removal listed). Nothing is dropped silently.

Metrics (always shipped with their definition string): *topological order* — Kahn, always taking the
ready vertex with the smallest (source offset, id); *critical path* — longest path by vertex count (unit weight) = longest chain of
prerequisites, **not** time; among equal-length paths the one whose vertex offsets are
lexicographically smallest; *bottleneck* — vertex with the largest share of all source-to-sink paths
passing through it (path-dominance), reported only if the share is > 0.5, the graph has ≥ 3 vertices and is not a single chain;
*most dependencies* — vertex with most ancestors in the DAG (transitive prerequisites) and, separately,
most direct DEPENDS_ON edges.

## 7. Diagnostics

Fields: `rule_id`, `severity` (error/warning/info), `certainty` (**proven** = follows from the
graph/source; **probable** = heuristic or LLM), `detection` (deterministic/heuristic/llm),
`description`, `evidence[]`, `affected_nodes[]`, `affected_edges[]`, `suggested_fix`.
A semantic finding (conflict, ambiguity, injection) is never `proven`.

| rule_id | Meaning | Detection | Certainty |
|---|---|---|---|
| `input.empty` | no non-whitespace text | D | proven |
| `parse.malformed` | broken syntax (unclosed XML tag, invalid YAML/JSON) | D | proven |
| `template.malformed` | nested / unbalanced placeholder | D | proven |
| `variable.undeclared` | used, never declared in the analysed input | D | proven |
| `variable.unused` | declared, never used | D | proven |
| `tool.undefined` | call-like reference to a tool with no definition | H | probable |
| `tool.unused` | defined, never referenced | D | proven |
| `tool.permission_mismatch` | a constraint forbids a tool that a task calls | H | probable |
| `dependency.cycle` | cycle in the projected DAG | D | proven (probable if an INFERRED edge is on the cycle) |
| `dependency.unresolved` | names a step/node that does not exist | D | proven |
| `task.unreachable` | task whose every prerequisite chain sits inside a cycle or an unresolved dependency | D | proven |
| `node.orphan` | Context, Tool or Example node with no edge, or a non-global Constraint with no edge (Task, System and global-scope Constraint nodes are never orphans) | D | proven |
| `instruction.duplicate` | same normalised text twice (exact) | D | proven |
| `constraint.conflict` | contradictory instructions | H | probable |
| `role.conflict` | two different identities in one scope | H | probable |
| `instruction.ambiguous` | vague wording without measurable criterion | H | probable |
| `output.contract_missing` | no formatting/output-specification constraint | H | probable |
| `success.criteria_unclear` | no success/acceptance wording | H | probable |
| `context.unavailable` | refers to context ("the attached file", "above") that no node supplies | H | probable |
| `injection.indicator` | override/exfiltration phrase, especially inside data blocks | H | probable |
| `loop.no_stop_condition` | repeat/loop wording without a stop clause | H | probable |

Rules that cannot be implemented reliably are listed as unfinished in `docs/STATUS.md`, not shipped.

## 8. Node IDs

`{code}:{path}:{key}`; `code` ∈ `sys task ctx con tool ex`; `path` = slugged section/agent path joined
with `.` (source file stem is prepended only when the analysis has more than one source file; the
single-input path is empty → `-`); `key` = slug of the name for variables/tools, or
`slug(first 4 words)-` + first 8 hex of SHA-256 over the normalised text (NFKC, casefold, whitespace
collapsed, list markers removed) for free-text units. Identical keys under one path get `~2`, `~3` in
document order. Slug = NFKC, casefold, runs of non-word chars → `-`, Unicode letters kept.
Edge IDs: `e_` + first 12 hex of SHA-256 over `relation|source|target|n` (n = ordinal among equal triples
by evidence offset).

## 9. Fixture expectation format

`tests/fixtures/<name>/` holds the input file(s) and `expected.json`:

```
topics[], language, review_status   metadata only
nodes[]       {key, type, quote, file?, occurrence?, role?, agent?, declared?, defined?, decoded?,
               id_suffix?, span_precision?}
edges[]       {relation, source, target, status, rule?, reference?, evidence: [quote | {quote, occurrence, file}],
               metadata?}          (source/target may be lists: all pairs are expanded)
diagnostics[] {rule_id, certainty, nodes: [key…]}      (non-exhaustive: listed ones must appear)
absent_types[]    node types that must not appear
absent_rules[]    diagnostic rules that must not fire
uncovered[]       quotes the analyzer must report as uncovered (this list is exact)
dag?              {status, topological_order?, critical_path?, cycle_nodes?, loops?}
bytes?            {bom, crlf, non_bmp}  — what the input file must really contain
```

`quote` is a literal substring of the input (the test resolves it to a span; a quote that is missing or
ambiguous without `occurrence` makes the fixture invalid). **Nodes and edges are exact sets:** any extra
node or edge is a failure.
