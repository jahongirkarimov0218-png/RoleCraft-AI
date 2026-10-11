# ruff: noqa: E501
"""graph.html: one self-contained file that opens offline (double-click, file://).

* No network: no CDN, no font, no fetch. The CSP is ``default-src 'none'`` plus the SHA-256 of the one inline
  script and the one inline style, so injected markup cannot run.
* The graph itself is rendered as SVG by Python (all text escaped there); the data block is JSON with ``<``,
  ``>``, ``&`` and every non-ASCII character escaped, so no content can close the ``<script>`` element.
* The script only uses ``textContent`` / ``createTextNode`` for prompt-derived text, never ``innerHTML``.
"""

from __future__ import annotations

import base64
import hashlib
import json
from html import escape

from ..ir import GraphDocument
from .layout import NODE_H, NODE_W
from .svg import COLORS, SHORT, svg_body
from .svg import CSS as SVG_CSS

PAGE_CSS = """
:root{--bg:#f7f8fa;--panel:#fff;--text:#151922;--muted:#566074;--border:#d9dde6;--accent:#2f6fe0;--mark:#ffe58a}
@media (prefers-color-scheme:dark){:root{--bg:#0b0d12;--panel:#11141b;--text:#e6e9f0;--muted:#98a1b6;--border:#272c38;--accent:#6c9dff;--mark:#6b5400}}
*{box-sizing:border-box}html,body{height:100%;margin:0}
body{background:var(--bg);color:var(--text);font:14px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif;display:flex;flex-direction:column}
header{display:flex;flex-wrap:wrap;gap:8px 16px;align-items:center;padding:8px 16px;border-bottom:1px solid var(--border);background:var(--panel)}
header h1{font-size:15px;margin:0}header .meta{color:var(--muted);font-size:12px}
.tools{display:flex;flex-wrap:wrap;gap:6px 12px;align-items:center;margin-left:auto}
button,input[type=search]{font:inherit;color:var(--text);background:var(--panel);border:1px solid var(--border);border-radius:6px;min-height:32px;padding:0 10px}
button{cursor:pointer}button[aria-pressed=true]{border-color:var(--accent);box-shadow:inset 0 0 0 1px var(--accent)}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
label.t{display:inline-flex;gap:4px;align-items:center;font-size:12px;color:var(--muted)}
label.t i{width:10px;height:10px;border-radius:2px;display:inline-block}
main{flex:1;min-height:0;display:grid;grid-template-columns:minmax(0,1fr) 380px}
#stage{position:relative;min-height:320px;overflow:hidden;touch-action:none}
#canvas{width:100%;height:100%;display:block;cursor:grab}#canvas.drag{cursor:grabbing}
.zoom{position:absolute;right:12px;bottom:12px;display:flex;gap:6px}
aside{border-left:1px solid var(--border);background:var(--panel);overflow:auto;padding:12px 16px}
aside h2{font-size:13px;margin:16px 0 6px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted)}
aside h2:first-child{margin-top:0}
dl{margin:0;display:grid;grid-template-columns:auto 1fr;gap:2px 10px}dt{color:var(--muted)}dd{margin:0;overflow-wrap:anywhere}
ul.list{list-style:none;margin:0;padding:0;display:grid;gap:6px}
ul.list li{border:1px solid var(--border);border-radius:6px;padding:6px 8px;overflow-wrap:anywhere}
ul.list button{width:100%;text-align:left;border:0;padding:0;min-height:0;background:none}
pre#source{margin:0;max-height:260px;overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere;font:12px/1.5 ui-monospace,Consolas,monospace;border:1px solid var(--border);border-radius:6px;padding:8px}
mark{background:var(--mark);color:inherit;border-radius:2px}
.sev-error{color:#c0332b}.sev-warning{color:#a46f00}.sev-info{color:var(--muted)}
.muted{color:var(--muted)}.badge{display:inline-block;font-size:11px;border:1px solid var(--border);border-radius:999px;padding:0 6px;margin-right:4px}
.node{cursor:pointer}.node.sel rect{stroke-width:3.2}.node.dim,.edge.dim,.elabel.dim{opacity:.16}
.gone{display:none}.edge.hl{stroke-width:2.6}.view.off{display:none}
.node:focus-visible rect{stroke-width:3.2}
@media (max-width:820px){main{grid-template-columns:1fr;grid-template-rows:minmax(300px,55vh) auto}aside{border-left:0;border-top:1px solid var(--border)}}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
"""

