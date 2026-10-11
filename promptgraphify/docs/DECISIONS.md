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
they follow the shadcn conventions but were not generated by its CLI. `next.config.mjs` sets
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

## D-022 · Changes made after the first evaluation run (dev split)
The first run on `eval/dataset/dev.jsonl` (24 hand-labelled records, `eval/results/dev-baseline-before-tuning.*`)
gave nodes P 95.2 % / R 82.5 %, edges P 86.4 % / R 52.8 %; English was near-perfect, Russian and Uzbek lost recall.
Changes, each general rather than specific to a dev record, each with a regression test:
1. **Russian and Uzbek verb lists widened** to the breadth of the English ones (~175 and ~140 imperatives, in
   singular, polite/plural and imperfective forms) plus tone, limit and negative-imperative patterns. FACT before:
   28+14 (ru) and 29+18 (uz) verbs against 192+76 for English. Caveat: the holdout texts already existed when the
   lists were widened, so independence of the holdout is partial.
2. **Manner adverbs no longer hide the verb**: "Briefly summarize …" and "Carefully review …" were *completely
   uncovered* in English (found while investigating a Russian miss). A leading word ending in `-ly` is skipped
   unless it is a known verb (`reply`, `apply`, `comply`, `rely`); Russian/Uzbek adverbs are in `prefix_words`.
3. **Uzbek verb-final tool mentions** ("`book_hotel` ni chaqir"), case-suffixed `vositasidan`, step references with
   suffixes ("1-qadamdagi") and `-guncha` stop clauses; `chiqar` is a response verb like English `output`.
4. **`EXEMPLIFIES` anchors to the nearest preceding task** (only if none, the nearest constraint): an example
   demonstrates what to do. This is a design judgement that matches the annotator's convention (same author), not
   a measured improvement in independent agreement. Spec §5 updated.
