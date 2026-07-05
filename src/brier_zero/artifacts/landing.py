"""BZ-303: landing page with four A/B hero variants and an embedded live
demo artifact (no login).

`render_variant` builds one variant; `render_all` returns the four pages
plus a router page that assigns a visitor a sticky variant (?v= override,
localStorage persistence) and records the assignment for the funnel.
Waitlist submissions POST to whatever endpoint is configured — or fall
back to a mailto: so the static page works with zero backend.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from . import base
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
        subline="Your people see failure years before your dashboard does. Brier Zero gives them "
                "a safe, pseudonymous way to price it into an internal market — so you get the "
                "signal and the journalist doesn't.",
        cta="Get the internal truth layer",
    ),
    HeroVariant(
        key="b", name="Map is Not Territory",
        headline="Your dashboard is a map. The market is the territory.",
        subline="Brier Zero detects where your roadmap diverges from reality — scoring every "
                "plan against agent-discovered ground truth before you build a quarter on a "
                "bad assumption.",
        cta="Score my map",
    ),
    HeroVariant(
        key="c", name="Artifact-Native",
        headline="Intelligence should be an artifact, not a conversation.",
        subline="Every Brier Zero market produces a self-contained interactive HTML artifact — "
                "progressive disclosure from executive summary to raw audit trail. Email it, "
                "archive it, open it anywhere. No login, no platform.",
        cta="Open a live artifact",
    ),
    HeroVariant(
        key="d", name="Calibrated Forecasting Engine",
        headline="The prediction market for people who can't trust their own roadmap.",
        subline="Autonomous research agents trade probabilities on your real questions, are "
                "scored by Brier score, and get better every time they're wrong.",
        cta="Join the waitlist",
    ),
]

_TRACK_JS = """
(function () {
  var v = document.body.dataset.variant;
  try {
    var log = JSON.parse(localStorage.getItem('bz_events') || '[]');
    log.push({event: 'view', variant: v, at: new Date().toISOString()});
    localStorage.setItem('bz_events', JSON.stringify(log));
  } catch (e) {}
  var form = document.getElementById('waitlist');
  if (!form) return;
  form.addEventListener('submit', function (ev) {
    try {
      var log = JSON.parse(localStorage.getItem('bz_events') || '[]');
      log.push({event: 'signup_submit', variant: v, at: new Date().toISOString()});
      localStorage.setItem('bz_events', JSON.stringify(log));
    } catch (e) {}
    if (!form.dataset.endpoint) {
      ev.preventDefault();
      var data = new FormData(form);
      var lines = ['Brier Zero waitlist signup (variant ' + v + ')'];
      data.forEach(function (val, key) { lines.push(key + ': ' + val); });
      location.href = 'mailto:' + form.dataset.mailto +
        '?subject=' + encodeURIComponent('Brier Zero waitlist (' + v + ')') +
        '&body=' + encodeURIComponent(lines.join('\\n'));
    }
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


def render_variant(
    variant: HeroVariant,
    demo_artifact_html: str,
    waitlist_endpoint: str = "",
    contact_email: str = "hello@brier.zero",
) -> str:
    questions = "".join(
        f'<label><p><strong>{esc(q)}</strong></p>'
        f'<textarea name="{esc(key)}" rows="2" style="width:100%"></textarea></label>'
        for key, q in _QUALIFY_QUESTIONS
    )
    endpoint_attrs = (
        f' action="{esc(waitlist_endpoint)}" method="post" data-endpoint="1"'
        if waitlist_endpoint else f' data-mailto="{esc(contact_email)}"'
    )
    # The live demo is embedded whole via iframe srcdoc so the landing page
    # stays one file and the artifact stays interactive (PRD 8.2).
    srcdoc = esc(demo_artifact_html)
    body = f"""
<section class="card" style="text-align:center; padding:3rem 1.5rem">
  <h1 style="font-size:2rem">{esc(variant.headline)}</h1>
  <p style="max-width:640px;margin:.75rem auto">{esc(variant.subline)}</p>
  <p><a href="#waitlist-section" class="badge good" style="font-size:1rem;padding:.5rem 1.25rem">{esc(variant.cta)}</a></p>
  <p class="muted">Agent-only prediction markets &middot; no human trading &middot; no gambling mechanics</p>
</section>

<h2>Open the live artifact — this is the product</h2>
<p class="muted">A real Brier Zero market artifact, embedded here. Click through all four layers.
No login. If this page were an email attachment, it would still work.</p>
<iframe srcdoc="{srcdoc}" style="width:100%;height:640px;border:1px solid var(--line);border-radius:10px"
        title="Live Brier Zero demo artifact" loading="lazy"></iframe>

<section id="waitlist-section">
  <h2>Battle-test signup</h2>
  <p class="muted">Four questions. If none of them sting, Brier Zero isn't for you yet.</p>
  <form id="waitlist" class="card"{endpoint_attrs}>
    <label><p><strong>Work email</strong></p><input type="email" name="email" required style="width:100%"></label>
    {questions}
    <p><button type="submit" class="badge good" style="font-size:1rem;padding:.5rem 1.5rem;cursor:pointer">
      {esc(variant.cta)}</button></p>
  </form>
</section>
"""
    page = base.page(
        f"Brier Zero — {variant.name}",
        body,
        subtitle="The Map/Territory Detection Engine",
        extra_js=_TRACK_JS,
    )
    # Tag the body so the tracker knows which variant it is on.
    return page.replace("<body>", f'<body data-variant="{variant.key}">', 1)


def render_router() -> str:
    keys = json.dumps([v.key for v in VARIANTS])
    body = (
        '<p class="muted">Assigning you a variant&hellip; '
        '<noscript>JavaScript is off — pick one: '
        + " · ".join(f'<a href="landing-{v.key}.html">{esc(v.name)}</a>' for v in VARIANTS)
        + "</noscript></p>"
    )
    return base.page(
        "Brier Zero", body,
        extra_js=_ROUTER_JS_TEMPLATE % {"variants": keys},
    )


def render_all(demo_artifact_html: str, waitlist_endpoint: str = "") -> dict[str, str]:
    """Returns {filename: html} for the router + all four variants."""
    out = {"index.html": render_router()}
    for v in VARIANTS:
        out[f"landing-{v.key}.html"] = render_variant(v, demo_artifact_html, waitlist_endpoint)
    return out
