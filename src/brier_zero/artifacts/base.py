"""Shared HTML shell for all Brier Zero artifacts.

Every artifact is a single self-contained file: inline CSS/JS, no external
requests, no backend, opens in any browser, light/dark aware. This module
owns the shell, the 4-layer progressive-disclosure pattern (BZ-101), and
the small inline-SVG chart helpers the renderers share.
"""

from __future__ import annotations

import html
import json
from datetime import datetime


def esc(text: object) -> str:
    return html.escape(str(text), quote=True)


_CSS = """
:root {
  --bg: #ffffff; --fg: #1a1d23; --muted: #5b6472; --line: #e3e6ea;
  --card: #f6f7f9; --accent: #3d5afe; --good: #1a7f37; --warn: #b45309;
  --bad: #b42318; --band: rgba(61, 90, 254, .12);
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #101318; --fg: #e6e9ee; --muted: #9aa4b2; --line: #2a3038;
    --card: #181d24; --accent: #7c93ff; --good: #4ade80; --warn: #fbbf24;
    --bad: #f87171; --band: rgba(124, 147, 255, .16);
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; padding: 2rem 1rem 4rem; background: var(--bg); color: var(--fg);
  font: 16px/1.55 -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}
main { max-width: 880px; margin: 0 auto; }
h1 { font-size: 1.5rem; line-height: 1.3; margin: 0 0 .25rem; }
h2 { font-size: 1.1rem; margin: 1.5rem 0 .5rem; }
h3 { font-size: .95rem; margin: 1rem 0 .35rem; }
p { margin: .4rem 0; }
.muted { color: var(--muted); font-size: .85rem; }
.card { background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 1rem 1.25rem; margin: .75rem 0; }
.headline { display: flex; flex-wrap: wrap; gap: 1rem; align-items: baseline; }
.prob { font-size: 3rem; font-weight: 700; letter-spacing: -.02em; }
.badge { display: inline-block; padding: .15rem .6rem; border-radius: 999px; font-size: .75rem; font-weight: 600; border: 1px solid var(--line); }
.badge.good { color: var(--good); border-color: var(--good); }
.badge.warn { color: var(--warn); border-color: var(--warn); }
.badge.bad  { color: var(--bad);  border-color: var(--bad); }
details.layer { border: 1px solid var(--line); border-radius: 10px; margin: .75rem 0; background: var(--card); }
details.layer > summary {
  cursor: pointer; padding: .8rem 1.25rem; font-weight: 600; list-style: none;
  display: flex; justify-content: space-between; align-items: center;
}
details.layer > summary::after { content: "+"; color: var(--muted); font-weight: 400; }
details.layer[open] > summary::after { content: "\\2212"; }
details.layer > .inner { padding: 0 1.25rem 1rem; border-top: 1px solid var(--line); overflow-x: auto; }
table { border-collapse: collapse; width: 100%; font-size: .85rem; }
th, td { text-align: left; padding: .45rem .6rem; border-bottom: 1px solid var(--line); vertical-align: top; }
th { color: var(--muted); font-weight: 600; }
.scroll { overflow-x: auto; }
.claim { border-bottom: 1px dashed var(--accent); cursor: help; position: relative; }
.claim .tip {
  visibility: hidden; opacity: 0; transition: opacity .15s; position: absolute;
  left: 0; top: 1.6em; z-index: 10; width: min(420px, 80vw); background: var(--card);
  color: var(--fg); border: 1px solid var(--line); border-radius: 8px;
  padding: .6rem .8rem; font-size: .8rem; box-shadow: 0 6px 24px rgba(0,0,0,.18);
}
.claim:hover .tip, .claim:focus-within .tip { visibility: visible; opacity: 1; }
.heat { display: flex; gap: 4px; flex-wrap: wrap; }
.heat .cell { width: 84px; padding: .5rem .4rem; border-radius: 8px; font-size: .72rem; text-align: center; color: #fff; }
input[type=range] { width: 100%; accent-color: var(--accent); }
.footer { margin-top: 3rem; font-size: .75rem; color: var(--muted); border-top: 1px solid var(--line); padding-top: .75rem; }
svg text { fill: var(--muted); font-size: 11px; }
svg .axis { stroke: var(--line); }
svg .series { stroke: var(--accent); fill: none; stroke-width: 2; }
svg .area { fill: var(--band); stroke: none; }
svg .mapline { stroke: var(--warn); stroke-dasharray: 5 4; stroke-width: 1.5; }
"""

_LAYER_JS = """
// Progressive disclosure layer manager: deep-linkable (#layer-3 opens 1..3),
// and each expansion is recorded for the audit trail (layer 4).
(function () {
  var opened = [];
  document.querySelectorAll('details.layer').forEach(function (d) {
    d.addEventListener('toggle', function () {
      if (d.open) opened.push({layer: d.dataset.layer, at: new Date().toISOString()});
      var log = document.getElementById('disclosure-log');
      if (log) log.textContent = JSON.stringify(opened, null, 2);
    });
  });
  var m = location.hash.match(/^#layer-([1-4])$/);
  if (m) {
    document.querySelectorAll('details.layer').forEach(function (d) {
      if (+d.dataset.layer <= +m[1]) d.open = true;
    });
  }
})();
"""


def page(title: str, body: str, subtitle: str = "", extra_css: str = "", extra_js: str = "") -> str:
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")
    sub = f'<p class="muted">{esc(subtitle)}</p>' if subtitle else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<style>{_CSS}{extra_css}</style>
