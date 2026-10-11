# Extraction evaluation

A small, hand-labelled dataset and a harness that measures how well the analyzer's nodes and edges match it.

```
python -m promptgraphify.evalkit --split dev                 # deterministic layer
python -m promptgraphify.evalkit --split holdout --details   # deterministic layer, list every miss
python -m promptgraphify.evalkit --split dev --llm           # also the optional LLM layer (needs a provider)
```

Results are written to `eval/results/<split>.json` and `.md`. Without a configured provider the LLM part is
reported as **not run**; it is never estimated.

## What this is, and is not

* **Unreviewed labels.** Every record is `review_status: unreviewed`. The labels were written by the assistant
  that also wrote the analyzer, from the text alone, before looking at any parser output. No human has reviewed
  them. The dataset has room for review: set `review_status` to `reviewed`, and add who and when, in the record.
* **Agreement, not accuracy.** A high score means the analyzer agrees with that annotator's reading. The
  annotator and the analyzer share a definition of "unit" (`docs/ANALYSIS_SPEC.md` §2), so unit boundaries are
  easier to agree on than they would be for independent annotators.
* **Small.** 24 records per split, 120 labelled nodes each. A difference of a few points is noise.
* **dev vs holdout.** `dev` was used to find and fix defects (see `docs/DECISIONS.md` D-022 and `results/`).
  `holdout` was written at the same time as `dev` but not run against the analyzer until the dev work was done,
  and it was run once. Caveat: the same person wrote both and also widened the Russian/Uzbek verb lists in
  between, so independence is partial.

## Format (`dataset/*.jsonl`, one JSON object per line)

| field | meaning |
|---|---|
| `id`, `lang` (`en` `ru` `uz`), `split`, `format` (`txt` `md` `xml` `yaml` `json`) | identity; `format` becomes the file extension |
| `text` | the prompt, exactly as analysed |
| `nodes[]` | `{type, quote, occurrence?}`: the labelled units. `quote` is an exact substring of `text` (unique, or give the 1-based `occurrence`). Named things (variables, tools) are labelled once, at their first occurrence |
| `edges[]` | `{relation, source, target}` where source and target are node quotes |
| `relations_complete[]` | the relations whose edges were labelled **exhaustively** for this record. Only these are scored, and an unlabelled predicted edge of such a relation counts as a false positive |
| `review_status`, `labeled_by` | provenance; `review_status` must be `unreviewed` until a human has reviewed the record |

### Annotation guidelines (written before labelling)

* One unit per instruction, constraint, identity statement, variable, tool or example block (the smallest
  independently checkable piece). Headings, tags and list markers are not units.
* `SystemNode` identity/role; `TaskNode` something to do; `ConstraintNode` prohibition, limit, tone, format;
  `ContextNode` a variable placeholder (as written, braces included) or a data block; `ToolNode` a tool name at
  its first mention or its definition; `ExampleNode` the body of an example block.
* `DEPENDS_ON`: needs the value of a variable or the result of an earlier step. `PRECEDES`: the text states
  an order (numbered list, "then", a handoff). `CALLS_TOOL`: a task uses a tool. `PROVIDES_CONTEXT`: a data block
  supplies background to a task. `EXEMPLIFIES`: an example demonstrates a task. `CONFLICTS_WITH`: two
  instructions cannot both be followed. `CONDITIONALLY_EXECUTES`: a unit runs only if a named variable or step
  has a value. `CONSTRAINS` is not scored: a global constraint constrains everything, and listing every pair is
  not useful.

## Metrics

* **Node, strict**: same type and exactly the same span. **Node, span only**: ignores the type.
* **Edge**: `(relation, source span, target span)`; symmetric relations (`CONFLICTS_WITH`) match in either order.
* Precision, recall and F1 are micro-averaged (counts summed over records). `n/a` means the denominator is zero.
