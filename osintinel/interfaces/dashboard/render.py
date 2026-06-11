"""Static dashboard renderer (doc 06 Phase 7) — one self-contained, offline HTML document.

Renders a :class:`DashboardData` into a single HTML string with **inline** CSS and SVG and
**no JavaScript at all** — navigation is pure CSS (hidden radios + `:checked` selectors), so it
works air-gapped, in sandboxed previews that strip scripts, and without a browser for tests.
No external fonts, scripts, styles, or network calls. The aesthetic is an "intelligence console":
a dark theme whose colour language *is* the epistemic ladder (information → connection →
explanation{speculation|extrapolation} → hypothesis → insight), so the visuals encode the
foundational separation rather than merely decorating it.

Sections: Overview · Knowledge Graph (layered SVG) · Timeline & Replay · Confidence Evolution
(SVG sparklines from ``confidence_history``) · Source Explorer · Agent Activity.
"""

from __future__ import annotations

import html

from ..api.service import TIER_COLORS, DashboardData

_EDGE_COLORS = {
    "supports": "#3ddc84", "contradicts": "#ff6b6b", "synthesized_from": "#4aa3df",
    "derived_from": "#56607a", "has_member": "#39435e", "has_explanation": "#39435e",
}
_LADDER = ["INFORMATION", "CONNECTION", "SPECULATION", "EXTRAPOLATION", "HYPOTHESIS", "INSIGHT"]


def _e(text) -> str:
    return html.escape(str(text), quote=True)


def _tier_color(klass: str | None, node_type: str | None = None) -> str:
    if node_type == "Source":
        return "#5a6477"
    if node_type == "HypothesisSet":
        return "#33405c"
    return TIER_COLORS.get(klass or "", "#7e8aa2")


# --------------------------------------------------------------------------- sections
def _kpi_cards(data: DashboardData) -> str:
    order = [("leader_confidence", "Leader confidence", "{:.0%}"),
             ("hypotheses", "Hypotheses", "{}"), ("evidence", "Evidence", "{}"),
             ("sources", "Sources", "{}"), ("iterations", "Iterations", "{}"),
             ("ledger_events", "Ledger events", "{}")]
    cards = []
    for key, label, fmt in order:
        if key not in data.kpis:
            continue
        val = data.kpis[key]
        shown = fmt.format(val) if isinstance(val, (int, float)) else _e(val)
        cards.append(f'<div class="kpi"><div class="kpi-val">{_e(shown)}</div>'
                     f'<div class="kpi-lbl">{_e(label)}</div></div>')
    return f'<div class="kpis">{"".join(cards)}</div>'


def _class_chip(klass: str | None, etype: str | None = None) -> str:
    if not klass:
        return ""
    c = _tier_color(klass, etype)
    return (f'<span class="chip" style="--c:{c}">{_e(klass)}</span>')


def _overview(data: DashboardData) -> str:
    rows = []
    for r in data.ranked:
        conf = r["confidence"]
        chip = _class_chip(r["epistemic_class"])
        bar = (f'<div class="bar"><div class="bar-fill" '
               f'style="width:{conf * 100:.1f}%;--c:{_tier_color(r["epistemic_class"])}"></div>'
               f'<span class="bar-num">{conf:.0%}</span></div>')
        rows.append(f"<tr><td>{_e(r['statement'])}</td><td>{chip}</td><td>{bar}</td></tr>")
    ranked_tbl = (f'<table class="tbl"><thead><tr><th>Hypothesis</th><th>Class</th>'
                  f'<th>Confidence</th></tr></thead><tbody>{"".join(rows)}</tbody></table>')

    def _list(title, items, cls=""):
        if not items:
            return ""
        lis = "".join(f"<li>{_e(x)}</li>" for x in items)
        return f'<div class="panel {cls}"><h3>{_e(title)}</h3><ul>{lis}</ul></div>'

    return f"""
    <section id="sec-overview" class="tab">
      <div class="panel"><h3>Executive summary</h3><p>{_e(data.executive_summary)}</p></div>
      <div class="panel"><h3>Competing hypotheses (preserved)</h3>{ranked_tbl}</div>
      <div class="grid2">
        {_list("Known unknowns", data.known_unknowns)}
        {_list("Unknown-unknown indicators", data.unknown_unknowns, "warn")}
      </div>
      {_list("Recommended next investigations", data.next_steps)}
    </section>"""


