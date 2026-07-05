"""BZ-202: Interactive Signal Slider — the Employee Proxy's HTML artifact.

A self-contained page a verified employee opens to review their draft
signal before submission: drag the slider, watch the blended market price
update live, and see how their signal compares to agent consensus. No
backend, no login — state lives in the page; submission is a copy-paste
payload (or POST in a deployed install).
"""

from __future__ import annotations

import json

from ..models import Market
from ..proxy import DraftSignal
from . import base
from .base import esc

_JS_TEMPLATE = """
(function () {
  var cfg = %(cfg)s;
  var slider = document.getElementById('confidence');
  var out = document.getElementById('blended');
  var you = document.getElementById('yourprob');
  var gapEl = document.getElementById('consensus-gap');
  var payload = document.getElementById('payload');
  function clamp(x, lo, hi) { return Math.min(hi, Math.max(lo, x)); }
  function render() {
    var conf = slider.value / 100;
    var delta = cfg.delta * conf / (cfg.confidence || 1);
    var nudge = clamp(delta * conf, -cfg.maxNudge, cfg.maxNudge);
    var blended = clamp(cfg.consensus + nudge, 0.01, 0.99);
    var yours = clamp(cfg.consensus + delta, 0.01, 0.99);
    out.textContent = Math.round(blended * 100) + '%%';
    you.textContent = Math.round(yours * 100) + '%%';
    var gap = yours - cfg.consensus;
    gapEl.textContent = (gap >= 0 ? '+' : '') + Math.round(gap * 100) +
      ' points vs agent consensus of ' + Math.round(cfg.consensus * 100) + '%%';
    gapEl.className = Math.abs(gap) > 0.15 ? 'badge bad' : (Math.abs(gap) > 0.05 ? 'badge warn' : 'badge good');
    payload.textContent = JSON.stringify({
      market_id: cfg.marketId, pseudonym: cfg.pseudonym,
      delta: +(delta * conf).toFixed(4), confidence: +conf.toFixed(2)
    }, null, 2);
  }
  slider.addEventListener('input', render);
  render();
})();
"""


def render(market: Market, draft: DraftSignal, max_nudge: float = 0.15) -> str:
    consensus = market.price_history[-1][1] if market.price_history else 0.5
    cfg = {
        "marketId": market.id,
        "pseudonym": draft.signal.pseudonym,
        "delta": draft.signal.delta,
        "confidence": draft.signal.confidence or 1.0,
        "consensus": consensus,
        "maxNudge": max_nudge,
    }
    body = (
        base.layer(1, "Your signal (review before submitting)", (
            f"<p>{esc(market.question.text)}</p>"
            f'<div class="headline"><span class="prob" id="blended">&mdash;</span>'
            f'<span class="muted">market price if you submit at this confidence</span></div>'
            f'<p><span id="consensus-gap" class="badge good"></span></p>'
            f"<h3>Confidence</h3>"
            f'<input type="range" id="confidence" min="0" max="100" '
            f'value="{int((draft.signal.confidence or 0.5) * 100)}" '
            f'aria-label="signal confidence percent">'
            f'<p class="muted">Your implied probability: <strong id="yourprob">&mdash;</strong>. '
            f"Signals are capped at &plusmn;{max_nudge:.0%} market impact no matter how "
            f"confident you are &mdash; one whisper informs the market, it never owns it.</p>"
        ))
        + base.layer(2, "How your whisper was interpreted", (
            f"<p>{esc(draft.explanation)}</p>"
            f"<p><strong>Public rationale (all the market will ever see):</strong> "
            f"{esc(draft.signal.public_rationale)}</p>"
            f'<p class="muted">Scrubbed before entering the market: '
            f"{esc(', '.join(draft.scrubbed_terms) if draft.scrubbed_terms else 'nothing sensitive detected')}. "
            f"Your pseudonym <code>{esc(draft.signal.pseudonym)}</code> is stable inside this market "
            f"only &mdash; it cannot be linked to you or to your signals in other markets.</p>"
        ), open_=True)
        + base.layer(3, "Submission payload", (
            "<p>This is the entire payload that leaves this page:</p>"
            '<pre id="payload" class="scroll"></pre>'
        ))
    )
    return base.page(
        "Signal Artifact — pseudonymous employee signal",
        body,
        subtitle=f"Market {market.id} · verified via SSO · identity stripped",
        extra_js=_JS_TEMPLATE % {"cfg": json.dumps(cfg)},
    )
