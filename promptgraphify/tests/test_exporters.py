"""Exports are checked with independent readers (an XML parser, networkx, an HTML parser, json), not by
string matching alone, and hostile prompt text must never turn into markup, script or Markdown structure."""

import base64
import hashlib
import io
import json
import re
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

import networkx as nx
import pytest

from promptgraphify import graphjson
from promptgraphify.analyze import AnalysisError, analyze
from promptgraphify.exporters import to_graphml, to_html, to_mermaid, to_report, to_svg
from promptgraphify.exporters.html import SCRIPT
from promptgraphify.security import xml_safe, xml_unsafe_count

RLO = chr(0x202E)
NONCHAR = chr(0xFFFE)
NUL = chr(0)
BEL = chr(7)

PROMPT = """# Task
You are a support bot.
1. Extract the ticket id from {{ticket}}.
2. Check step 1.
3. Summarize step 2.

## Rules
- Never promise a refund.
- Keep every answer under 50 words.
"""

HOSTILE = (
    "# T\n"
    "1. Do </script><script>alert(1)</script> now.\n"
    '2. Check step 1 "onmouseover="alert(1)" <img src=x onerror=alert(1)>.\n'
    "3. Extract `a``b` | pipe | [link](javascript:alert(1)) <b>bold</b> ]]> & -->.\n"
    f"4. Summarize step 3 {RLO}evil.\n"
)

CONTROL = f"1. Extract the id{NUL}{BEL}{NONCHAR}.\n2. Check step 1.\n"
CYCLE = "1. Check step 2.\n2. Check step 1.\n"
AMBIGUOUS = "1. Look up the order with the search_orders tool.\n"


def doc_of(text: str, path: str = "p.md"):
    return analyze({path: text})


# ----------------------------------------------------------------------------------------- graph.json
def test_graph_json_export_is_canonical_and_reloads():
    doc = doc_of(PROMPT)
    text = graphjson.dumps(doc)
    assert graphjson.dumps(graphjson.loads(text)) == text
    assert json.loads(text)["graph_id"] == doc.graph_id


# ---------------------------------------------------------------------------------------------- GraphML
def read_graphml(text: str):
    return nx.read_graphml(io.BytesIO(text.encode("utf-8")))


def test_graphml_rereads_with_every_node_edge_and_attribute():
    doc = doc_of(PROMPT)
    g = read_graphml(to_graphml(doc))
    assert g.number_of_nodes() == len(doc.nodes) and g.number_of_edges() == len(doc.edges)
    for n in doc.nodes:
        a = g.nodes[n.id]
        assert (a["type"], a["label"], a["original_text"]) == (n.type, n.label, n.original_text)
        assert (a["span_start"], a["span_end"]) == (n.source_span.start, n.source_span.end)
        assert json.loads(a["metadata"]) == n.metadata
    # networkx returns a plain DiGraph unless some pair has parallel edges, so identify edges by attribute
    by_id = {a["edge_id"]: (u, v, a) for u, v, a in g.edges(data=True)}
    assert set(by_id) == {e.id for e in doc.edges}
    for e in doc.edges:
        u, v, a = by_id[e.id]
        assert (u, v, a["relation"], a["status"]) == (e.source, e.target, e.relation, e.status)
        assert json.loads(a["evidence"]) == [ev.model_dump(mode="json") for ev in e.evidence]
    assert g.graph["graph_id"] == doc.graph_id and g.graph["xml_replaced_chars"] == 0


def test_graphml_keeps_newlines_and_unicode_in_text():
    doc = doc_of("Summarize the text.\n\nTranslate it into Uzbek: salom, dunyo — “quoted”.\n")
    g = read_graphml(to_graphml(doc))
    assert {a["original_text"] for _, a in g.nodes(data=True)} == {n.original_text for n in doc.nodes}


def test_graphml_replaces_unrepresentable_characters_and_says_how_many():
    doc = doc_of(CONTROL)
    raw_unsafe = sum(xml_unsafe_count(n.original_text) + xml_unsafe_count(n.label) for n in doc.nodes)
    assert raw_unsafe > 0
    text = to_graphml(doc)
    ET.fromstring(text.encode("utf-8"))  # well-formed
    g = read_graphml(text)
    assert g.graph["xml_replaced_chars"] >= raw_unsafe
    assert all(NUL not in a["original_text"] and NONCHAR not in a["original_text"] for _, a in g.nodes(data=True))