def _graph_svg(data: DashboardData) -> str:
    W, H, pad = 1000, 640, 70
    pos = {n.id: (pad + n.x * (W - 2 * pad), pad + n.y * (H - 2 * pad)) for n in data.nodes}

    edges_svg = []
    for ed in data.edges:
        if ed.source not in pos or ed.target not in pos:
            continue
        x1, y1 = pos[ed.source]
        x2, y2 = pos[ed.target]
        color = _EDGE_COLORS.get(ed.type, "#56607a")
        op = 0.85 if ed.type in ("supports", "contradicts") else 0.35
        w = 1.0 + (abs(ed.weight) * 2.5 if ed.weight else 0.0)
        edges_svg.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                         f'stroke="{color}" stroke-width="{w:.1f}" stroke-opacity="{op}"/>')

    nodes_svg = []
    for n in data.nodes:
        x, y = pos[n.id]
        color = _tier_color(n.epistemic_class, n.type)
        r = 7.0 + (n.confidence or 0.0) * 9.0 if n.type in ("Hypothesis", "Explanation") else 7.0
        glow = (f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r + 7:.1f}" fill="{color}" '
                f'opacity="0.18"/>') if n.epistemic_class == "INSIGHT" else ""
        label = _e(n.label[:24])
        tip = _e(f"{n.type}: {n.label}" + (f" ({n.epistemic_class})" if n.epistemic_class else ""))
        nodes_svg.append(
            f'<g class="gnode"><title>{tip}</title>{glow}'
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{color}" '
            f'stroke="#0b0e16" stroke-width="1.5"/>'
            f'<text x="{x:.1f}" y="{y - r - 5:.1f}" class="glabel">{label}</text></g>')

    legend = "".join(
        f'<span class="lg"><i style="background:{c}"></i>{_e(k)}</span>'
        for k, c in TIER_COLORS.items())
    edge_legend = "".join(
        f'<span class="lg"><i style="background:{c}"></i>{_e(k)}</span>'
        for k, c in _EDGE_COLORS.items() if k in ("supports", "contradicts", "synthesized_from",
                                                  "derived_from"))
    return f"""
    <section id="sec-graph" class="tab">
      <div class="panel">
        <h3>Knowledge graph <span class="muted">— layered by epistemic tier (left → right)</span></h3>
        <div class="legendbar">{legend}</div>
        <div class="legendbar muted">edges: {edge_legend}</div>
        <svg viewBox="0 0 {W} {H}" class="graph" preserveAspectRatio="xMidYMid meet">
          <g>{"".join(edges_svg)}</g><g>{"".join(nodes_svg)}</g>
        </svg>
      </div>
    </section>"""


def _timeline(data: DashboardData) -> str:
    max_ev = max((t.event_count for t in data.timeline), default=1)
    cols = []
    for t in data.timeline:
        h = 8 + int(120 * t.event_count / max_ev)
        tip = ", ".join(f"{k}×{v}" for k, v in sorted(t.types.items()))
        cols.append(f'<div class="tl-col"><div class="tl-bar" style="height:{h}px" '
                    f'title="{_e(tip)}"></div><div class="tl-it">it {t.iteration}</div>'
                    f'<div class="tl-n">{t.event_count}</div></div>')
    rows = "".join(
        f'<tr><td>{ev.seq}</td><td>{ev.iteration}</td>'
        f'<td><span class="tag">{_e(ev.actor)}</span></td>'
        f'<td><code>{_e(ev.type)}</code></td><td>{_e(ev.summary)}</td></tr>'
        for ev in data.events)
    return f"""
    <section id="sec-timeline" class="tab">
      <div class="panel"><h3>Timeline <span class="muted">— events per iteration</span></h3>
        <div class="timeline">{"".join(cols)}</div>
        <p class="muted">Investigation replay: every iteration is reconstructable from the
        append-only ledger; the graph as of iteration <em>k</em> is a pure replay of events with
        iteration ≤ <em>k</em>.</p>
      </div>
      <div class="panel"><h3>Provenance ledger ({len(data.events)} events)</h3>
        <div class="scroll"><table class="tbl"><thead><tr><th>#</th><th>it</th><th>actor</th>
        <th>type</th><th>summary</th></tr></thead><tbody>{rows}</tbody></table></div>
      </div>
    </section>"""


