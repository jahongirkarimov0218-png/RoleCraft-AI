import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from promptgraphify.spans import Span, cp_to_utf16, utf16_to_cp

EMOJI = "😀"  # U+1F600: one code point, two UTF-16 units


def test_span_rejects_reversed_and_negative():
    with pytest.raises(ValidationError):
        Span(start=5, end=3)
    with pytest.raises(ValidationError):
        Span(start=-1, end=3)


def test_span_text_and_relations():
    s = Span(start=2, end=5)
    assert s.text("abcdefg") == "cde" and len(s) == 3
    assert s.overlaps(Span(start=4, end=9)) and not s.overlaps(Span(start=5, end=9))
    assert s.contains(Span(start=3, end=4)) and not s.contains(Span(start=1, end=4))


def test_emoji_is_one_code_point_two_utf16_units():
    text = f"a{EMOJI}b"
    assert len(text) == 3
    assert cp_to_utf16(text, 0) == 0
    assert cp_to_utf16(text, 1) == 1
    assert cp_to_utf16(text, 2) == 3  # after the emoji
    assert cp_to_utf16(text, 3) == 4


def test_utf16_inside_surrogate_pair_is_rejected():
    text = f"a{EMOJI}b"
    assert utf16_to_cp(text, 3) == 2
    with pytest.raises(ValueError):
        utf16_to_cp(text, 2)  # between the two surrogates


def test_crlf_counts_two_code_points():
    text = "ab\r\ncd"
    assert text.index("c") == 4
    assert cp_to_utf16(text, 4) == 4  # BMP only: units == code points


def test_bom_occupies_index_zero():
    text = "\ufeffHello"
    assert text.index("H") == 1
    assert Span(start=1, end=6).text(text) == "Hello"


def test_offsets_out_of_range():
    with pytest.raises(ValueError):
        cp_to_utf16("abc", 4)
    with pytest.raises(ValueError):
        utf16_to_cp("abc", 4)


@given(st.text(), st.data())
def test_roundtrip_for_any_text(text, data):
    cp = data.draw(st.integers(min_value=0, max_value=len(text)))
    assert utf16_to_cp(text, cp_to_utf16(text, cp)) == cp


@given(st.text(alphabet=st.sampled_from(["a", "\n", "\r", EMOJI, "я", "\ufeff", " "]), max_size=40))
def test_utf16_length_matches_encoder(text):
    assert cp_to_utf16(text, len(text)) == len(text.encode("utf-16-le")) // 2
