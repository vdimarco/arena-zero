"""BZ-101 + PRD 5.5: dual-output market artifact renderer.

`render_human` -> market-human.html: 4-layer progressive disclosure.
`render_agent` -> market-agent.md: structured text for the next agent.
"""

from __future__ import annotations

from ..fidelity import variance_band
from ..models import Market, MapTerritoryRisk, MarketStatus
from . import base
from .base import esc


def _fidelity_tone(score: int) -> str:
    return "good" if score >= 80 else ("warn" if score >= 50 else "bad")


def render_human(market: Market) -> str:
    price = market.price_history[-1][1] if market.price_history else 0.5
    fid = market.fidelity.score if market.fidelity else 100
    band = variance_band(fid, price)

    badges = [base.risk_badge(f"map fidelity {fid}/100", _fidelity_tone(fid))]
    if market.risk is MapTerritoryRisk.HIGH:
        badges.append(base.risk_badge("high map/territory risk", "bad"))
    if market.resolution is not None:
        badges.append(base.risk_badge(
            f"resolved {'YES' if market.resolution.outcome else 'NO'}",
            "good" if market.resolution.outcome else "bad",
        ))
    elif market.status is MarketStatus.OPEN:
        badges.append(base.risk_badge("open", "good"))

    # Layer 1: executive summary — busy-CEO view.
    summary = (
        f'<div class="headline"><span class="prob">{price:.0%}</span>'
        f'<span>{" ".join(badges)}</span></div>'
        f'<p>{esc(market.question.text)}</p>'
        f'<p class="muted">Displayed range {band[0]:.0%}&ndash;{band[1]:.0%} '
        f'(width reflects map fidelity, not agent mood). Resolves by '
        f'{esc(market.question.close_at.date().isoformat())}.</p>'
    )
    if market.gap_analysis:
        summary += (
            f'<p><strong>Map/Territory Gap:</strong> {esc(market.gap_analysis.narrative)}</p>'
        )

    # Layer 2: chart + key signals — engaged-analyst view.
    map_claim = market.official_map.claimed_probability if market.official_map else None
    chart = base.line_chart(market.price_history, map_claim=map_claim, band=band)
    heat = base.heatmap([
        ("divergence", market.gap_analysis.divergence if market.gap_analysis else
         (abs(price - map_claim) if map_claim is not None else 0.0)),
        ("map risk", 1.0 if market.risk is MapTerritoryRisk.HIGH else 0.15),
        ("fidelity", (100 - fid) / 100),
        ("signals", min(1.0, len(market.signals) / 5)),
    ])
    signals_rows = "".join(
        f"<tr><td>{esc(s.pseudonym)}</td><td>{s.delta:+.1%}</td>"
        f"<td>{s.confidence:.0%}</td><td>{esc(s.public_rationale)}</td></tr>"
        for s in market.signals
    ) or '<tr><td colspan="4" class="muted">No employee signals yet.</td></tr>'
    layer2 = (
        f"{chart}<h3>Risk heatmap</h3>{heat}"
        f'<h3>Pseudonymous employee signals</h3><div class="scroll"><table>'
        f"<tr><th>pseudonym</th><th>delta</th><th>confidence</th><th>public rationale</th></tr>"
        f"{signals_rows}</table></div>"
    )

    # Layer 3: full reasoning + sources — skeptical-researcher view.
    rst = market.restatement
    rst_html = ""
    if rst:
        items = "".join(
            f"<tr><td>{esc(a.text)}</td>"
            f"<td>{'yes' if a.stated_in_map else '<strong>no</strong>'}</td>"
            f"<td>{esc(a.status.value)}</td></tr>"
            for a in rst.assumptions
        )
        rst_html = (
            f"<h3>Agent restatement</h3><p>{esc(rst.paraphrase)}</p>"
            f'<div class="scroll"><table><tr><th>assumption</th><th>in map?</th><th>review</th></tr>{items}</table></div>'
        )
    trades_html = "".join(
        f'<div class="card"><strong>{esc(t.agent_id)}</strong> traded {t.probability:.0%}'
        f'<p>{esc(t.rationale)}</p>'
        + "".join(
            f'<p class="muted"><span class="claim" tabindex="0">{esc(s.title)}'
            f'<span class="tip">&ldquo;{esc(s.snippet)}&rdquo;<br>'
            f'<em>{esc(s.domain)} &middot; trust {s.confidence:.0%}</em></span></span> '
            f'&mdash; <a href="{esc(s.url)}">{esc(s.url)}</a></p>'
            for s in t.sources
        )
        + "</div>"
        for t in market.trades
    ) or '<p class="muted">No trades yet.</p>'
    gap_html = ""
    if market.gap_alerts:
        gap_html = "<h3>Gap alerts</h3>" + "".join(f"<p>&#9888;&#65039; {esc(g)}</p>" for g in market.gap_alerts)
    layer3 = rst_html + "<h3>Agent trades &amp; sources</h3>" + trades_html + gap_html

    # Layer 4: raw data + audit trail — regulator view.
    raw = {
        "market_id": market.id,
        "status": market.status.value,
        "risk": market.risk.value,
        "question": market.question.text,
        "resolution_criteria": market.question.resolution_criteria,
        "official_map": (
            {"text": market.official_map.text,
             "claimed_probability": market.official_map.claimed_probability,
             "as_of": market.official_map.as_of}
            if market.official_map else None
        ),
        "price_history": [(t.isoformat(), p) for t, p in market.price_history],
        "trades": [
            {"agent": t.agent_id, "p": t.probability, "skills": t.skill_ids,
             "sources": [s.url for s in t.sources], "at": t.at.isoformat()}
            for t in market.trades
        ],
        "signals": [
            {"pseudonym": s.pseudonym, "delta": s.delta, "confidence": s.confidence}
            for s in market.signals
        ],
        "fidelity": market.fidelity.score if market.fidelity else None,
        "resolution": (
            {"outcome": market.resolution.outcome, "by": market.resolution.resolved_by,
             "at": market.resolution.resolved_at.isoformat()}
            if market.resolution else None
        ),
    }
    layer4 = (
        base.json_block(raw)
        + "<h3>Disclosure audit trail (this session)</h3>"
        + '<pre id="disclosure-log" class="scroll">[]</pre>'
    )

    body = (
        base.layer(1, "Executive summary", summary)
        + base.layer(2, "Probability chart & key signals", layer2)
        + base.layer(3, "Full agent reasoning & sources", layer3)
        + base.layer(4, "Raw market data & audit trail", layer4)
    )
    return base.page(
        f"Brier Zero — {market.question.text}",
        body,
        subtitle=f"Market {market.id} · {market.status.value} · map fidelity {fid}/100",
    )