def _spark(points, color, width=300, height=46, thick=2.0) -> str:
    if not points:
        return ""
    if len(points) == 1:
        points = points + points
    n = len(points)
    pts = " ".join(f"{(i / (n - 1)) * (width - 8) + 4:.1f},"
                   f"{height - 4 - p.confidence * (height - 8):.1f}" for i, p in enumerate(points))
    return (f'<svg viewBox="0 0 {width} {height}" class="spark">'
            f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="{thick}" '
            f'stroke-linejoin="round"/></svg>')


def _confidence(data: DashboardData) -> str:
    rows = []
    for t in data.hypothesis_tracks:
        color = _tier_color(t.final_class)
        spark = _spark(t.points, color, thick=3.0 if t.is_leader else 1.6)
        star = ' <span class="star">★ leader</span>' if t.is_leader else ""
        rows.append(
            f'<tr><td>{_e(t.statement)}{star}</td><td>{_class_chip(t.final_class)}</td>'
            f'<td class="mono">{t.final_confidence:.0%}</td><td>{spark}</td></tr>')
    return f"""
    <section id="sec-confidence" class="tab">
      <div class="panel">
        <h3>Hypothesis &amp; confidence evolution <span class="muted">— from confidence_history
        (append-only; competing hypotheses preserved)</span></h3>
        <table class="tbl"><thead><tr><th>Hypothesis</th><th>Class</th><th>Final</th>
        <th>Trajectory</th></tr></thead><tbody>{"".join(rows)}</tbody></table>
      </div>
    </section>"""


def _sources(data: DashboardData) -> str:
    rows = "".join(
        f'<tr><td>{_e(s.source)}</td>'
        f'<td><span class="tag">{_e(s.independence_group)}</span></td>'
        f'<td><code>{_e(s.acquisition_method)}</code></td>'
        f'<td>{_e(s.tool_used or "—")}</td><td>{s.evidence_count}</td>'
        f'<td class="muted">{_e(s.license_note or "—")}</td></tr>'
        for s in data.sources)
    groups = sorted({s.independence_group for s in data.sources})
    chips = "".join(f'<span class="tag">{_e(g)}</span>' for g in groups)
    return f"""
    <section id="sec-sources" class="tab">
      <div class="panel"><h3>Source explorer
        <span class="muted">— {len(groups)} independent group(s)</span></h3>
        <div class="legendbar">{chips}</div>
        <table class="tbl"><thead><tr><th>Source</th><th>Independence group</th><th>Method</th>
        <th>Tool</th><th>Evidence</th><th>License</th></tr></thead><tbody>{rows}</tbody></table>
      </div>
    </section>"""


def _agents(data: DashboardData) -> str:
    max_ev = max((a.event_count for a in data.agent_activity), default=1)
    rows = []
    for a in data.agent_activity:
        w = 100 * a.event_count / max_ev
        types = ", ".join(f"{k}×{v}" for k, v in sorted(a.event_types.items()))
        rows.append(
            f'<div class="arow"><div class="aname">{_e(a.actor)}</div>'
            f'<div class="abar"><div class="abar-fill" style="width:{w:.1f}%"></div>'
            f'<span>{a.event_count}</span></div>'
            f'<div class="muted atypes">{_e(types)}</div></div>')
    return f"""
    <section id="sec-agents" class="tab">
      <div class="panel"><h3>Agent activity <span class="muted">— ledger events by actor</span></h3>
        {"".join(rows)}
      </div>
    </section>"""


_TABS = [("overview", "Overview"), ("graph", "Knowledge Graph"),
         ("timeline", "Timeline &amp; Replay"), ("confidence", "Confidence Evolution"),
         ("sources", "Sources"), ("agents", "Agents")]


def _ladder_bar() -> str:
    seg = "".join(f'<span style="background:{TIER_COLORS[k]}">{k.lower()}</span>' for k in _LADDER)
    return f'<div class="ladder">{seg}</div>'