SCRIPT = r"""
(function () {
  "use strict";
  var DATA = JSON.parse(document.getElementById("pg-data").textContent);
  var byId = {}, edgeById = {}, inc = {}, out = {};
  DATA.nodes.forEach(function (n) { byId[n.id] = n; });
  DATA.edges.forEach(function (e) {
    edgeById[e.id] = e;
    (out[e.source] = out[e.source] || []).push(e);
    (inc[e.target] = inc[e.target] || []).push(e);
  });
  var svg = document.getElementById("canvas"), vp = document.getElementById("viewport");
  var stage = document.getElementById("stage");
  var st = { view: "graph", sel: null, tx: 0, ty: 0, k: 1, hidden: {}, q: "" };

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text;
    return n;
  }
  function clear(n) { while (n.firstChild) n.removeChild(n.firstChild); }
  function cps(s) { return Array.from(s); }  /* offsets are Unicode code points, JS strings are UTF-16 */

  function apply() { vp.setAttribute("transform", "translate(" + st.tx + " " + st.ty + ") scale(" + st.k + ")"); }
  function viewEl() { return document.getElementById("view-" + st.view); }
  function fit() {
    var v = viewEl(), w = +v.getAttribute("data-w") || 1, h = +v.getAttribute("data-h") || 1;
    var r = svg.getBoundingClientRect();
    var k = Math.min(1.2, (r.width - 24) / w, (r.height - 24) / h);
    st.k = k > 0 ? k : 1;
    st.tx = (r.width - w * st.k) / 2; st.ty = Math.max(12, (r.height - h * st.k) / 2);
    apply();
  }
  function zoomAt(f, cx, cy) {
    var k = Math.min(4, Math.max(0.15, st.k * f)), r = k / st.k;
    st.tx = cx - (cx - st.tx) * r; st.ty = cy - (cy - st.ty) * r; st.k = k; apply();
  }
  function center() { var r = svg.getBoundingClientRect(); return [r.width / 2, r.height / 2]; }

  /* --- view switch, filters, search */
  function setView(name) {
    st.view = name;
    ["graph", "dag"].forEach(function (v) {
      document.getElementById("view-" + v).classList.toggle("off", v !== name);
      document.getElementById("btn-" + v).setAttribute("aria-pressed", String(v === name));
    });
    refresh(); fit();
  }
  function refresh() {
    var q = st.q.toLowerCase();
    viewEl().querySelectorAll(".node").forEach(function (g) {
      var n = byId[g.getAttribute("data-node-id")];
      g.classList.toggle("gone", !!st.hidden[n.type]);
      g.classList.toggle("dim", !!q && n.label.toLowerCase().indexOf(q) < 0);
      g.classList.toggle("sel", n.id === st.sel);
    });
    viewEl().querySelectorAll(".edge").forEach(function (p) {
      var e = edgeById[p.getAttribute("data-edge-id")];
      var gone = !e || st.hidden[byId[e.source].type] || st.hidden[byId[e.target].type];
      p.classList.toggle("gone", !!gone);
      p.classList.toggle("hl", !!e && st.sel !== null && (e.source === st.sel || e.target === st.sel));
    });
  }

  /* --- inspector */
  function row(dl, k, v) { dl.appendChild(el("dt", "", k)); dl.appendChild(el("dd", "", v)); }
  function edgeItem(e, other) {
    var li = el("li");
    var b = el("button", "", e.relation + " · " + (byId[other] ? byId[other].label : other));
    b.addEventListener("click", function () { select(other, true); });
    li.appendChild(b);
    li.appendChild(el("div", "muted", e.status + " · confidence " + e.confidence + " · " + e.rationale));
    if (e.evidence.length) li.appendChild(el("div", "muted", "“" + e.evidence[0].text + "”"));
    return li;
  }
  function renderSource(n) {
    var pre = document.getElementById("source"); clear(pre);
    var src = DATA.sources.filter(function (s) { return s.path === n.source_file; })[0];
    if (!src) { pre.textContent = "source not available"; return; }
    var a = cps(src.text), s = n.source_span.start, e = n.source_span.end, m = el("mark");
    m.textContent = a.slice(s, e).join("");
    pre.appendChild(document.createTextNode(a.slice(0, s).join("")));
    pre.appendChild(m);
    pre.appendChild(document.createTextNode(a.slice(e).join("")));
    m.scrollIntoView({ block: "center" });
  }
  function renderInspector(n) {
    var box = document.getElementById("inspector"); clear(box);
    if (!n) { box.appendChild(el("p", "muted", "Select a node to see its evidence.")); return; }
    var dl = el("dl");
    row(dl, "type", n.type); row(dl, "label", n.label); row(dl, "text", n.original_text);
    row(dl, "file", n.source_file + " [" + n.source_span.start + ", " + n.source_span.end + ")");
    row(dl, "role", (n.role_scope.role || "—") + (n.role_scope.agent ? " / " + n.role_scope.agent : ""));
    row(dl, "method", n.extraction_method + " · confidence " + n.confidence);
    var meta = Object.keys(n.metadata);
    if (meta.length) row(dl, "metadata", meta.map(function (k) { return k + ": " + JSON.stringify(n.metadata[k]); }).join("; "));
    box.appendChild(dl);
    [["Outgoing", out[n.id] || [], "target"], ["Incoming", inc[n.id] || [], "source"]].forEach(function (g) {
      if (!g[1].length) return;
      box.appendChild(el("h2", "", g[0] + " (" + g[1].length + ")"));
      var ul = el("ul", "list");
      g[1].forEach(function (e) { ul.appendChild(edgeItem(e, e[g[2]])); });
      box.appendChild(ul);
    });
    var ds = DATA.diagnostics.filter(function (d) { return d.affected_nodes.indexOf(n.id) >= 0; });
    if (ds.length) {
      box.appendChild(el("h2", "", "Diagnostics on this node"));
      var ul2 = el("ul", "list");
      ds.forEach(function (d) { ul2.appendChild(diagItem(d)); });
      box.appendChild(ul2);
    }
  }
  function select(id, focusView) {
    st.sel = id; refresh(); renderInspector(id ? byId[id] : null);
    if (id) renderSource(byId[id]); else clear(document.getElementById("source"));
    if (id && focusView) {
      var g = viewEl().querySelector('.node[data-node-id="' + CSS.escape(id) + '"]');
      if (g) g.focus({ preventScroll: true });
    }
  }
  function diagItem(d) {
    var li = el("li");
    var head = el("div"); head.appendChild(el("span", "sev-" + d.severity, d.severity));
    head.appendChild(document.createTextNode(" · " + d.certainty + " · " + d.rule_id));
    li.appendChild(head);
    li.appendChild(el("div", "", d.description));
    if (d.suggested_fix) li.appendChild(el("div", "muted", "Fix: " + d.suggested_fix));
    if (d.affected_nodes.length && byId[d.affected_nodes[0]]) {
      var b = el("button", "", "Show " + byId[d.affected_nodes[0]].label);
      b.addEventListener("click", function () { select(d.affected_nodes[0], true); });
      li.appendChild(b);
    }
    return li;
  }

  /* --- wiring */
  var diagBox = document.getElementById("diagnostics");
  if (!DATA.diagnostics.length) diagBox.appendChild(el("p", "muted", "No diagnostics."));
  else { var ul = el("ul", "list"); DATA.diagnostics.forEach(function (d) { ul.appendChild(diagItem(d)); }); diagBox.appendChild(ul); }

  svg.addEventListener("click", function (ev) {
    var g = ev.target.closest ? ev.target.closest(".node") : null;
    select(g ? g.getAttribute("data-node-id") : null, false);
  });
  svg.addEventListener("keydown", function (ev) {
    var g = ev.target.closest ? ev.target.closest(".node") : null;
    if (g && (ev.key === "Enter" || ev.key === " ")) { ev.preventDefault(); select(g.getAttribute("data-node-id"), false); }
    if (ev.key === "Escape") select(null, false);
    if (ev.key === "+" || ev.key === "=") { var c = center(); zoomAt(1.2, c[0], c[1]); }
    if (ev.key === "-") { var c2 = center(); zoomAt(1 / 1.2, c2[0], c2[1]); }
  });
  svg.addEventListener("wheel", function (ev) {
    ev.preventDefault();
    var r = svg.getBoundingClientRect();
    zoomAt(ev.deltaY < 0 ? 1.1 : 1 / 1.1, ev.clientX - r.left, ev.clientY - r.top);
  }, { passive: false });
  var drag = null;
  svg.addEventListener("pointerdown", function (ev) {
    if (ev.target.closest && ev.target.closest(".node")) return;
    drag = { x: ev.clientX, y: ev.clientY, tx: st.tx, ty: st.ty };
    svg.classList.add("drag"); svg.setPointerCapture(ev.pointerId);
  });
  svg.addEventListener("pointermove", function (ev) {
    if (!drag) return;
    st.tx = drag.tx + ev.clientX - drag.x; st.ty = drag.ty + ev.clientY - drag.y; apply();
  });
  function endDrag() { drag = null; svg.classList.remove("drag"); }
  svg.addEventListener("pointerup", endDrag); svg.addEventListener("pointercancel", endDrag);

  document.getElementById("btn-graph").addEventListener("click", function () { setView("graph"); });
  document.getElementById("btn-dag").addEventListener("click", function () { setView("dag"); });
  document.getElementById("zin").addEventListener("click", function () { var c = center(); zoomAt(1.25, c[0], c[1]); });
  document.getElementById("zout").addEventListener("click", function () { var c = center(); zoomAt(0.8, c[0], c[1]); });
  document.getElementById("zfit").addEventListener("click", fit);
  document.getElementById("q").addEventListener("input", function (ev) { st.q = ev.target.value; refresh(); });
  document.querySelectorAll("input[data-type]").forEach(function (cb) {
    cb.addEventListener("change", function () { st.hidden[cb.getAttribute("data-type")] = !cb.checked; refresh(); });
  });
  window.addEventListener("resize", fit);
  renderInspector(null); setView("graph");
  document.documentElement.setAttribute("data-ready", "1");
})();
"""


