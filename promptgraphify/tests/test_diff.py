"""Diff: stable-ID matching, 'probably modified' only by similarity, and the six kinds of change. Every
expected value is derived by hand from the two inline prompts."""

from promptgraphify.analyze import analyze
from promptgraphify.diff import diff_documents

OLD = """# Task
You are a support bot.
1. Extract the ticket id from {{ticket}}.
2. Check step 1.
3. Summarize step 2.

## Rules
- Never promise a refund.
- Keep every answer under 50 words.
"""


def d(old: str, new: str):
    return diff_documents(analyze({"p.md": old}), analyze({"p.md": new}))


def labels(refs):
    return sorted(r.original_text for r in refs)


def test_identical_prompts_have_an_empty_diff():
    r = d(OLD, OLD)
    assert r.identical and r.old_graph_id == r.new_graph_id
    assert r.nodes_added == [] and r.nodes_removed == [] and r.probably_modified == [] and r.dependencies == []
    assert not r.sequence.changed and r.diagnostics_new == [] and r.diagnostics_resolved == []


def test_inserting_an_unrelated_line_changes_nothing_else():
    new = OLD.replace("## Rules", "Be brief.\n\n## Rules")  # shifts every offset after it
    r = d(OLD, new)
    assert labels(r.nodes_added) == ["Be brief."] and r.nodes_removed == [] and r.probably_modified == []


def test_added_and_removed_nodes_and_dependencies():
    new = OLD.replace("3. Summarize step 2.", "3. Summarize step 2.\n4. Send step 3 with the notify_user tool.")
    r = d(OLD, new)
    assert "Send step 3 with the notify_user tool." in labels(r.nodes_added)
    assert {c.kind for c in r.dependencies} == {"added"}
    rels = sorted((c.edge.relation, c.target_label) for c in r.dependencies)
    assert ("CALLS_TOOL", "notify_user") in rels and ("DEPENDS_ON", "Summarize step 2.") in rels
    back = d(new, OLD)
    assert {c.kind for c in back.dependencies} == {"removed"} and back.nodes_added == []
    assert "Send step 3 with the notify_user tool." in labels(back.nodes_removed)


def test_a_reworded_instruction_is_only_probably_modified():
    new = OLD.replace("Never promise a refund.", "Never promise any refunds.")
    r = d(OLD, new)
    (pair,) = r.probably_modified
    assert pair.basis == "text_similarity" and 0.6 <= pair.similarity < 1
    assert (
        pair.old.original_text == "Never promise a refund." and pair.new.original_text == "Never promise any refunds."
    )
    assert r.nodes_added == [] and r.nodes_removed == []  # not presented as add + remove
    kinds = [c.kind for c in r.constraints]
    assert kinds == ["probably_modified"]


def test_unrelated_replacement_is_add_plus_remove_not_a_guess():
    new = OLD.replace("Never promise a refund.", "Respond only in formal Uzbek.")
    r = d(OLD, new)
    assert r.probably_modified == []
    assert labels(r.nodes_removed) == ["Never promise a refund."] and labels(r.nodes_added) == [
        "Respond only in formal Uzbek."
    ]
    assert sorted(c.kind for c in r.constraints) == ["added", "removed"]


def test_constraint_added_removed_and_scope_change():
    r = d(OLD, OLD.replace("- Keep every answer under 50 words.\n", ""))
    assert [c.kind for c in r.constraints] == ["removed"]


def test_a_constraint_moved_to_another_section_is_reported_as_moved():
    # In OLD the rule sits under "# Task" (scope: that section); in NEW it is above every heading (global).
    new = "- Never promise a refund.\n\n" + OLD.replace("- Never promise a refund.\n", "")
    r = d(OLD, new)
    (pair,) = r.probably_modified
    assert pair.identical_text and pair.similarity == 1.0
    assert [c.kind for c in r.constraints] == ["moved"]


def test_execution_sequence_change_is_reported_with_moved_vertices():
    new = """# Task
You are a support bot.
1. Summarize the notes.
2. Extract the ticket id from {{ticket}}.
3. Check step 2.

## Rules
- Never promise a refund.
- Keep every answer under 50 words.
"""
    r = d(OLD, new)
    assert r.sequence.changed and r.sequence.old_status == r.sequence.new_status == "ok"
    assert r.sequence.old_critical_path != r.sequence.new_critical_path or r.sequence.moved
    assert r.sequence.old_order[0] != r.sequence.new_order[0]


def test_dag_blocked_is_a_sequence_change():
    r = d("1. Extract the data.\n2. Check step 1.\n", "1. Check step 2.\n2. Check step 1.\n")
    assert r.sequence.changed and (r.sequence.old_status, r.sequence.new_status) == ("ok", "blocked")
    assert any(x.diagnostic.rule_id == "dependency.cycle" for x in r.diagnostics_new)


def test_new_and_resolved_diagnostics():
    broken = OLD.replace("{{ticket}}", "{{ticket}} and {{order}}")
    r = d(OLD, broken)
    assert [x.diagnostic.rule_id for x in r.diagnostics_new if x.diagnostic.rule_id == "variable.undeclared"] == [
        "variable.undeclared"
    ]
    assert "order" in [lab for x in r.diagnostics_new for lab in x.labels]
    fixed = d(broken, OLD)
    assert any(x.diagnostic.rule_id == "variable.undeclared" for x in fixed.diagnostics_resolved)
    assert not any(x.diagnostic.rule_id == "variable.undeclared" for x in fixed.diagnostics_new)


def test_summary_counts_match_the_lists():
    new = OLD.replace("Never promise a refund.", "Never promise any refunds.").replace("# Task", "# Task\nBe brief.")
    r = d(OLD, new)
    s = r.summary
    assert s.nodes_added == len(r.nodes_added) and s.nodes_removed == len(r.nodes_removed)
    assert s.probably_modified == len(r.probably_modified) and s.constraints_changed == len(r.constraints)
    assert s.dependencies_added + s.dependencies_removed == len(r.dependencies)
    assert not r.identical


def test_diff_is_deterministic_and_symmetric_in_size():
    a, b = analyze({"p.md": OLD}), analyze({"p.md": OLD.replace("50 words", "80 words")})
    assert diff_documents(a, b).model_dump_json() == diff_documents(a, b).model_dump_json()
    fwd, back = diff_documents(a, b), diff_documents(b, a)
    assert len(fwd.probably_modified) == len(back.probably_modified)


def test_every_listed_dependency_cites_evidence():
    r = d(OLD, OLD.replace("3. Summarize step 2.", "3. Summarize step 2 and {{extra}}."))
    for c in r.dependencies:
        assert c.evidence


def test_rewording_a_step_on_the_critical_path_does_not_change_the_sequence():
    new = OLD.replace("3. Summarize step 2.", "3. Summarize the result of step 2.")
    r = d(OLD, new)
    (pair,) = r.probably_modified
    assert pair.old.original_text == "Summarize step 2." and pair.new.original_text == "Summarize the result of step 2."
    assert not r.sequence.changed and r.sequence.moved == [] and r.sequence.note == "order unchanged"
    assert r.sequence.old_critical_path != r.sequence.new_critical_path  # the labels differ, the vertices do not