def test_xml_safe_boundaries():
    keep = "a\t\n\r bé퟿�\U00010000\U0010ffff"
    assert xml_safe(keep) == keep and xml_unsafe_count(keep) == 0
    for bad in (chr(0), chr(8), chr(0xB), chr(0xC), chr(0x1F), chr(0xD800), chr(0xDFFF), chr(0xFFFE), chr(0xFFFF)):
        assert xml_safe("x" + bad + "y") == "x�y" and xml_unsafe_count(bad) == 1


# ------------------------------------------------------------------------------------------------- SVG
@pytest.mark.parametrize("view", ["graph", "dag"])
@pytest.mark.parametrize("text", [PROMPT, HOSTILE, CONTROL, CYCLE, AMBIGUOUS])
def test_svg_is_well_formed_xml_for_every_view_and_input(view, text):
    ET.fromstring(to_svg(doc_of(text), view).encode("utf-8"))


def test_svg_has_one_group_per_node_and_one_path_per_arrow():
    doc = doc_of(PROMPT)
    root = ET.fromstring(to_svg(doc, "graph").encode("utf-8"))
    ns = "{http://www.w3.org/2000/svg}"
    nodes = [g for g in root.iter(ns + "g") if g.get("class") == "node"]
    assert sorted(g.get("data-node-id") for g in nodes) == sorted(n.id for n in doc.nodes)
    assert len([p for p in root.iter(ns + "path") if "edge" in (p.get("class") or "")]) == len(doc.edges)
    dag = ET.fromstring(to_svg(doc, "dag").encode("utf-8"))
    dag_nodes = [g.get("data-node-id") for g in dag.iter(ns + "g") if g.get("class") == "node"]
    assert sorted(dag_nodes) == sorted(doc.dag.vertices)


def test_svg_dag_view_draws_one_arrow_per_ordered_pair():
    doc = doc_of(PROMPT)
    root = ET.fromstring(to_svg(doc, "dag").encode("utf-8"))
    ns = "{http://www.w3.org/2000/svg}"
    arrows = [p for p in root.iter(ns + "path") if "edge" in (p.get("class") or "")]
    assert len(arrows) == len({(e.source, e.target) for e in doc.dag.edges})


def test_svg_hostile_text_is_text_not_markup():
    svg = to_svg(doc_of(HOSTILE), "graph")
    root = ET.fromstring(svg.encode("utf-8"))
    tags = {el.tag.split("}")[-1] for el in root.iter()}
    assert "script" not in tags and "img" not in tags and "foreignObject" not in tags
    assert not any(k.lower().startswith("on") for el in root.iter() for k in el.attrib)
    # Prompt text may appear as *text* (titles, aria-labels); it must never reach a URL/style/handler context.
    assert not any(k.endswith("href") or k in {"src", "style", "action"} for el in root.iter() for k in el.attrib)
    assert RLO not in svg


def test_svg_dag_arrows_say_needed_by_not_depends_on():
    svg = to_svg(doc_of(PROMPT), "dag")
    assert "needed by" in svg and "depends on" not in svg
    assert "depends on" in to_svg(doc_of(PROMPT), "graph")


# --------------------------------------------------------------------------------------------- Mermaid
@pytest.mark.parametrize("view", ["graph", "dag"])
def test_mermaid_structure_matches_the_graph(view):
    doc = doc_of(HOSTILE)
    lines = to_mermaid(doc, view).splitlines()
    assert lines[0] == "flowchart LR"
    decl = [ln for ln in lines if re.match(r"^ {4}n\d+[\(\[\{>]", ln)]
    arrows = [ln for ln in lines if re.match(r"^ {4}n\d+ (-->|-\.->)\|", ln)]
    classdefs = [ln for ln in lines if ln.startswith("    classDef ")]
    assert len(lines) == 1 + len(decl) + len(arrows) + len(classdefs)  # no label produced an extra line
    expected_vertices = doc.dag.vertices if view == "dag" else [n.id for n in doc.nodes]
    assert len(decl) == len(expected_vertices)
    aliases = {re.match(r"^ {4}(n\d+)", ln).group(1) for ln in decl}
    for ln in arrows:
        a, b = re.findall(r"\bn\d+\b", ln.replace("|", " | "))[:2]
        assert a in aliases and b in aliases


