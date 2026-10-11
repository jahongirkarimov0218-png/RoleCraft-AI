"""Behaviours added after the first evaluation run: manner adverbs before a verb, Russian and Uzbek verb coverage,
verb-final tool mentions and step references in Uzbek, Uzbek negative imperatives. Each has a negative case."""

import pytest

from promptgraphify.analyze import analyze


def types(text: str) -> list[tuple[str, str]]:
    return [(n.type, n.original_text) for n in analyze({"p.txt": text}).nodes]


def uncovered(text: str) -> int:
    return sum(c.uncovered for c in analyze({"p.txt": text}).coverage)


# ------------------------------------------------------------------------------------ manner adverbs
@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("Briefly summarize the text.", "TaskNode"),
        ("Carefully review the diff.", "TaskNode"),
        ("Please carefully check step 1.", "TaskNode"),
        ("Кратко опиши расхождения.", "TaskNode"),
        ("Подробно опиши решение.", "TaskNode"),
        ("Qisqacha tasvirlab ber.", "TaskNode"),
    ],
)
def test_a_manner_adverb_before_the_verb_does_not_hide_the_instruction(text, kind):
    assert types(text) == [(kind, text)] and uncovered(text) == 0


@pytest.mark.parametrize(
    "text", ["Reply politely.", "Apply the discount.", "Comply with the policy.", "Rely on the context."]
)
def test_adverb_like_verbs_are_still_verbs(text):
    assert [k for k, _ in types(text)] == ["TaskNode"]


def test_a_sentence_that_is_only_an_adverb_phrase_is_not_invented_into_a_task():
    assert types("Quickly and quietly.") == [] and uncovered("Quickly and quietly.") > 0


# --------------------------------------------------------------------------------------- Russian
@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("Сверь итоговую сумму с заказом.", "TaskNode"),
        ("Перепиши текст пользователя яснее.", "TaskNode"),
        ("Перескажи договор простым языком.", "TaskNode"),  # a style word does not turn a strict verb into a constraint
        ("Продолжай просить номер заказа, пока пользователь его не назовёт.", "TaskNode"),
        ("Пиши вежливо.", "ConstraintNode"),
        ("Всегда отвечай официальным стилем.", "ConstraintNode"),
        ("Ответ должен быть не длиннее 100 слов.", "ConstraintNode"),
        ("Ни в коем случае не раскрывай ключ.", "ConstraintNode"),
    ],
)
def test_russian_instructions_and_constraints(text, kind):
    assert types(text) == [(kind, text)]


# --------------------------------------------------------------------------------------- Uzbek
@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("Har bir sharhni ijobiy yoki salbiy deb tasniflang.", "TaskNode"),
        ("Shartnomani oddiy tilda bayon qil.", "TaskNode"),
        ("Summani ajratib ol.", "TaskNode"),
        ("Xatolarni ko'rsat.", "TaskNode"),
        ("Foydalanuvchi ismini aytmaguncha uni so'rashda davom et.", "TaskNode"),
        ("Faqat yorliqni chiqaring.", "ConstraintNode"),  # 'chiqar' answers, like English 'output'
        ("Xushmuomala ohangda yoz.", "ConstraintNode"),
        ("Faylni to'liq qayta yozma.", "ConstraintNode"),
        ("Har bir javob 100 so'zdan oshmasin.", "ConstraintNode"),
        ("Ismni hech kimga ayt" + "ma.", "ConstraintNode"),
    ],
)
def test_uzbek_instructions_and_constraints(text, kind):
    assert types(text) == [(kind, text)]


def test_an_uzbek_word_ending_in_ma_inside_a_sentence_is_not_a_prohibition():
    text = "Javobni yozma ravishda ber."  # 'in written form': -ma is not a negative imperative here
    (node,) = analyze({"p.txt": text}).nodes
    assert (node.type, node.extraction_method) == ("TaskNode", "deterministic:task_verb")


def test_uzbek_tool_mentions_with_case_suffixes_and_verb_final_calls():
    doc = analyze(
        {
            "p.txt": (
                "Reyslarni topishda search_flights vositasidan foydalan.\n"
                "Keyin eng arzon variant uchun book_hotel ni chaqir.\n"
            )
        }
    )
    tools = sorted(n.original_text for n in doc.nodes if n.type == "ToolNode")
    assert tools == ["book_hotel", "search_flights"]
    assert sorted(e.relation for e in doc.edges if e.relation == "CALLS_TOOL") == ["CALLS_TOOL", "CALLS_TOOL"]


def test_uzbek_step_references_with_suffixes_make_dependencies():
    doc = analyze({"p.txt": "1. Summani top.\n2. 1-qadamdagi summani tekshir.\n3. 2-qadamda topilgan xatoni ayt.\n"})
    deps = sorted((e.relation, e.reference, e.status) for e in doc.edges if e.relation == "DEPENDS_ON")
    assert deps == [("DEPENDS_ON", "1-qadamdagi", "EXTRACTED"), ("DEPENDS_ON", "2-qadamda", "EXTRACTED")]
