"""BZ-303: the Brier Zero site — four A/B hero variants, one editorial design.

Design language ("the midnight briefing"): committed dark situation-room
palette (ink blue-black ground, phosphor-amber accent), Newsreader serif as
the briefing voice (embedded as data URIs — no CDN), monospace for data and
eyebrows, and the product thesis as the hero graphic: the map line and the
territory line pulling apart. Everything is still one self-contained file
per variant: no external requests, no backend, works as an email attachment.

`render_all` returns the sticky A/B router plus the four variant pages;
`render_artifact_preview` returns a skeleton-less version for artifact hosts.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from pathlib import Path

from .base import esc

_QUALIFY_QUESTIONS = [
    ("leak", "What is the most critical project at your company that you suspect is "
             "‘failing in secret’?"),
    ("map", "Ask your lead to restate your top initiative's success criteria. "
            "Did their answer surprise you?"),
    ("artifact", "How do you currently share prediction models or forecasts with your board?"),
    ("fidelity", "What is the one assumption in your current roadmap that nobody has validated?"),
]


@dataclass(frozen=True)
class HeroVariant:
    key: str
    name: str
    headline: str
    subline: str
    cta: str


VARIANTS = [
    HeroVariant(
        key="a", name="The Apple Case",
        headline="Know what your employees know. Before they leak it.",
        subline="Your people see failure years before your dashboard does. Brier Zero gives "
                "them a pseudonymous way to price it into an internal market — you get the "
                "signal, the journalist doesn't.",
        cta="Request a pilot briefing",
    ),
    HeroVariant(
        key="b", name="Map is Not Territory",
        headline="Your dashboard says 90%. The market says 35%.",
        subline="Brier Zero runs an internal prediction market traded only by research "
                "agents — and calibrated by the people who actually know. It finds the gap "
                "between your roadmap and reality before the write-off, and before the leak.",
        cta="Request a pilot briefing",
    ),
    HeroVariant(
        key="c", name="Artifact-Native",
        headline="Intelligence should be an artifact, not a conversation.",
        subline="Every market produces one self-contained interactive file — executive "
                "summary to raw audit trail in four clicks. Email it to your board. Archive "
                "it for compliance. No login. No platform.",
        cta="Open a live artifact",
    ),
    HeroVariant(
        key="d", name="Calibrated Forecasting Engine",
        headline="The prediction market for people who can't trust their own roadmap.",
        subline="Autonomous research agents trade probabilities on your real questions, are "
                "scored by Brier score, and get better every time they're wrong.",
        cta="Join the pilot waitlist",
    ),
]

_ASSETS = Path(__file__).parent / "assets"


def _font_css() -> str:
    """Newsreader as data URIs — the site must not phone home for fonts."""
    def data_uri(name: str) -> str:
        raw = (_ASSETS / name).read_bytes()
        return "data:font/woff2;base64," + base64.b64encode(raw).decode()

    return f"""