def test_mermaid_labels_cannot_close_their_quotes_or_open_markup():
    text = to_mermaid(doc_of(HOSTILE), "graph")
    for ln in text.splitlines():
        if not re.match(r"^ {4}n\d+[\(\[\{>]", ln):
            continue
        label = re.search(r'"(.*)"', ln).group(1)
        assert not any(c in label for c in '"[]{}|<>`'), label
    assert RLO not in text


def test_mermaid_dashed_arrows_mark_non_extracted_edges():
    doc = doc_of(AMBIGUOUS)
    assert any(e.status == "AMBIGUOUS" for e in doc.edges)
    assert "-.->" in to_mermaid(doc, "graph")


# --------------------------------------------------------------------------------------------- report
CODE_SPAN = re.compile(r"(`+).+?\1", re.S)


def test_report_has_every_section_and_states_definitions():
    r = to_report(doc_of(PROMPT))
    for heading in ("## Summary", "## Most connected nodes", "## Execution order", "## Diagnostics", "## Coverage"):
        assert heading in r
    assert "degree = number of knowledge-graph edges" in r
    assert "Critical path:" in r and "critical_path_length" in r


def test_report_is_deterministic_and_matches_the_graph():
    doc = doc_of(PROMPT)
    assert to_report(doc) == to_report(doc_of(PROMPT))
    assert f"Nodes: {len(doc.nodes)}" in to_report(doc) and f"Edges: {len(doc.edges)}" in to_report(doc)


def test_report_most_connected_is_sorted_by_degree():
    doc = doc_of(PROMPT)
    degree: dict[str, int] = {}
    for e in doc.edges:
        degree[e.source] = degree.get(e.source, 0) + 1
        if e.target != e.source:
            degree[e.target] = degree.get(e.target, 0) + 1
    shown = [int(m) for m in re.findall(r"— degree (\d+) —", to_report(doc))]
    assert shown == sorted(shown, reverse=True) and shown[0] == max(degree.values())


def test_report_hostile_text_stays_inside_code_spans():
    outside = CODE_SPAN.sub("", to_report(doc_of(HOSTILE)))
    assert "<" not in outside and "javascript:" not in outside and "](" not in outside and RLO not in outside


def test_report_lists_ambiguous_edges_for_review():
    r = to_report(doc_of(AMBIGUOUS))
    assert "AMBIGUOUS edges" in r and "CALLS_TOOL" in r


def test_report_names_the_cycle_when_the_dag_is_blocked():
    r = to_report(doc_of(CYCLE))
    assert "No execution order exists" in r and "cycle" in r and "evidence:" in r


def test_report_for_a_prompt_without_ordering_says_so():
    r = to_report(doc_of("You are a helpful assistant.\n"))
    assert "no ordering relations" in r


def test_report_shows_uncovered_text_honestly():
    doc = doc_of("You are a bot.\nxyzzy plugh quux.\n")
    unc = sum(c.uncovered for c in doc.coverage)
    assert unc > 0  # the premise: this text is not understood, so the report has something to admit
    r = to_report(doc)
    assert f"uncovered {unc}" in r and "uncovered [" in r and "xyzzy plugh quux." in r


# ---------------------------------------------------------------------------------------------- HTML
class Tags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags: list[tuple[str, dict[str, str | None]]] = []
        self.scripts: list[str] = []
        self.styles: list[str] = []
        self._open: str | None = None

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))
        if tag in ("script", "style"):
            self._open = tag
            (self.scripts if tag == "script" else self.styles).append("")

    def handle_endtag(self, tag):
        if tag == self._open:
            self._open = None

    def handle_data(self, data):
        if self._open == "script":
            self.scripts[-1] += data
        elif self._open == "style":
            self.styles[-1] += data


def parse_html(text: str) -> Tags:
    p = Tags()
    p.feed(text)
    p.close()
    return p


