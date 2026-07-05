"""BZ-301: visual Map/Territory gap report as an HTML artifact."""

from __future__ import annotations

from ..models import Market
from . import base
from .base import esc


def render(market: Market) -> str:
    fid = market.fidelity
    if fid is None:
        raise ValueError("run MapFidelityScorer before rendering a gap report")
    price = market.price_history[-1][1] if market.price_history else None
    map_claim = market.official_map.claimed_probability if market.official_map else None

    tone = "good" if fid.score >= 80 else ("warn" if fid.score >= 50 else "bad")
    headline = (
        f'<div class="headline"><span class="prob">{fid.score}/100</span>'
        f'<span>{base.risk_badge("map fidelity", tone)}</span></div>'
        f"<p>{esc(fid.narrative)}</p>"
    )
    if price is not None and map_claim is not None:
        headline += base.heatmap([
            ("map says", map_claim),
            ("market says", price),
            ("divergence", abs(price - map_claim)),
        ])

    def bullets(items: list[str], empty: str) -> str:
        if not items:
            return f'<p class="muted">{esc(empty)}</p>'
        return "".join(f"<p>&#9888;&#65039; {esc(i)}</p>" for i in items)

    assumptions = "".join(
        f"<tr><td>{esc(a.text)}</td>"
        f"<td>{'yes' if a.stated_in_map else '<strong>no</strong>'}</td>"
        f"<td>{esc(a.status.value)}</td></tr>"
        for a in fid.surfaced_assumptions
    ) or '<tr><td colspan="3" class="muted">No assumptions surfaced.</td></tr>'

    body = (
        base.layer(1, "Map Fidelity", headline)
        + base.layer(2, "Where the map is silent", bullets(
            fid.silent, "The map covers everything the agents surfaced."), open_=True)
        + base.layer(2, "Where the map is contradicted", bullets(
            fid.contradicted, "No high-confidence evidence disputes the map."), open_=True)
        + base.layer(3, "Where the map is stale", bullets(
            fid.stale, "The map is at least as fresh as the evidence."))
        + base.layer(3, "All surfaced assumptions", (
            f'<div class="scroll"><table><tr><th>assumption</th><th>in map?</th><th>review</th></tr>'
            f"{assumptions}</table></div>"
        ))
        + (base.layer(4, "Auto gap analysis", f"<p>{esc(market.gap_analysis.narrative)}</p>")
           if market.gap_analysis else "")
    )
    return base.page(
        f"Map/Territory Gap Report — {market.question.text}",
        body,
        subtitle=f"Market {market.id} · the map is not the territory",
    )