@font-face {{
  font-family: 'Newsreader';
  font-style: normal;
  font-weight: 400 700;
  font-display: swap;
  src: url({data_uri('newsreader-latin.woff2')}) format('woff2');
}}
@font-face {{
  font-family: 'Newsreader';
  font-style: italic;
  font-weight: 500;
  font-display: swap;
  src: url({data_uri('newsreader-latin-italic.woff2')}) format('woff2');
}}
"""


# --- Analytics -------------------------------------------------------------
# PostHog funnel for the DEPLOYED marketing pages only. The self-contained
# artifacts and the claude.ai artifact-preview renders never get this (they'd
# be CSP-blocked and must stay dependency-free).
#
# Client API key for the "Uptick HQ" PostHog project (id 500056). Public by
# design (it's a client-side ingest key). Swap here to retarget the funnel.
POSTHOG_TOKEN = "phc_uueVktK2gaALRxPpXzdMWE6PYZiNgGhEeE7qLoMUJviP"
POSTHOG_HOST = "https://us.i.posthog.com"

# Load array.js async, init on load, fire a variant-tagged pageview. All other
# capture() calls are user-triggered (post-load), so the guarded cap() helpers
# in the page scripts are always safe.
_PH_LOADER = """<script>
(function(){
  try {
    var s = document.createElement('script');
    s.async = true;
    s.src = '__HOST__'.replace('.i.posthog.com', '-assets.i.posthog.com') + '/static/array.js';
    s.onload = function(){
      posthog.init('__TOKEN__', {api_host: '__HOST__', person_profiles: 'identified_only'});
      try {
        var v = (document.body && document.body.dataset) ? document.body.dataset.variant : undefined;
        posthog.capture('$pageview', {variant: v});
      } catch(e) {}
    };
    document.head.appendChild(s);
  } catch(e) {}
})();
</script>"""


def _analytics() -> str:
    return _PH_LOADER.replace("__TOKEN__", POSTHOG_TOKEN).replace("__HOST__", POSTHOG_HOST)


# The palette is a committed dark theme: this product is read at midnight.
# Amber is the lone accent (dossier stamp / terminal phosphor); green and
# red are semantic only and never decorate.
_SITE_CSS = """
:root {
  --ink: #0b0e14; --panel: #121826; --panel-2: #0f141d; --line: #26303f;
  --text: #e3e9f2; --dim: #8a96a8; --amber: #e5a13c; --amber-dim: #9c7434;
  --good: #5bc49a; --bad: #e0685c;
  --serif: 'Newsreader', Georgia, 'Times New Roman', serif;
  --sans: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  --mono: ui-monospace, "SF Mono", "Cascadia Code", Menlo, Consolas, monospace;
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0; background: var(--ink); color: var(--text);
  font: 16px/1.65 var(--sans);
}
main { max-width: 960px; margin: 0 auto; padding: 0 1.25rem 5rem; }
a { color: var(--amber); text-decoration: none; }
a:hover { text-decoration: underline; }
:focus-visible { outline: 2px solid var(--amber); outline-offset: 3px; border-radius: 2px; }

.topbar {
  display: flex; justify-content: space-between; align-items: center;
  padding: 1.1rem 0; border-bottom: 1px solid var(--line); margin-bottom: 4rem;
}
.wordmark { font: 600 .85rem var(--mono); letter-spacing: .22em; color: var(--text); }
.wordmark em { color: var(--amber); font-style: normal; }
.topbar a.cta-link { font: 500 .78rem var(--mono); letter-spacing: .08em; }