def render_dashboard(data: DashboardData) -> str:
    # CSS-only tabs: hidden radios drive section visibility via :checked sibling selectors —
    # so navigation works with ZERO JavaScript (and even in sandboxed previews that strip it).
    radios = "".join(
        f'<input type="radio" name="tab" id="tab-{tid}" class="tabradio"'
        f'{" checked" if i == 0 else ""}>'
        for i, (tid, _label) in enumerate(_TABS))
    nav = "".join(
        f'<label class="navbtn" for="tab-{tid}">{label}</label>' for tid, label in _TABS)
    body = (_overview(data) + _graph_svg(data) + _timeline(data) + _confidence(data)
            + _sources(data) + _agents(data))
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>OSINTINEL — {_e(data.title)}</title>
<style>{_CSS}</style></head>
<body>
<header class="top">
  <div class="brand"><span class="logo">◎</span> OSINTINEL
    <span class="muted">/ Investigation Console</span></div>
  <div class="meta">{_e(data.title)} · <code>{_e(data.investigation_id[:8])}</code>
    · {_e(data.domain or "—")} · terminated: {_e(data.termination_reason)}</div>
</header>
{_ladder_bar()}
{_kpi_cards(data)}
{radios}
<nav class="nav">{nav}</nav>
<main>{body}</main>
<footer class="foot">Generated {_e(data.generated_at)} · self-contained, offline, replayable
from the append-only ledger · competing hypotheses preserved, uncertainty surfaced.</footer>
</body></html>"""


_CSS = """
:root{--bg:#0b0e16;--bg2:#111726;--panel:#141b2d;--line:#222c44;--ink:#e6ecf7;--mut:#8a96b0;
--accent:#3ddc84}
*{box-sizing:border-box}
body{margin:0;background:radial-gradient(1200px 600px at 70% -10%,#16203a 0,var(--bg) 60%);
color:var(--ink);font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
code,.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
.top{display:flex;justify-content:space-between;align-items:center;padding:16px 24px;
border-bottom:1px solid var(--line);background:rgba(10,13,22,.6);backdrop-filter:blur(6px)}
.brand{font-weight:700;letter-spacing:.5px;font-size:16px}
.logo{color:var(--accent);margin-right:6px}
.meta{color:var(--mut);font-size:12.5px}
.muted{color:var(--mut);font-weight:400}
/* epistemic ladder — given room to breathe, with arrows between rungs */
.ladder{display:flex;gap:6px;margin:0;padding:10px 24px;font-size:11px;letter-spacing:.5px;
text-transform:uppercase;flex-wrap:wrap;border-bottom:1px solid var(--line);
background:rgba(10,13,22,.4)}
.ladder span{flex:1 1 120px;text-align:center;padding:8px 10px;color:#06121f;font-weight:700;
border-radius:6px;opacity:.95;min-width:96px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;padding:18px 24px}
.kpi{background:linear-gradient(160deg,var(--panel),var(--bg2));border:1px solid var(--line);
border-radius:12px;padding:14px 16px}
.kpi-val{font-size:24px;font-weight:700}
.kpi-lbl{color:var(--mut);font-size:12px;margin-top:2px}
/* CSS-only tabs: radios are hidden; labels are the buttons; :checked drives the panels */
.tabradio{position:absolute;opacity:0;pointer-events:none}
.nav{display:flex;gap:8px;padding:8px 24px 0;flex-wrap:wrap}
.navbtn{background:transparent;border:1px solid var(--line);color:var(--mut);padding:9px 16px;
border-radius:9px 9px 0 0;cursor:pointer;font-size:13px;user-select:none;white-space:nowrap}
.navbtn:hover{color:var(--ink);border-color:#33405c}
main{padding:18px 24px 40px}
.tab{display:none}
#tab-overview:checked~main #sec-overview,
#tab-graph:checked~main #sec-graph,
#tab-timeline:checked~main #sec-timeline,
#tab-confidence:checked~main #sec-confidence,
#tab-sources:checked~main #sec-sources,
#tab-agents:checked~main #sec-agents{display:block}
#tab-overview:checked~nav label[for=tab-overview],
#tab-graph:checked~nav label[for=tab-graph],
#tab-timeline:checked~nav label[for=tab-timeline],
#tab-confidence:checked~nav label[for=tab-confidence],
#tab-sources:checked~nav label[for=tab-sources],
#tab-agents:checked~nav label[for=tab-agents]{background:var(--panel);color:var(--ink);
border-color:var(--line);border-bottom-color:var(--panel)}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px 18px;
margin-bottom:16px}
.panel h3{margin:0 0 12px;font-size:14.5px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media(max-width:760px){.grid2{grid-template-columns:1fr}}
.tbl{width:100%;border-collapse:collapse;font-size:13px}
.tbl th{text-align:left;color:var(--mut);font-weight:600;border-bottom:1px solid var(--line);
padding:8px 10px}
.tbl td{border-bottom:1px solid #1a2236;padding:8px 10px;vertical-align:middle}
.chip{display:inline-block;padding:2px 9px;border-radius:999px;font-size:11px;font-weight:700;
color:#06121f;background:var(--c)}
.tag{display:inline-block;padding:2px 8px;border-radius:6px;background:#1d263d;color:#bcd;
font-size:11.5px}
.bar{position:relative;background:#0e1424;border:1px solid var(--line);border-radius:6px;
height:18px;min-width:120px;overflow:hidden}
.bar-fill{height:100%;background:var(--c);opacity:.85}
.bar-num{position:absolute;right:6px;top:0;font-size:11px;line-height:18px;color:var(--ink)}
ul{margin:6px 0 0;padding-left:18px}li{margin:3px 0}
.warn h3{color:#ffb454}
.graph{width:100%;height:auto;background:#0a0f1c;border:1px solid var(--line);border-radius:10px}
.glabel{fill:#aeb9d4;font-size:10px;text-anchor:middle}
.gnode:hover circle{stroke:#fff}
.legendbar{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:10px;font-size:11.5px;color:var(--mut)}
.lg{display:inline-flex;align-items:center;gap:5px}.lg i{width:11px;height:11px;border-radius:3px;display:inline-block}
.timeline{display:flex;gap:10px;align-items:flex-end;height:170px;padding:8px 4px;overflow-x:auto}
.tl-col{display:flex;flex-direction:column;align-items:center;gap:4px;min-width:46px}
.tl-bar{width:26px;background:linear-gradient(#3ddc84,#4aa3df);border-radius:5px 5px 0 0}
.tl-it{color:var(--mut);font-size:11px}.tl-n{font-size:11px;font-weight:700}
.scroll{max-height:380px;overflow:auto;border:1px solid var(--line);border-radius:8px}
.spark{width:300px;height:46px;background:#0a0f1c;border-radius:6px}
.star{color:#3ddc84;font-size:11px;font-weight:700}
.arow{display:grid;grid-template-columns:160px 1fr 1.2fr;gap:12px;align-items:center;margin:7px 0}
.aname{font-weight:600}.atypes{font-size:11.5px}
.abar{position:relative;background:#0e1424;border:1px solid var(--line);border-radius:6px;height:20px}
.abar-fill{height:100%;background:linear-gradient(90deg,#4aa3df,#3ddc84);border-radius:6px}
.abar span{position:absolute;right:8px;top:0;line-height:20px;font-size:11px}
.foot{color:var(--mut);font-size:12px;padding:16px 24px;border-top:1px solid var(--line)}
/* mobile: stack the header, let wide tables scroll, keep the knowledge graph tall & readable */
@media(max-width:600px){
  .top{flex-direction:column;align-items:flex-start;gap:6px;padding:12px 16px}
  .meta{font-size:11.5px}
  .kpis{padding:12px 16px;gap:10px;grid-template-columns:repeat(auto-fit,minmax(108px,1fr))}
  .kpi-val{font-size:20px}
  .ladder{padding:8px 16px;gap:4px}.ladder span{flex-basis:88px;min-width:78px;padding:7px 6px}
  .nav{padding:8px 12px 0;flex-wrap:nowrap;overflow-x:auto}
  .navbtn{padding:8px 12px;font-size:12px}
  main{padding:12px 16px 32px}.panel{padding:14px}
  .tbl{display:block;overflow-x:auto;white-space:nowrap;-webkit-overflow-scrolling:touch}
  .arow{grid-template-columns:1fr;gap:4px}.abar{height:16px}
  .spark{width:210px}.graph{min-height:300px}
}
"""
