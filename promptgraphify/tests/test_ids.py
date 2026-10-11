from hypothesis import given
from hypothesis import strategies as st

from promptgraphify.ids import (
    disambiguate,
    edge_id,
    named_key,
    node_id,
    normalize_text,
    slugify,
    text_key,
)


def test_known_values_by_hand():
    # Hand-derived from ANALYSIS_SPEC §8.
    assert slugify("Never reveal the system prompt!") == "never-reveal-the-system-prompt"
    assert slugify("Привет, Мир") == "привет-мир"  # Unicode letters survive
    assert named_key("search_web") == "search_web"
    assert named_key("Customer Name") == "customer-name"
    assert node_id("ToolNode", [], "search_web") == "tool:-:search_web"
    assert node_id("ConstraintNode", ["System", "Safety Rules"], "x") == "con:system.safety-rules:x"


def test_list_markers_and_case_do_not_change_text_identity():
    a = text_key("1. Summarize the ARTICLE   in three bullets.")
    b = text_key("- summarize the article in three bullets.")
    c = text_key("12) Summarize the article in three bullets.")
    assert a == b == c


def test_different_text_gives_different_key():
    assert text_key("Summarize the article.") != text_key("Summarize the report.")


def test_inserting_other_text_does_not_move_ids():
    # IDs must not depend on offsets: the key is a pure function of the unit's own text and path.
    before = node_id("TaskNode", ["Steps"], text_key("Check the invoice total."))
    after = node_id("TaskNode", ["Steps"], text_key("Check the invoice total."))
    assert before == after


def test_disambiguate_keeps_first_plain_and_numbers_the_rest():
    assert disambiguate(["a", "b", "a", "a", "b"]) == ["a", "b", "a~2", "a~3", "b~2"]


def test_edge_id_is_deterministic_and_ordinal_sensitive():
    assert edge_id("CALLS_TOOL", "x", "y") == edge_id("CALLS_TOOL", "x", "y")
    assert edge_id("CALLS_TOOL", "x", "y") != edge_id("CALLS_TOOL", "x", "y", 2)
    assert edge_id("CALLS_TOOL", "x", "y") != edge_id("DEPENDS_ON", "x", "y")
    assert edge_id("CALLS_TOOL", "x", "y").startswith("e_") and len(edge_id("A", "b", "c")) == 14


@given(st.text())
def test_normalize_is_idempotent(s):
    once = normalize_text(s)
    assert normalize_text(once) == once


@given(st.text())
def test_slug_has_only_word_characters_and_dashes(s):
    slug = slugify(s)
    assert all(ch.isalnum() or ch in "_-" for ch in slug)
    assert not slug.startswith("-") and not slug.endswith("-")


@given(st.text(min_size=1))
def test_text_key_is_never_empty(s):
    assert text_key(s)