def _json_for_html(obj: object) -> str:
    """JSON that is safe inside a <script> element: ASCII only, and no ``<``, ``>`` or ``&``."""
    text = json.dumps(obj, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def _sha256(text: str) -> str:
    return "sha256-" + base64.b64encode(hashlib.sha256(text.encode("utf-8")).digest()).decode("ascii")


def to_html(doc: GraphDocument) -> str:
    graph_svg, gw, gh = svg_body(doc, "graph")
    dag_svg, dw, dh = svg_body(doc, "dag")
    data = _json_for_html(doc.model_dump(mode="json"))
    swatches = "".join(f'label i[data-c="{c}"]{{background:{c}}}\n' for c in COLORS.values())
    style = SVG_CSS + PAGE_CSS + swatches  # colours via attribute selectors: the CSP forbids style="" attributes
    csp = (
        "default-src 'none'; "
        f"script-src '{_sha256(SCRIPT)}'; style-src '{_sha256(style)}'; "
        "img-src data:; base-uri 'none'; form-action 'none'"
    )
    legend = "".join(
        f'<label class="t"><input type="checkbox" data-type="{t}" checked><i data-c="{c}"></i>{SHORT[t].title()}</label>'
        for t, c in COLORS.items()
    )
    n_nodes, n_edges = len(doc.nodes), len(doc.edges)
    return (
        "<!doctype html>\n"
        '<html lang="en" data-pg-schema="' + escape(doc.schema_version) + '">\n<head>\n<meta charset="utf-8">\n'
        f'<meta http-equiv="Content-Security-Policy" content="{escape(csp)}">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        f"<title>PromptGraphify graph {escape(doc.graph_id)}</title>\n<style>{style}</style>\n</head>\n<body>\n"
        "<header>\n"
        "<h1>PromptGraphify</h1>"
        f'<span class="meta">graph {escape(doc.graph_id)} · {n_nodes} nodes · {n_edges} edges · '
        f"DAG {escape(doc.dag.status)} · community-built, not affiliated with Graphify Labs</span>\n"
        '<div class="tools">'
        '<button id="btn-graph" type="button" aria-pressed="true">Knowledge graph</button>'
        '<button id="btn-dag" type="button" aria-pressed="false">Execution DAG</button>'
        '<input id="q" type="search" placeholder="Find node…" aria-label="Find node by label">'
        f"{legend}</div>\n</header>\n"
        '<main>\n<div id="stage">\n'
        '<svg id="canvas" xmlns="http://www.w3.org/2000/svg" tabindex="0" role="application" '
        'aria-label="Prompt graph. Tab moves between nodes, Enter selects, plus and minus zoom.">\n'
        '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
        'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#8a93a6"/></marker></defs>\n'
        '<g id="viewport">\n'
        f'<g class="view" id="view-graph" data-w="{gw:.0f}" data-h="{gh:.0f}">\n{graph_svg}\n</g>\n'
        f'<g class="view off" id="view-dag" data-w="{dw:.0f}" data-h="{dh:.0f}">\n{dag_svg}\n</g>\n'
        "</g>\n</svg>\n"
        '<div class="zoom"><button id="zout" type="button" aria-label="Zoom out">−</button>'
        '<button id="zfit" type="button" aria-label="Fit to view">Fit</button>'
        '<button id="zin" type="button" aria-label="Zoom in">+</button></div>\n</div>\n'
        '<aside aria-label="Details">\n<h2>Inspector</h2><div id="inspector"></div>\n'
        '<h2>Source</h2><pre id="source" aria-label="Source text with the selected span highlighted"></pre>\n'
        '<h2>Diagnostics</h2><div id="diagnostics"></div>\n</aside>\n</main>\n'
        f'<script type="application/json" id="pg-data">{data}</script>\n'
        f"<script>{SCRIPT}</script>\n</body>\n</html>\n"
    )


__all__ = ["NODE_H", "NODE_W", "to_html"]