.eyebrow {
  font: 500 .7rem var(--mono); letter-spacing: .2em; text-transform: uppercase;
  color: var(--amber); margin: 0 0 1rem;
}
.hero h1 {
  font: 600 clamp(2.5rem, 6vw, 4.1rem)/1.07 var(--serif);
  letter-spacing: -.015em; margin: 0 0 1.25rem; max-width: 20ch; text-wrap: balance;
}
.hero .sub { font-size: 1.12rem; color: var(--dim); max-width: 58ch; margin: 0 0 2rem; }
.cta-row { display: flex; gap: .9rem; flex-wrap: wrap; margin-bottom: 3.5rem; }
.btn {
  display: inline-block; font: 600 .85rem var(--mono); letter-spacing: .04em;
  padding: .85rem 1.5rem; border-radius: 3px; cursor: pointer; border: 1px solid transparent;
}
.btn.solid { background: var(--amber); color: var(--ink); }
.btn.solid:hover { background: #f0b458; text-decoration: none; }
.btn.ghost { border-color: var(--line); color: var(--text); background: transparent; }
.btn.ghost:hover { border-color: var(--amber-dim); text-decoration: none; }

.chart-frame {
  background: var(--panel-2); border: 1px solid var(--line); border-radius: 4px;
  padding: 1.25rem 1.25rem .75rem; overflow-x: auto;
}
.chart-frame .cap {
  font: 500 .68rem var(--mono); letter-spacing: .14em; text-transform: uppercase;
  color: var(--dim); margin: .5rem 0 0;
}
svg .grid { stroke: var(--line); stroke-width: 1; }
svg .lbl { font: 500 10.5px var(--mono); letter-spacing: .08em; fill: var(--dim); }
svg .lbl.amber { fill: var(--amber); }
svg .mapline { stroke: var(--dim); stroke-width: 1.5; stroke-dasharray: 6 5; fill: none; }
svg .market { stroke: var(--amber); stroke-width: 2.25; fill: none;
  stroke-dasharray: 1400; stroke-dashoffset: 1400; animation: draw 2.4s ease-out .4s forwards; }
svg .gapfill { fill: rgba(229, 161, 60, .09); opacity: 0; animation: appear .9s ease-out 2.4s forwards; }
svg .delta { opacity: 0; animation: appear .7s ease-out 2.7s forwards; }
@keyframes draw { to { stroke-dashoffset: 0; } }
@keyframes appear { to { opacity: 1; } }

.ticker-wrap {
  border-block: 1px solid var(--line); margin: 4.5rem 0; padding: .7rem 0;
  overflow: hidden; white-space: nowrap;
}
.ticker { display: inline-block; animation: tick 46s linear infinite; }
.ticker-wrap:hover .ticker { animation-play-state: paused; }
.ticker span { font: 500 .74rem var(--mono); letter-spacing: .06em; color: var(--dim); margin-right: 3.5rem; }
.ticker span b { color: var(--amber); font-weight: 600; }
@keyframes tick { from { transform: translateX(0); } to { transform: translateX(-50%); } }

section.block { margin: 5rem 0; }
.rule-head { display: flex; align-items: center; gap: 1rem; margin-bottom: 2.25rem; }
.rule-head::after { content: ""; flex: 1; height: 1px; background: var(--line); }
.block h2 { font: 600 1.9rem/1.2 var(--serif); letter-spacing: -.01em; margin: 0 0 .6rem; text-wrap: balance; }
.block > p.lede { color: var(--dim); max-width: 62ch; margin: 0 0 2rem; }

.gaps { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 1px; background: var(--line); border: 1px solid var(--line); }
.gaps article { background: var(--panel-2); padding: 1.6rem 1.4rem; }
.gaps h3 { font: 500 .7rem var(--mono); letter-spacing: .18em; color: var(--amber); margin: 0 0 .8rem; }
.gaps p { margin: 0; color: var(--dim); font-size: .95rem; }
.gaps p strong { color: var(--text); font-weight: 600; }

.steps { list-style: none; margin: 0; padding: 0; display: grid; gap: 0; counter-reset: step; }
.steps li {
  display: grid; grid-template-columns: 3.5rem 1fr; gap: 1.25rem;
  padding: 1.5rem 0; border-top: 1px solid var(--line);
}
.steps li:last-child { border-bottom: 1px solid var(--line); }
.steps .num { font: 500 1.5rem var(--serif); font-style: italic; color: var(--amber); }
.steps h3 { font: 600 1.15rem var(--serif); margin: 0 0 .3rem; display: flex; gap: .75rem; align-items: baseline; flex-wrap: wrap; }
.steps p { margin: 0; color: var(--dim); font-size: .95rem; max-width: 62ch; }
.chip {
  font: 600 .62rem var(--mono); letter-spacing: .16em; color: var(--dim);
  border: 1px solid var(--line); border-radius: 2px; padding: .15rem .5rem; white-space: nowrap;
}

.artifact-embed iframe {
  width: 100%; height: 660px; border: 1px solid var(--line); border-radius: 4px;
  background: #fff;
}
.artifact-points { display: flex; gap: 2rem; flex-wrap: wrap; margin-top: 1.25rem; }
.artifact-points div { font: 500 .74rem var(--mono); letter-spacing: .08em; color: var(--dim); }
.artifact-points b { color: var(--text); }

.tenets { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 2rem 3rem; }
.tenets h3 { font: 600 1.05rem var(--serif); margin: 0 0 .35rem; }
.tenets p { margin: 0; color: var(--dim); font-size: .92rem; }

form.clearance { background: var(--panel); border: 1px solid var(--line); border-radius: 4px; padding: 2rem; display: grid; gap: 1.4rem; }
form.clearance label { display: grid; gap: .5rem; }
form.clearance label > span { font: 600 .95rem var(--serif); }
form.clearance input, form.clearance textarea {
  background: var(--ink); border: 1px solid var(--line); border-radius: 3px;
  color: var(--text); font: 400 .95rem var(--sans); padding: .7rem .8rem; width: 100%;
}
form.clearance input:focus, form.clearance textarea:focus { border-color: var(--amber-dim); outline: none; }
form.clearance .fine { font-size: .8rem; color: var(--dim); margin: 0; }

.footer {
  margin-top: 6rem; padding-top: 1.5rem; border-top: 1px solid var(--line);
  display: flex; justify-content: space-between; gap: 1rem; flex-wrap: wrap;
}
.footer .motto { font: 500 .72rem var(--mono); letter-spacing: .22em; color: var(--dim); }
.footer .note { font-size: .78rem; color: var(--dim); max-width: 46ch; }
.footer .note i { font-family: var(--serif); }

@media (prefers-reduced-motion: reduce) {
  svg .market { stroke-dasharray: none; stroke-dashoffset: 0; animation: none; }
  svg .gapfill, svg .delta { opacity: 1; animation: none; }
  .ticker { animation: none; }
  html { scroll-behavior: auto; }
}
"""

_TRACK_JS = """
(function () {
  var v = document.body.dataset.variant;
  function cap(ev, props) { try { if (window.posthog && posthog.capture) posthog.capture(ev, props || {}); } catch (e) {} }
  var form = document.getElementById('waitlist');
  if (!form) return;
  form.addEventListener('submit', function (ev) {
    ev.preventDefault();
    var data = {variant: v};
    new FormData(form).forEach(function (val, key) { data[key] = val; });
    try { if (data.email && window.posthog && posthog.identify) posthog.identify(data.email, {email: data.email}); } catch (e) {}
    cap('waitlist_signup', data);
    form.innerHTML = '<p style="font:600 1.05rem var(--serif)">\\u2713 Logged. We read every one \\u2014 expect a note from a human, not a drip sequence.</p>';
  });
})();
"""

_ROUTER_JS_TEMPLATE = """
(function () {
  var variants = %(variants)s;
  var params = new URLSearchParams(location.search);
  var forced = params.get('v');
  var v = forced && variants.indexOf(forced) >= 0 ? forced : null;
  try {
    if (!v) v = localStorage.getItem('bz_variant');
    if (!v || variants.indexOf(v) < 0) {
      v = variants[Math.floor(Math.random() * variants.length)];
    }
    localStorage.setItem('bz_variant', v);
  } catch (e) { v = v || variants[0]; }
  location.replace('landing-' + v + '.html' + location.hash);
})();
"""

# Demo numbers the hero chart draws: the dashboard's flat 90% vs the agent
# market walking down to 35%.
_MARKET_PATH = [
    (0.00, 0.78), (0.11, 0.74), (0.22, 0.71), (0.33, 0.64), (0.44, 0.60),
    (0.55, 0.54), (0.66, 0.47), (0.78, 0.41), (0.89, 0.37), (1.00, 0.35),
]


def _divergence_chart() -> str:
    w, h, pad = 840, 300, 42
    def x(f: float) -> float:
        return pad + f * (w - 2 * pad)
    def y(p: float) -> float:
        return pad + (1 - p) * (h - 2 * pad)

    map_y = y(0.90)
    pts = " ".join(f"{x(f):.1f},{y(p):.1f}" for f, p in _MARKET_PATH)
    gap_poly = (
        pts + " " + " ".join(f"{x(f):.1f},{map_y:.1f}" for f, _ in reversed(_MARKET_PATH))
    )
    grid = "".join(
        f'<line class="grid" x1="{pad}" y1="{y(g):.1f}" x2="{w-pad}" y2="{y(g):.1f}"/>'
        f'<text class="lbl" x="6" y="{y(g)+4:.1f}">{int(g*100)}%</text>'
        for g in (0.2, 0.4, 0.6, 0.8, 1.0)
    )
    end_x, end_y = x(1.0), y(0.35)
    return f"""
<svg viewBox="0 0 {w} {h}" role="img"
     aria-label="Chart: the internal dashboard holds at 90 percent while the agent market falls to 35 percent — a 55 point gap.">
  {grid}
  <polygon class="gapfill" points="{gap_poly}"/>
  <line class="mapline" x1="{pad}" y1="{map_y:.1f}" x2="{w-pad}" y2="{map_y:.1f}"/>
  <text class="lbl" x="{pad}" y="{map_y-9:.1f}">THE MAP — program dashboard · 90%</text>
  <polyline class="market" points="{pts}"/>
  <circle class="delta" cx="{end_x:.1f}" cy="{end_y:.1f}" r="4" fill="var(--amber)"/>
  <text class="lbl amber delta" x="{end_x-215:.1f}" y="{end_y+26:.1f}">THE TERRITORY — agent market · 35%</text>
  <g class="delta">
    <line class="grid" x1="{end_x:.1f}" y1="{map_y:.1f}" x2="{end_x:.1f}" y2="{end_y:.1f}" stroke-dasharray="3 3"/>
    <text class="lbl amber" x="{end_x-52:.1f}" y="{(map_y+end_y)/2:.1f}">Δ 55 PTS</text>
  </g>
</svg>"""


_TICKER_ITEMS = [
    ("SURPRISE ASSUMPTION", "‘thermal validation passed’ appears nowhere in the official map"),
    ("MAP STALE", "dashboard dated 120 days before the newest strong evidence"),
    ("DIVERGENCE 55 PTS", "gap analysis auto-generated — what does the map not know?"),
    ("PSEUDONYMOUS SIGNAL", "verified employee · −9 pts · identity mathematically stripped"),
    ("SKILL AUDIT", "‘press-scan’ heuristic flagged dead weight after 3 resolutions"),
    ("MAP FIDELITY 0/100", "displayed confidence widened — a confident agent with a bad map is dangerous"),
]


def _ticker() -> str:
    seq = "".join(f"<span><b>{esc(k)}</b> — {esc(v)}</span>" for k, v in _TICKER_ITEMS)
    # Content duplicated once so the -50% translate loops seamlessly.
    return f'<div class="ticker-wrap" aria-hidden="true"><div class="ticker">{seq}{seq}</div></div>'


def _body(variant: HeroVariant, demo_artifact_html: str,
          waitlist_endpoint: str, contact_email: str) -> str:
    questions = "".join(
        f'<label><span>{esc(q)}</span><textarea name="{esc(key)}" rows="2"></textarea></label>'
        for key, q in _QUALIFY_QUESTIONS
    )
    endpoint_attrs = (
        f' action="{esc(waitlist_endpoint)}" method="post" data-endpoint="1"'
        if waitlist_endpoint else f' data-mailto="{esc(contact_email)}"'
    )
    srcdoc = esc(demo_artifact_html)
    return f"""
<main>
<nav class="topbar">
  <span class="wordmark">BRIER<em>//</em>ZERO</span>
  <a class="cta-link" href="#clearance">REQUEST BRIEFING →</a>
</nav>

<header class="hero">
  <p class="eyebrow">Agent-only prediction markets · map/territory detection</p>
  <h1>{esc(variant.headline)}</h1>
  <p class="sub">{esc(variant.subline)}</p>
  <div class="cta-row">
    <a class="btn solid" href="#clearance">{esc(variant.cta)}</a>
    <a class="btn ghost" href="#artifact">Open a live artifact ↓</a>
  </div>
  <div class="chart-frame">
    {_divergence_chart()}
    <p class="cap">Live demo market · “Will Apple ship a production passenger car by December 31, 2028?”</p>
  </div>
</header>

{_ticker()}

<section class="block">
  <div class="rule-head"><p class="eyebrow" style="margin:0">Why this exists</p></div>
  <h2>Weak teams fail loudly. Strong teams fail quietly.</h2>
  <p class="lede">A confident wrong assumption doesn't crash — it propagates across three
  quarters of planning before anyone inspects it. Three gaps let it happen.</p>
  <div class="gaps">
    <article>
      <h3>The Leak Gap</h3>
      <p>Your best people know a project is failing <strong>years</strong> before your
      dashboard does. With no safe internal channel, that truth goes to a journalist —
      for clout. You lose the narrative. They gain nothing but risk.</p>
    </article>
    <article>
      <h3>The Map Gap</h3>
      <p>Roadmaps, dashboards, status decks — every org runs on maps. The more capable
      the team, the more dangerous a stale map becomes, because <strong>nobody checks it
      against the territory</strong> until the write-off.</p>
    </article>
    <article>
      <h3>The Artifact Gap</h3>
      <p>The one signal you needed is buried on page forty of a chat transcript.
      Intelligence that can't be <strong>opened, clicked, and forwarded</strong> doesn't
      change decisions.</p>
    </article>
  </div>
</section>

<section class="block">
  <div class="rule-head"><p class="eyebrow" style="margin:0">How it works</p></div>
  <h2>Five moves from question to calibrated truth.</h2>
  <ol class="steps">
    <li><span class="num">i</span><div>
      <h3>You ask a real question</h3>
      <p>“Will the vehicle program ship by 2028?” — with resolution criteria a lawyer
      could referee. Vague markets are rejected at creation.</p>
    </div></li>
    <li><span class="num">ii</span><div>
      <h3>The agent restates it back <span class="chip">RESTATEMENT PROTOCOL</span></h3>
      <p>Before a single trade, the research agent paraphrases your question and lists
      every assumption it's trading on. If one surprises you, the market is flagged —
      a surprised founder is a gap caught early, for free.</p>
    </div></li>
    <li><span class="num">iii</span><div>
      <h3>Research agents trade — humans never do <span class="chip">BRIER-SCORED</span></h3>
      <p>Agents weigh source credibility, pool evidence, and price the question.
      Reputation-weighted, difficulty-adjusted, no gambling surface, no regulatory
      ambiguity. The score is a research metric, not a payout.</p>
    </div></li>
    <li><span class="num">iv</span><div>
      <h3>Your people whisper <span class="chip">PSEUDONYMOUS · CAPPED ±15 PTS</span></h3>
      <p>SSO proves employment; HMAC strips identity. A whisper becomes a bounded
      probability signal — the market gets the truth, nobody gets a name, and no single
      voice can own the price.</p>
    </div></li>
    <li><span class="num">v</span><div>
      <h3>Every resolution audits the machine <span class="chip">META-CALIBRATION</span></h3>
      <p>After each market resolves, every research skill that touched it is scored.
      Methods that stop predicting get flagged as dead weight and down-weighted. The
      engine distrusts its own map, too.</p>
    </div></li>
  </ol>
</section>

<section class="block artifact-embed" id="artifact">
  <div class="rule-head"><p class="eyebrow" style="margin:0">The deliverable</p></div>
  <h2>Not a dashboard. A file.</h2>
  <p class="lede">This is a real market artifact, embedded live. Four layers of
  progressive disclosure — headline probability for the board, raw audit trail for the
  regulator. It opens in any browser, forever, with no login. Click through it.</p>
  <iframe srcdoc="{srcdoc}" title="Live Brier Zero demo artifact" loading="lazy"></iframe>
  <div class="artifact-points">
    <div><b>SELF-CONTAINED</b> · zero external requests</div>
    <div><b>HOVER-TO-VERIFY</b> · every claim shows its exact source</div>
    <div><b>FIDELITY-WEIGHTED</b> · confidence shown as a band, not a point</div>
  </div>
</section>

<section class="block">
  <div class="rule-head"><p class="eyebrow" style="margin:0">Built for orgs that can't talk</p></div>
  <div class="tenets">
    <div><h3>No human trading, ever.</h3>
      <p>No pump-and-dump, no insider-trading surface, no gambling mechanics. Agent-only
      by design — which is also why it's fast.</p></div>
    <div><h3>Pseudonymity is math, not policy.</h3>
      <p>HMAC-SHA256 pseudonyms are stable inside one market and unlinkable across
      markets. We couldn't dox your engineers if we were subpoenaed to.</p></div>
    <div><h3>The artifact is yours.</h3>
      <p>Take the file and leave, any day. The thing you'd miss is the ongoing
      calibration that produces the next one.</p></div>
    <div><h3>Honesty about our own map.</h3>
      <p>A market with low map fidelity is displayed as high variance even when agents
      are confident. Epistemic humility, enforced in the renderer.</p></div>
  </div>
</section>

<section class="block" id="clearance">
  <div class="rule-head"><p class="eyebrow" style="margin:0">Request clearance</p></div>
  <h2>Four questions. If none of them sting, you don't need us yet.</h2>
  <form id="waitlist" class="clearance"{endpoint_attrs}>
    <label><span>Work email</span><input type="email" name="email" required></label>
    {questions}
    <p><button type="submit" class="btn solid">{esc(variant.cta)}</button></p>
    <p class="fine">Answers stay between us — they calibrate the pilot, not a CRM
    sequence. Design-partner pilots are limited to five organizations this fall.</p>
  </form>
</section>

<footer class="footer">
  <span class="motto">THE MAP IS NOT THE TERRITORY.</span>
  <p class="note"><i>Brier score</i>, n. — the mean squared error of a probabilistic
  forecast. Zero is perfect. We're named after the direction of travel.</p>
</footer>
</main>
"""


def render_variant(
    variant: HeroVariant,
    demo_artifact_html: str,
    waitlist_endpoint: str = "",
    contact_email: str = "hello@brier.zero",
) -> str:
    body = _body(variant, demo_artifact_html, waitlist_endpoint, contact_email)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="dark">
<meta name="description" content="{esc(variant.subline)}">
<title>Brier Zero — the Map/Territory Detection Engine</title>
{_analytics()}
<style>{_font_css()}{_SITE_CSS}</style>
</head>
<body data-variant="{variant.key}">
{body}
<script>{_TRACK_JS}</script>
</body>
</html>
"""


def render_artifact_preview(
    demo_artifact_html: str,
    variant: HeroVariant | None = None,
    contact_email: str = "hello@brier.zero",
) -> str:
    """Skeleton-less page for artifact hosts that wrap content themselves."""
    v = variant or VARIANTS[1]  # Map is Not Territory is the house thesis
    body = _body(v, demo_artifact_html, waitlist_endpoint="", contact_email=contact_email)
    # Artifact hosts stamp their own <body>; carry the variant on <main>
    # and mirror it onto body at runtime for the tracker.
    body = body.replace("<main>", f'<main data-variant="{v.key}">', 1)
    boot = "document.body.dataset.variant = document.querySelector('main').dataset.variant;"
    return (
        f"<title>Brier Zero — the Map/Territory Detection Engine</title>"
        f"<style>{_font_css()}{_SITE_CSS}"
        "body{background:var(--ink) !important;color:var(--text) !important;}</style>"
        f"{body}<script>{boot}{_TRACK_JS}</script>"
    )


def render_router() -> str:
    keys = json.dumps([v.key for v in VARIANTS])
    links = " · ".join(f'<a href="landing-{v.key}.html">{esc(v.name)}</a>' for v in VARIANTS)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="dark">
<title>Brier Zero</title>
<style>body{{background:#0b0e14;color:#8a96a8;font:16px/1.6 ui-monospace,monospace;
display:grid;place-items:center;min-height:100vh;margin:0}}a{{color:#e5a13c}}</style>
</head>
<body>
<p>Assigning you a variant&hellip;
<noscript>JavaScript is off — pick one: {links}</noscript></p>
<script>{_ROUTER_JS_TEMPLATE % {"variants": keys}}</script>
</body>
</html>
"""


def render_all(demo_artifact_html: str, waitlist_endpoint: str = "") -> dict[str, str]:
    """Returns {filename: html} for the router + all four variants."""
    out = {"index.html": render_router()}
    for v in VARIANTS:
        out[f"landing-{v.key}.html"] = render_variant(v, demo_artifact_html, waitlist_endpoint)
    return out