def render_agent(market: Market) -> str:
    """market-agent.md — what the next session reads before touching this work."""
    price = market.price_history[-1][1] if market.price_history else 0.5
    fid = market.fidelity.score if market.fidelity else None
    lines = [
        f"# market-agent: {market.id}",
        "",
        "## Intent",
        f"- question: {market.question.text}",
        f"- resolution_criteria: {market.question.resolution_criteria}",
        f"- close_at: {market.question.close_at.isoformat()}",
        f"- status: {market.status.value}",
        f"- current_price: {price:.4f}",
        f"- map_fidelity: {fid if fid is not None else 'unscored'}",
        f"- map_territory_risk: {market.risk.value}",
        "",
        "## Constraints",
        "- agent-only trading; humans create/resolve, never trade",
        "- employee input enters only as pseudonymous signals (bounded nudge, max ±15%)",
        "- price display must be widened by (100 - fidelity)/100 * 0.25 — do not show a point estimate as truth",
        "",
        "## Assumptions surfaced (restatement protocol)",
    ]
    if market.restatement:
        for a in market.restatement.assumptions:
            lines.append(f"- [{a.status.value}] (in_map={a.stated_in_map}) {a.text}")
    else:
        lines.append("- restatement not yet run — DO NOT open this market for trading")
    lines += ["", "## Source confidence & audit trail"]
    for t in market.trades:
        lines.append(f"- {t.agent_id} p={t.probability:.2f} skills={','.join(t.skill_ids) or '-'}")
        for s in t.sources:
            lines.append(f"  - trust={s.confidence:.2f} {s.title} <{s.url}>")
    lines += [
        "",
        "## Known unknowns (intentionally out of scope)",
        "- whisper raw text is never persisted here — only pseudonymous deltas",
        "- resolution disputes are a human process; this file records outcomes, not adjudication",
        "- source snippets are excerpts; full documents were not archived in this artifact",
        "",
        "## Gap alerts",
    ]
    lines += [f"- {g}" for g in market.gap_alerts] or ["- none"]
    if market.gap_analysis:
        lines += ["", "## Gap analysis", market.gap_analysis.narrative]
    if market.resolution:
        lines += ["", "## Resolution",
                  f"- outcome: {'YES' if market.resolution.outcome else 'NO'}"
                  f" (by {market.resolution.resolved_by} at {market.resolution.resolved_at.isoformat()})"]
    return "\n".join(lines) + "\n"
