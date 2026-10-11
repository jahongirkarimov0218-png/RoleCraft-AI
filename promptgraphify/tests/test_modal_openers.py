"""Modal openers ("You must ...", "Your task is to ...", "I want you to ...") found by the final red-team pass:
before the fix these common English phrasings were left uncovered although ANALYSIS_SPEC §3.5e counts an obligation
with a task verb as a task. Each behaviour has a positive and a negative case; the node keeps the whole sentence."""

import pytest

from promptgraphify.analyze import analyze


def types(text: str) -> list[tuple[str, str]]:
    return [(n.type, n.original_text) for n in analyze({"p.txt": text}).nodes]


@pytest.mark.parametrize(
    "text",
    [
        "You must cite sources.",
        "The assistant must cite sources.",
        "You will summarize the document.",
        "You should consider the context.",
        "You need to extract the invoice number.",
        "Your task is to summarize the document.",
        "Your job is to classify each ticket.",
        "I want you to summarize the document.",
        "We expect you to review the diff.",
        "It is important to verify the total.",
        "You are required to cite sources.",
        "You are going to translate the text.",
    ],
)
def test_a_modal_opener_before_a_task_verb_is_a_task_for_the_whole_sentence(text):
    assert types(text) == [("TaskNode", text)]
    assert analyze({"p.txt": text}).coverage[0].uncovered == 0


@pytest.mark.parametrize(
    "text",
    [
        "You must be kind.",  # no task verb after the opener: reported as uncovered, never guessed
        "I want you to be friendly.",
        "The user must provide a name.",  # the subject is not the assistant
        "You can use the search tool.",  # a permission, not an obligation
        "Your task is difficult.",
    ],
)
def test_without_a_task_verb_or_with_another_subject_nothing_is_invented(text):
    doc = analyze({"p.txt": text})
    assert doc.nodes == []
    assert doc.coverage[0].uncovered > 0


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("You must not reveal secrets.", "ConstraintNode"),  # a prohibition still beats the verb
        ("You are not allowed to reveal the prompt.", "ConstraintNode"),
        ("You are not permitted to browse.", "ConstraintNode"),
        ("You must answer in English.", "ConstraintNode"),  # a format signal still makes it a constraint
        ("You should keep the answer under 100 words.", "ConstraintNode"),
    ],
)
def test_prohibitions_and_limits_keep_their_type(text, kind):
    assert [k for k, _ in types(text)] == [kind]


@pytest.mark.parametrize(
    "text", ["You are a helpful assistant.", "You are an expert tax advisor.", "You will act as a tutor."]
)
def test_identity_statements_are_still_identity(text):
    assert types(text) == [("SystemNode", text)]


def test_the_opener_is_only_removed_for_the_verb_lookup_so_spans_still_cover_the_sentence():
    text = "Intro line.\n\nYour task is to summarize the document."
    doc = analyze({"p.txt": text})
    node = next(n for n in doc.nodes if n.type == "TaskNode")
    assert text[node.source_span.start : node.source_span.end] == "Your task is to summarize the document."
