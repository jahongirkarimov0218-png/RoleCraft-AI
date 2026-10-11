"""The evaluation dataset is well-formed and honest about its status; the scoring maths is checked by hand on tiny
cases; the LLM part says "not run" without a provider and never fabricates a number."""

import json
from pathlib import Path

import pytest

from promptgraphify.analyze import analyze
from promptgraphify.evalkit import (
    CAVEATS,
    Counts,
    DatasetError,
    Scores,
    load_dataset,
    parse_record,
    render_markdown,
    resolve_quote,
    run_split,
    score_record,
)

from .fake_llm import FakeAdapter

DATASET = Path(__file__).parent.parent / "eval" / "dataset"
SPLITS = ("dev", "holdout")


def raw(**over):
    base = {
        "id": "t-1", "lang": "en", "split": "dev", "format": "txt", "review_status": "unreviewed",
        "labeled_by": "test", "text": "You are a bot.\nNever lie.\nSummarize it.\n",
        "nodes": [{"type": "SystemNode", "quote": "You are a bot."}, {"type": "ConstraintNode", "quote": "Never lie."},
                  {"type": "TaskNode", "quote": "Summarize it."}],
        "edges": [], "relations_complete": ["DEPENDS_ON"],
    }  # fmt: skip
    return {**base, **over}


# ------------------------------------------------------------------------------------ the real dataset
@pytest.mark.parametrize("split", SPLITS)
def test_dataset_is_well_formed_balanced_and_unreviewed(split):
    path = DATASET / f"{split}.jsonl"
    lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    records = load_dataset(path)  # raises DatasetError for any unresolved quote / unknown type / dangling edge
    assert len(records) == len(lines) == 24
    assert {r.lang for r in records} == {"en", "ru", "uz"} and all(
        sum(r.lang == lang for r in records) == 8 for lang in ("en", "ru", "uz")
    )
    assert all(r.split == split for r in records)
    assert all(line["review_status"] == "unreviewed" and "not human-reviewed" in line["labeled_by"] for line in lines)


def test_no_label_claims_human_review():
    for split in SPLITS:
        text = (DATASET / f"{split}.jsonl").read_text(encoding="utf-8").lower()
        assert "human-reviewed" not in text.replace("not human-reviewed", "")
        assert '"review_status": "reviewed"' not in text


def test_dev_and_holdout_do_not_share_prompts_or_ids():
    dev, hold = (load_dataset(DATASET / f"{s}.jsonl") for s in SPLITS)
    assert not {r.text for r in dev} & {r.text for r in hold}
    assert not {r.id for r in dev} & {r.id for r in hold}


def test_every_node_type_and_relation_group_is_represented_in_the_dataset():
    records = [r for s in SPLITS for r in load_dataset(DATASET / f"{s}.jsonl")]
    assert {t for r in records for t, _, _ in r.nodes} == {
        "SystemNode", "TaskNode", "ContextNode", "ConstraintNode", "ToolNode", "ExampleNode"
    }  # fmt: skip
    assert {rel for r in records for rel, _, _ in r.edges} >= {
        "DEPENDS_ON",
        "PRECEDES",
        "CALLS_TOOL",
        "EXEMPLIFIES",
        "CONFLICTS_WITH",
    }


# ------------------------------------------------------------------------------------------ validation
@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"review_status": "reviewed"}, "must be 'unreviewed'"),
        ({"lang": "de"}, "unknown lang"),
        ({"format": "pdf"}, "unknown lang or format"),
        ({"nodes": [{"type": "PersonaNode", "quote": "You are a bot."}]}, "unknown node type"),
        ({"nodes": [{"type": "TaskNode", "quote": "not in the text"}]}, "quote not found"),
        ({"nodes": []}, "at least one node"),
        ({"nodes": [{"type": "TaskNode", "quote": "t"}]}, "occurs"),
        ({"edges": [{"relation": "DEPENDS_ON", "source": "You are a bot.", "target": "ghost"}]}, "not a labelled node"),
        ({"edges": [{"relation": "LOVES", "source": "You are a bot.", "target": "Never lie."}]}, "unknown relation"),
        (
            {"edges": [{"relation": "PRECEDES", "source": "Never lie.", "target": "Summarize it."}]},
            "not listed in relations_complete",
        ),
        ({"relations_complete": ["NOPE"]}, "unknown relation"),
    ],
)
def test_malformed_records_are_rejected_with_the_record_id(change, message):
    with pytest.raises(DatasetError, match=message) as e:
        parse_record(raw(**change))
    assert "t-1" in str(e.value)


def test_quotes_must_be_unique_unless_an_occurrence_is_stated():
    assert resolve_quote("a b a", "b", None) == (2, 3)
    with pytest.raises(DatasetError, match="occurs 2 times"):
        resolve_quote("a b a", "a", None)
    assert resolve_quote("a b a", "a", 2) == (4, 5)
    with pytest.raises(DatasetError, match="does not exist"):
        resolve_quote("a b a", "a", 3)


# ------------------------------------------------------------------------------------------ scoring
def score(rec_raw, text=None):
    rec = parse_record(rec_raw)
    s = Scores()
    score_record(rec, analyze({rec.path: text or rec.text}), s)
    return s


def test_a_perfect_match_scores_one():
    s = score(raw())
    assert s.nodes_strict.metrics()["f1"] == 1.0 and s.misses == []