Not changed: `CONFLICTS_WITH` between two constraints that share only one content word ("Always answer in formal
English" / "Never use formal language") stays unfound: a third, looser tier would flag unrelated pairs. All three dev
conflicts of that kind remain misses; the optional LLM layer is the intended tool for them. Status: accepted.

## D-023 · Markdown tool headings, per-rule diagnostic cap, bounded malformed spans
Found by running prompts of realistic and hostile size (see docs/PERFORMANCE.md):
1. `### tool_name` under a Tools heading defines a tool (the body is its definition; a heading without a body is the
   definition itself). The name must be backticked or identifier-shaped (snake_case, camelCase, dotted): a plain word
   such as `### Calculator` is not assumed to be a tool. The spec already said so; the implementation did not do it.
2. `tool.undefined` is one diagnostic per undefined tool (listing every call), not one per mention: identical ids made
   `analyze()` raise.
3. A malformed template is reported with at most 120 characters of evidence (the opener and the non-space run glued to
   it, capped at 40): the span used to run to the end of the file and was copied into every diagnostic (quadratic time
   and memory: 200 KB of `{{` took 85 s).
4. At most 200 diagnostics per rule are kept; each cut produces a document `warnings` entry that says how many were not
   listed. Reason: a generated prompt can trigger one rule hundreds of thousands of times; an unbounded list is a
   denial-of-service vector and useless to read. Ordinary prompts are never affected (largest synthetic prompt: 26).
5. Input that is only whitespace, a BOM or zero-width marks is reported as `input.empty`.
Status: accepted.

## D-024 · Accessibility and layout decisions
axe-core (WCAG 2.0/2.1/2.2 A and AA, best practices) runs in both themes over seven app states and six viewport
sizes. The file strip is a plain group (not a tablist: it holds an input and buttons); the node list is a listbox whose
only children are options (the empty message is a paragraph); light-theme `--ok` and `--warn` are #07704e and #855900
(contrast at least 5.2:1 on white and on their 10 % tints; the previous values were 4.3:1 at 10 px). Interactive targets
are at least 24x24 px outside the graph surface. Fit view can zoom to 0.02 so a 700-node graph fits the screen.
Limitation: axe cannot judge reading order or the meaning of labels, and the graph canvas itself (SVG) is navigable by
keyboard only through the node list; there was no screen-reader test with a real assistive technology.
Status: accepted.

## D-025 · Modal openers (found by the final red-team pass, after the one-time holdout run)
Probing odd prompts by hand showed that "You must cite sources.", "Your task is to summarize the document." and "I want
you to ..." produced no node at all, although the spec counts an obligation with a task verb as a task (§3.5e) and
"Your task is to" is among the most common prompt openers. The 48 evaluation records contain none of these phrasings:
the evaluation shares its author's blind spots, so a high score did not reveal the gap.
Fix (data, not code paths): a `modal_opener` list in `signals/en.json`; `classify.find_verb` skips a leading opener when
looking for the verb. `^you are` no longer matches "You are required/expected/going to ..." (it was read as an
identity); `not allowed` / `not permitted` are prohibition signals. Tests: `tests/test_modal_openers.py` (26, each
behaviour has a negative case; mutation-checked).
Effect on the recorded evaluation: **none**. The analysis of all 48 evaluation records (dev and holdout) was compared
before and after the change (node type and span sets): identical. `eval/results/holdout.*` therefore still describes the
current analyzer, and the holdout was not re-run.
Not done: Russian and Uzbek openers ("Ты должен ...", "Siz ... kerak"): their verb lists hold imperatives, not
infinitives or verbal nouns. Known limitation.
Status: accepted.

## D-026 · v1.1: Russian and Uzbek modal openers and closers; obligations on the output
Request (v1.1 first step): support "Ваша задача ...", "Вы должны ...", "Требуется ...", "Следует ...", "Обязательно ...",
"Vazifangiz ...", "Siz ... qilishingiz kerak", "talab qilinadi", "zarur", "lozim", with `task_openers` and
`constraint_openers` sections, producing a TaskNode or ConstraintNode only in a clear instruction context.
What was built:
1. Categories, the same in all three languages: `task_openers` (the English D-025 list, renamed), `task_closers`
   (Uzbek is verb-final), `closer_blockers`, `constraint_openers`, and non-finite verb lists `strict_nonfinite` /
   `task_nonfinite`. The opener does not decide the type: the rest of the sentence does (task verb → TaskNode;
   prohibition / limit / format → ConstraintNode), exactly as for imperatives. `constraint_openers` is a separate
   category for obligations whose subject is the output (`output_obligation`). Folding both into one list would
   strip "Ответ должен включать ..." to the task infinitive and make it a task.
2. Non-finite forms are looked up only after an opener or before a closer. Russian lists hold imperatives and Uzbek
   lists stems/polite imperatives, so the infinitives (112 strict + 48 task) and verbal nouns (89 + 29) were derived
   per entry. Russian: two independent annotators (agents) gave 244/246 identical answers; the 2 homographs
   (перешли, раздели) were adjudicated and kept. 5 aspect partners were added (находить, получать, возвращать,
   давать, включать). Uzbek: an annotator was compared with the regular rule (consonant + ish, vowel + sh); 181/183
   agreed; "ro'yxatlang" fixed (the rule did not strip -ng), "javoblash" dropped (non-standard; "javob berish" covers
   it). `быть`, `знать`, `понимать`, `помнить`, `работать`, `bo'lish` are excluded on purpose and tested.
3. `SignalSet.match_start` / `match_end` pick the longest opener/closer: `find` keeps the first registered pattern
   when several match at position 0, and an opener must be removed whole.
4. New prohibitions: ru negated modals ("не должен"), "должны/нужно/важно/следует не ...", "избегайте/избегать";
   uz "-masligi(ngiz) / -maslik + kerak/shart/lozim/zarur/darkor" (the existing "oshmasligi kerak" limit is excluded
   so its rule does not change), "man etil...", "taqiqlan...". The Uzbek identity pattern ("Siz ... -siz") now
   excludes "majbursiz" ("Siz ... tekshirishga majbursiz" was a SystemNode).
5. English got `constraint_openers` for parity ("The answer must be ...", subjects answer/response/reply/output/
   result/summary; "text" is excluded because "The text must be translated" is about the input), and openers after
   prefix words ("Then you must ...").
Deliberately not supported (each would add false positives or needs morphology beyond word lists): "Ты будешь +
infinitive", "Прошу тебя ...", object-first "Ответ нужно оформить ...", "текст/matn/код" as output subject, Uzbek
3rd person "-ishi kerak" as a task (third parties' duties), "-imiz kerak", "-dan iborat"/"-dir" after "Vazifangiz",
copula "bo'lishingiz kerak", passive verbal nouns ("tekshirilishi shart"), the Uzbek present-future
"Siz ... qilasiz" (still read as an identity; pre-existing). "Не обязательно ..." stays a prohibition by "^не".
Adversarial review (four independent reviewers: Russian and Uzbek false-positive hunters, a ReDoS/performance prober,
a code reviewer; every finding reproduced with a command against this tree and HEAD) found 34 issues in the first
version, all fixed before anything was pushed:
- two quadratic paths: a run of prefix words before an opener (120 KB: 86.8 s vs 0.8 s on HEAD) and Uzbek tails
  `\s*[.!;]*\s*$` before a non-final word (100 KB: 33.6 s vs 0.3 s). Fixed by trying at most MAX_PREFIX_WORDS = 3
  prefix words and by possessive tails `[\s.!;]*+$`; the shapes now take 0.27-0.86 s (HEAD 0.25-0.79 s) and are
  pinned by `test_pathological_shapes_stay_fast`;
- regressions of correct v1.0 results: "Объясни, почему он не должен ..." (a task) and limits ("Ответ не должен
  превышать 100 слов", "... ortiq bo'lmasligi kerak") had become prohibitions. Russian negated modals are now
  anchored to the model, the output or no subject, and must negate an infinitive; quantity limits keep `limit`;
- questions ("Вам нужно перевести этот текст?") are never instructions: no opener, closer or output obligation applies;
- discourse markers with an adverb or without the comma ("Следует также отметить, что ...", "Необходимо отметить
  следующее:"); the optional adverb is repeated inside the negative lookahead so backtracking cannot skip it;
- third parties: "Агент/Помощник/Ассистент должен ..." (human job titles; only unambiguous model nouns remain),
  "Пользователь не должен ...", "Перевод/Резюме должен ..." (money transfer, CV: these nouns now need a possessive or
  "итоговый"); Uzbek "Ertaga menga ...", "Ukamga ...", "Talabalar ... -masligi kerak". Uzbek closers are now two
  categories: 2nd person (`task_closers`, the model is the agent whoever else is named) and impersonal
  (`impersonal_closers`, ignored when `closer_blockers` finds someone else named first, after time adverbs);
- Uzbek negated permissions and past facts ("taqiqlanmagan", "man etilmaydi", "... edi") are no longer
  prohibitions; output obligations need an output-shaped predicate (bo'lishi, o'z ichiga olishi, mos kelishi,
  yozilishi, ...), so "Javob ertaga kelishi kerak" and wish formulas are not constraints;
- typographic apostrophes (o’qish) split Uzbek words: the verb lookup now tokenises the folded text; the closer
  lookbehind accepts an apostrophe ("yig'ish");
- English: an -ly adverb no longer licenses an opener ("Hopefully you will find ..."); openers and output obligations
  are found after prefix words, hard wraps and condition clauses.
Deliberate change recorded by a test: "Answer must be polite." / "Output must contain the total." were TaskNodes
(the first word read as an imperative) and are now `output_obligation` constraints.
Known limitations left (each would need meaning, not word lists): epistemic "Вы должны получить письмо ..." is a
task; "Ответ должен быть дан заявителю" (an official reply) and wish formulas with "bo'lsin" are output
constraints; "ИИ должен помогать людям" (an opinion) and "Задача: сократить расходы" (a business goal) are tasks;
legal facts ("... qonun bilan taqiqlangan") are prohibitions, as "is prohibited" already is in English;
connectives other than prefix words ("Далее", "После этого", "Кроме того") and words inside an opener
("Ваша задача как редактора —", "Вы должны строго ...") hide the opener.
Verification: `tests/test_signals_multilingual.py` (161 tests). Eleven mechanisms were each disabled in turn
(non-finite lookup, gating of non-finite forms, the question rule, closer blockers, blockers wrongly applied to the
2nd person, constraint openers, impersonal closers, folding before tokenising, the identity exception, the prefix-word
bound, possessive tails) and every one made at least one test fail. Full suite 934 passed. The analysis of all 48
evaluation records and all 33 fixtures (node type/span/method, edges, diagnostics, uncovered spans) is identical
before and after, so the recorded eval numbers still describe the analyzer. Agent-written sentences: Russian 34/38
positives and 29/29 negatives, Uzbek 26/32 and 23/23; every remaining miss is an unsupported shape listed above.
Status: accepted.