</head>
<body>
<main>
<h1>{esc(title)}</h1>
{sub}
{body}
<div class="footer">Brier Zero artifact &middot; self-contained &middot; generated {generated} &middot; no backend required</div>
</main>
<script>{_LAYER_JS}{extra_js}</script>
</body>
</html>
"""


def layer(num: int, title: str, inner_html: str, open_: bool = False) -> str:
    """One progressive-disclosure layer (BZ-101). Layer 1 renders open and
    un-collapsible; layers 2-4 are <details> blocks."""
    if num == 1:
        return f'<section class="card" data-layer="1"><h2>{esc(title)}</h2>{inner_html}</section>'
    op = " open" if open_ else ""
    return (
        f'<details class="layer" data-layer="{num}"{op}>'
        f'<summary>Layer {num} &mdash; {esc(title)}</summary>'
        f'<div class="inner">{inner_html}</div></details>'
    )


def risk_badge(label: str, tone: str) -> str:
    return f'<span class="badge {esc(tone)}">{esc(label)}</span>'


# ---------------------------------------------------------------- SVG helpers

def line_chart(
    points: list[tuple[datetime, float]],
    width: int = 780,
    height: int = 220,
    map_claim: float | None = None,
    band: tuple[float, float] | None = None,
) -> str:
    """Inline-SVG probability chart: price series, optional official-map
    reference line, optional fidelity variance band."""
    if not points:
        return '<p class="muted">No price history yet.</p>'
    pad = 34
    xs = [p[0].timestamp() for p in points]
    x0, x1 = min(xs), max(xs)
    span = (x1 - x0) or 1.0

    def X(ts: float) -> float:
        return pad + (ts - x0) / span * (width - 2 * pad)

    def Y(p: float) -> float:
        return pad + (1 - p) * (height - 2 * pad)

    poly = " ".join(f"{X(t):.1f},{Y(v):.1f}" for t, v in ((x, v) for x, v in zip(xs, (p[1] for p in points))))
    parts = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="probability over time">']
    for gy in (0.0, 0.25, 0.5, 0.75, 1.0):
        parts.append(f'<line class="axis" x1="{pad}" y1="{Y(gy):.1f}" x2="{width-pad}" y2="{Y(gy):.1f}"/>')
        parts.append(f'<text x="4" y="{Y(gy)+4:.1f}">{int(gy*100)}%</text>')
    if band is not None:
        lo, hi = band
        parts.append(
            f'<rect class="area" x="{pad}" y="{Y(hi):.1f}" width="{width-2*pad}" '
            f'height="{max(1.0, Y(lo)-Y(hi)):.1f}"/>'
        )
    if map_claim is not None:
        parts.append(f'<line class="mapline" x1="{pad}" y1="{Y(map_claim):.1f}" x2="{width-pad}" y2="{Y(map_claim):.1f}"/>')
        parts.append(f'<text x="{width-pad-150}" y="{Y(map_claim)-6:.1f}">official map: {int(map_claim*100)}%</text>')
    parts.append(f'<polyline class="series" points="{poly}"/>')
    last_x, last_y = X(xs[-1]), Y(points[-1][1])
    parts.append(f'<circle cx="{last_x:.1f}" cy="{last_y:.1f}" r="4" fill="currentColor"/>')
    parts.append("</svg>")
    return "".join(parts)


def timeline_svg(events: list[tuple[datetime, str]], anchor: datetime, width: int = 780) -> str:
    """Event timeline relative to an anchor date (BZ-103)."""
    if not events:
        return '<p class="muted">No dated events.</p>'
    events = sorted(events, key=lambda e: e[0])
    height = 40 + 34 * len(events)
    ts = [e[0].timestamp() for e in events] + [anchor.timestamp()]
    x0, x1 = min(ts), max(ts)
    span = (x1 - x0) or 1.0
    pad = 20

    def X(t: float) -> float:
        return pad + (t - x0) / span * (width - 2 * pad)

    parts = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="event timeline">']
    axis_y = height - 22
    parts.append(f'<line class="axis" x1="{pad}" y1="{axis_y}" x2="{width-pad}" y2="{axis_y}"/>')
    ax = X(anchor.timestamp())
    parts.append(f'<line class="mapline" x1="{ax:.1f}" y1="12" x2="{ax:.1f}" y2="{axis_y}"/>')
    parts.append(f'<text x="{min(ax+4, width-160):.1f}" y="12">market created {anchor.date().isoformat()}</text>')
    for i, (when, label) in enumerate(events):
        x, y = X(when.timestamp()), 26 + 34 * i
        parts.append(f'<circle cx="{x:.1f}" cy="{axis_y}" r="4" fill="currentColor"/>')
        parts.append(f'<line class="axis" x1="{x:.1f}" y1="{y+4}" x2="{x:.1f}" y2="{axis_y}"/>')
        tx = min(x + 6, width - 300)
        parts.append(f'<text x="{tx:.1f}" y="{y}">{esc(when.date().isoformat())} &mdash; {esc(label[:60])}</text>')
    parts.append("</svg>")
    return "".join(parts)


def heatmap(cells: list[tuple[str, float]]) -> str:
    """Color-coded risk heatmap: value 0 (good/green) .. 1 (bad/red)."""
    out = ['<div class="heat">']
    for label, v in cells:
        v = min(1.0, max(0.0, v))
        hue = 130 * (1 - v)  # green -> red
        out.append(
            f'<div class="cell" style="background:hsl({hue:.0f} 55% 38%)">'
            f'{esc(label)}<br><strong>{v:.0%}</strong></div>'
        )
    out.append("</div>")
    return "".join(out)


def json_block(data: object) -> str:
    return f'<pre class="scroll">{esc(json.dumps(data, indent=2, default=str))}</pre>'
