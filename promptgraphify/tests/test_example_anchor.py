"""EXEMPLIFIES without a naming reference: the example belongs to the nearest preceding *task* (D-022)."""

from promptgraphify.analyze import analyze

WITH_TASK = (
    "Classify each review as positive or negative.\nOutput only the label.\n\n"
    "Example:\nReview: Great.\nLabel: positive\n"
)
ONLY_CONSTRAINT = "Output only the label.\n\nExample:\nReview: Great.\nLabel: positive\n"


def target_of_example(text: str) -> tuple[str, str]:
    doc = analyze({"p.txt": text})
    nodes = {n.id: n for n in doc.nodes}
    (e,) = [e for e in doc.edges if e.relation == "EXEMPLIFIES"]
    assert nodes[e.source].type == "ExampleNode" and (e.status, e.rule, e.reference) == (
        "INFERRED",
        "proximity.preceding",
        None,
    )
    return nodes[e.target].type, nodes[e.target].original_text


def test_the_task_wins_over_a_nearer_constraint():
    assert target_of_example(WITH_TASK) == ("TaskNode", "Classify each review as positive or negative.")


def test_without_any_task_the_nearest_constraint_is_used():
    assert target_of_example(ONLY_CONSTRAINT) == ("ConstraintNode", "Output only the label.")
