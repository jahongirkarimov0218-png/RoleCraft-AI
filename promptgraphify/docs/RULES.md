# Analyzer rules: method, certainty and known limits

Every diagnostic carries `rule_id`, `severity`, `certainty`, `detection`, `evidence` (exact source spans),
`affected_nodes`, `affected_edges` and `suggested_fix`. **Proven** means the finding follows from the source or the graph;
**probable** means a heuristic produced it. A semantic finding (conflict, ambiguity, injection) is never proven. At most
200 diagnostics per rule are listed; a cut is reported in the document's `warnings`.

The table is checked against `src/promptgraphify/rules.py` by `tests/test_rules_doc.py`; each implemented rule has at least
one positive and one negative test in `tests/test_analyzer_rules.py`.

| Rule | Severity | Detection / certainty | How it is found | Known limits |
|---|---|---|---|---|
| `input.empty` | error | deterministic / proven | every input file is whitespace, a BOM or zero-width marks | none |
| `parse.malformed` | warning | deterministic / proven | the scanners recorded an unclosed tag or fence, a stray close tag, a bracket or YAML/JSON syntax problem | spans after a recovered error may be the enclosing block (`metadata.span_precision = "enclosing"`) |
| `template.malformed` | warning | deterministic / proven | nested (`{{ {{x}} }}`) or unbalanced (`{{x`) placeholders | evidence is capped at 120 characters |
| `variable.undeclared` | warning | deterministic / proven | a placeholder is used and no declaration, YAML/JSON `variables` key, or "save as {{x}}" produces it in the analysed input | a variable supplied by the caller at run time looks undeclared (that is the point, but it is a warning, not an error) |
| `variable.unused` | info | deterministic / proven | a declared variable has no use | uses inside code fences are not counted |
| `tool.undefined` | warning | heuristic / probable | a task names an identifier-shaped tool ("use the `x_y` tool", "call x_y", Russian/Uzbek equivalents) that no definition provides; one diagnostic per tool | only identifier-shaped names (snake_case, camelCase, dotted, backticked) are recognised; a prose tool name ("the calculator") is not |
| `tool.unused` | info | deterministic / proven | a defined tool is never referenced by a task or constraint | a tool called only from another file is referenced if that file is analysed in the same run |
| `tool.permission_mismatch` | error | heuristic / probable | a prohibition constraint names a tool that a task calls | needs the constraint to name the tool; "never call external services" is not matched to a tool |
| `dependency.cycle` | error | deterministic / proven (probable if an INFERRED edge is on the cycle) | a strongly connected component of the execution DAG; the evidence is the union of the edges' spans | deliberate loops (`repeat step 1`) are modelled separately and are not cycles |
| `dependency.unresolved` | error | deterministic / proven | "step N" / "шаг N" / "N-qadam" with no such step | a reference without a number ("the result of the previous task") is neither resolved nor reported |
| `task.unreachable` | warning | deterministic / proven | tasks Kahn's algorithm never schedules because they lie on or behind a cycle or an unresolved dependency | a conditional edge counts as a dependency, so a cycle through one is a cycle |
| `node.orphan` | info | deterministic / proven | a Context, Tool or Example node (or a non-global Constraint) with no edge | system and task nodes are never orphans by design |
| `instruction.duplicate` | info | deterministic / proven | the same type and the same normalised text twice (Unicode NFKC, case, list marker and spacing are folded) | punctuation is **not** folded ("Be brief." and "be  brief!" differ) and near-duplicates ("Keep it short.") are not found |
| `constraint.conflict` | warning | heuristic / probable | a `CONFLICTS_WITH` edge: same wording with opposite polarity (`always` / `never`), or at least 60 % token overlap | **needs near-identical wording**: "Always answer in formal English" vs "Never use formal language" is missed (3 of 3 such pairs on the dev set). A looser rule would flag unrelated pairs |
| `role.conflict` | warning | heuristic / probable | two different identity statements ("You are ...") in one scope (file, role, agent) | identities are recognised by patterns ("You are ...", "Act as ...", "Your role is ..." and the Russian/Uzbek equivalents); other phrasings are not seen |
| `instruction.ambiguous` | info | heuristic / probable | a task or constraint with a vague word from the signal lists (good, appropriate, as needed, ...) and no digit | a word list per language; irony, domain terms and vague words outside the list are not found |
| `output.contract_missing` | info | heuristic / probable | there is a task but no constraint that names a format, schema, length or limit | a format stated only in an example block is not seen |
| `success.criteria_unclear` | info | heuristic / probable | no "success", "done when", "criteria" wording anywhere | prompts that define success implicitly ("Reply only with the label") still get this info finding |
| `context.unavailable` | warning | heuristic / probable | "the attached file", "the above", "the previous conversation" with no context node in the file | does not check that the referenced thing exists outside the analysed files |
| `injection.indicator` | warning | heuristic / probable | phrases such as "ignore all previous instructions", "reveal the system prompt", especially inside data blocks (`<document>`); a rule that *forbids* the phrase is not reported | a fixed phrase list in three languages; paraphrases are missed, benign mentions are flagged. The text is never executed or obeyed either way |
| `loop.no_stop_condition` | warning | heuristic / probable | a task that repeats ("repeat", "keep asking") without "until ..." or a bound | a stop condition in another sentence is not linked |

## What is not implemented

* Semantic duplicate and near-duplicate detection; semantic contradiction between differently worded instructions
  (the optional LLM layer can propose such edges, and its proposals are verified, but its precision and recall were
  **not measured** here: no provider was available).
* Checking that a tool's parameters match how a task calls it.
* Unreachability through contradictory conditions.
* `OVERRIDES` edges from role precedence alone, and `PRODUCES` edges for output files.
* Any rule that needs an LLM to decide (no rule is LLM-only).