def csp_of(text: str) -> dict[str, str]:
    content = next(a["content"] for t, a in parse_html(text).tags if t == "meta" and a.get("http-equiv"))
    return {d.split(" ", 1)[0]: d.split(" ", 1)[1] if " " in d else "" for d in content.split("; ")}


def sha(text: str) -> str:
    return "'sha256-" + base64.b64encode(hashlib.sha256(text.encode("utf-8")).digest()).decode() + "'"


@pytest.mark.parametrize("text", [PROMPT, HOSTILE])
def test_html_csp_pins_exactly_the_inline_script_and_style(text):
    html = to_html(doc_of(text))
    parsed = parse_html(html)
    code = [
        s
        for (t, a), s in zip([x for x in parsed.tags if x[0] == "script"], parsed.scripts, strict=True)
        if not a.get("type")
    ]
    assert len(code) == 1 and csp_of(html)["script-src"] == sha(code[0]) and code[0] == SCRIPT
    assert len(parsed.styles) == 1 and csp_of(html)["style-src"] == sha(parsed.styles[0])
    policy = " ".join(csp_of(html).values())
    assert csp_of(html)["default-src"] == "'none'" and "unsafe-inline" not in policy and "unsafe-eval" not in policy


def test_html_loads_nothing_from_outside():
    html = to_html(doc_of(PROMPT))
    parsed = parse_html(html)
    forbidden_tags = {"link", "img", "iframe", "object", "embed", "form", "base", "audio", "video", "source", "frame"}
    assert not [t for t, _ in parsed.tags if t in forbidden_tags]
    assert not [(t, k) for t, a in parsed.tags for k in a if k in {"src", "href", "action", "srcset", "poster"}]
    without_data = re.sub(r'<script type="application/json".*?</script>', "", html, flags=re.S)
    assert set(re.findall(r"https?://[^\s\"'<>]+", without_data)) <= {"http://www.w3.org/2000/svg"}
    assert "@import" not in html and not re.search(r"url\((?!#)", html)  # only local #fragment references
    assert not any("style" in a for _, a in parsed.tags)  # inline style attributes would break the CSP


def test_html_data_block_is_inert_and_complete():
    doc = doc_of(HOSTILE)
    html = to_html(doc)
    parsed = parse_html(html)
    scripts = [s for (t, _), s in zip([x for x in parsed.tags if x[0] == "script"], parsed.scripts, strict=True)]
    assert len(scripts) == 2  # the data block and the code: injected </script> never opened a third
    blocks = [a for t, a in parsed.tags if t == "script"]
    data = scripts[next(i for i, a in enumerate(blocks) if a.get("type") == "application/json")]
    assert not set("<>&") & set(data)
    assert json.loads(data) == doc.model_dump(mode="json")


def test_html_script_never_writes_markup():
    for banned in (
        "innerHTML",
        "outerHTML",
        "insertAdjacentHTML",
        "document.write",
        "eval(",
        "new Function",
        "setTimeout(",
    ):
        assert banned not in SCRIPT


def test_html_is_deterministic_and_self_describing():
    doc = doc_of(PROMPT)
    html = to_html(doc)
    assert html == to_html(doc_of(PROMPT))
    assert doc.graph_id in html and "not affiliated with Graphify Labs" in html
    assert 'lang="en"' in html and 'name="viewport"' in html


@pytest.mark.parametrize("text", [PROMPT, CYCLE, CONTROL, "You are a helpful assistant.\n"])
def test_every_export_works_on_blocked_empty_and_odd_graphs(text):
    doc = doc_of(text)
    for out in (to_html(doc), to_report(doc), to_mermaid(doc), to_mermaid(doc, "dag"), to_graphml(doc), to_svg(doc)):
        out.encode("utf-8")  # writable to a file as UTF-8


# ------------------------------------------------------------------------------------- surrogates
def test_a_lone_surrogate_is_rejected_cleanly_not_crashed_on():
    with pytest.raises(AnalysisError) as e:
        analyze({"p.md": "Summarize this " + chr(0xD800) + " please.\n"})
    assert e.value.code == "invalid_text"
    with pytest.raises(AnalysisError):
        analyze({"p" + chr(0xDC00) + ".md": "Summarize this.\n"})
