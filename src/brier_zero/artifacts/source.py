"""BZ-103: HTML Source Artifact — the research agent's evidence, verifiable.

Hover-to-verify claims, side-by-side source comparison, and an event
timeline relative to market creation.
"""

from __future__ import annotations

from ..models import Market
from ..research import Assessment
from . import base
from .base import esc


def render(market: Market, assessment: Assessment, agent_id: str) -> str:
    ev = assessment.evidence

    # Claims with hover-to-verify: the claim text is the interpretation;
    # the tooltip is the exact source snippet backing it.
    claims = "".join(
        f'<p><span class="claim" tabindex="0">'
        f"{esc(('Supports YES' if e.supports_yes else 'Supports NO') + ' — ' + e.source.title)}"
        f'<span class="tip">&ldquo;{esc(e.source.snippet)}&rdquo;<br>'
        f"<em>{esc(e.source.domain)} &middot; trust {e.source.confidence:.0%}"
        f"{' &middot; ' + e.source.published_at.date().isoformat() if e.source.published_at else ''}</em>"
        f"</span></span> <span class=\"muted\">(strength {e.strength:.0%})</span></p>"
        for e in ev
    ) or '<p class="muted">No evidence recorded.</p>'

    # Side-by-side comparison table.
    rows = "".join(
        f"<tr><td>{esc(e.source.title)}</td><td>{esc(e.source.domain)}</td>"
        f"<td>{e.source.published_at.date().isoformat() if e.source.published_at else '—'}</td>"
        f"<td>{'YES' if e.supports_yes else 'NO'}</td>"
        f"<td>{e.strength:.0%}</td><td>{e.source.confidence:.0%}</td>"
        f"<td>&ldquo;{esc(e.source.snippet[:160])}&rdquo;</td></tr>"
        for e in sorted(ev, key=lambda x: -x.source.confidence)
    )
    table = (
        '<div class="scroll"><table><tr><th>source</th><th>domain</th><th>published</th>'
        "<th>side</th><th>strength</th><th>trust</th><th>key snippet</th></tr>"
        f"{rows}</table></div>"
    )

    # Timeline of dated source events vs market creation.
    events = [
        (e.source.published_at, e.source.title)
        for e in ev if e.source.published_at is not None
    ]
    timeline = base.timeline_svg(events, anchor=market.question.created_at)

    body = (
        base.layer(1, "Assessment", (
            f'<div class="headline"><span class="prob">{assessment.probability:.0%}</span>'
            f"<span>{base.risk_badge(f'{len(ev)} sources', 'good')}</span></div>"
            f"<p>{esc(assessment.rationale)}</p>"
            f'<p class="muted">Research agent {esc(agent_id)} &middot; skills: '
            f"{esc(', '.join(assessment.skill_ids) or 'none recorded')}</p>"
        ))
        + base.layer(2, "Claims — hover to verify against exact source text", claims, open_=True)
        + base.layer(3, "Side-by-side source comparison", table)
        + base.layer(4, "Event timeline vs market creation", timeline)
    )
    return base.page(
        f"Source Artifact — {market.question.text}",
        body,
        subtitle=f"Evidence backing {esc(agent_id)}'s position on market {market.id}",
    )