def test_a_missed_unit_lowers_recall_and_an_extra_one_lowers_precision():
    uncovered_text = "You are a bot.\nNever lie.\nSummarize it.\nzzz qqq www.\n"
    quiet = score(raw(text=uncovered_text))
    # text the analyzer cannot classify is neither a hit nor an extra node: it is uncovered, and reported elsewhere
    assert (quiet.nodes_strict.tp, quiet.nodes_strict.fp, quiet.nodes_strict.fn) == (3, 0, 0)
    extra = score(raw(nodes=raw()["nodes"][:2]))  # the annotator did not label the task the analyzer found
    assert (extra.nodes_strict.tp, extra.nodes_strict.fp, extra.nodes_strict.fn) == (2, 1, 0)
    assert any("extra TaskNode 'Summarize it.'" in m for m in extra.misses)
    lacking = score(raw(nodes=raw()["nodes"] + [{"type": "TaskNode", "quote": "Never"}]))
    assert lacking.nodes_strict.fn == 1 and any("missed TaskNode 'Never'" in m for m in lacking.misses)


def test_a_wrong_type_is_a_strict_error_but_a_relaxed_hit():
    s = score(raw(nodes=[{"type": "TaskNode", "quote": "You are a bot."}, *raw()["nodes"][1:]]))
    assert (s.nodes_strict.tp, s.nodes_strict.fp, s.nodes_strict.fn) == (2, 1, 1)
    assert (s.nodes_relaxed.tp, s.nodes_relaxed.fp, s.nodes_relaxed.fn) == (3, 0, 0)


def test_edges_are_scored_only_for_the_relations_the_annotator_completed():
    text = "1. Extract {{x}}.\n2. Check step 1.\n"
    nodes = [{"type": "TaskNode", "quote": "Extract {{x}}."}, {"type": "TaskNode", "quote": "Check step 1."},
             {"type": "ContextNode", "quote": "{{x}}", "occurrence": 1}]  # fmt: skip
    edges = [{"relation": "PRECEDES", "source": "Extract {{x}}.", "target": "Check step 1."}]
    complete = score(raw(text=text, nodes=nodes, edges=edges, relations_complete=["PRECEDES"]))
    assert complete.by_relation["PRECEDES"].tp == 1 and "DEPENDS_ON" not in complete.by_relation
    strict = score(raw(text=text, nodes=nodes, edges=edges, relations_complete=["PRECEDES", "DEPENDS_ON"]))
    # the analyzer found two DEPENDS_ON edges that the annotator did not label: they count as false positives
    assert strict.by_relation["DEPENDS_ON"].fp == 2 and strict.by_relation["DEPENDS_ON"].tp == 0
    assert any("extra edge DEPENDS_ON" in m for m in strict.misses)


def test_a_symmetric_relation_matches_in_either_direction():
    text = "Always answer in formal English.\nNever answer in formal English.\n"
    nodes = [
        {"type": "ConstraintNode", "quote": "Always answer in formal English."},
        {"type": "ConstraintNode", "quote": "Never answer in formal English."},
    ]
    forward = [{"relation": "CONFLICTS_WITH", "source": nodes[0]["quote"], "target": nodes[1]["quote"]}]
    backward = [{"relation": "CONFLICTS_WITH", "source": nodes[1]["quote"], "target": nodes[0]["quote"]}]
    for edges in (forward, backward):
        s = score(raw(text=text, nodes=nodes, edges=edges, relations_complete=["CONFLICTS_WITH"]))
        assert s.by_relation["CONFLICTS_WITH"].tp == 1 and s.by_relation["CONFLICTS_WITH"].fp == 0


def test_counts_metrics_handle_zero_denominators_without_inventing_numbers():
    assert Counts(0, 0, 0).metrics() == {"tp": 0, "fp": 0, "fn": 0, "precision": None, "recall": None, "f1": None}
    assert Counts(0, 3, 0).metrics()["precision"] == 0.0 and Counts(0, 3, 0).metrics()["recall"] is None
    m = Counts(3, 1, 3).metrics()
    assert (m["precision"], m["recall"], m["f1"]) == (0.75, 0.5, 0.6)


# ----------------------------------------------------------------------------------------- the report
def test_without_a_provider_the_llm_part_is_not_run_and_has_no_numbers(tmp_path):
    for use_llm in (False, True):
        result = run_split("dev", DATASET, use_llm=use_llm, adapter=None)
        assert result["llm"]["status"] == "not run" and set(result["llm"]) == {"status", "reason"}
        md = render_markdown(result)
        assert "**Not run.**" in md and CAVEATS in md
    assert "No provider is configured" in run_split("dev", DATASET, use_llm=True, adapter=None)["llm"]["reason"]


def test_the_llm_path_records_model_prompt_version_and_its_own_metrics_when_a_provider_is_given():
    fake = FakeAdapter({"nodes": [], "edges": []})
    result = run_split("dev", DATASET, use_llm=True, adapter=fake, now="2026-01-01T00:00:00+00:00")
    llm = result["llm"]
    assert (llm["status"], llm["model"], llm["adapter"], llm["prompt_version"], llm["run_at"]) == (
        "run", "fake-model-1", "fake", "1", "2026-01-01T00:00:00+00:00"
    )  # fmt: skip
    assert (
        llm["overall"]["nodes_strict"]["tp"] == result["deterministic"]["overall"]["nodes_strict"]["tp"]
    )  # nothing proposed
    assert len(fake.calls) == 24


def test_the_deterministic_result_is_reproducible_and_pins_the_dataset():
    a, b = (run_split("dev", DATASET, use_llm=False, adapter=None) for _ in range(2))
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    assert len(a["dataset_sha256"]) == 64 and a["records"] == 24
