"""BZ-302: Skill Audit Report artifact — skill-by-skill Brier history."""

from __future__ import annotations

from ..audit import SkillAuditPipeline, SkillAuditReport
from . import base
from .base import esc


def render(report: SkillAuditReport, pipeline: SkillAuditPipeline) -> str:
    weights = pipeline.selection_weights()

    rows = []
    for sid, rec in sorted(pipeline.records.items(), key=lambda kv: kv[1].mean_brier or 1.0):
        mean = rec.mean_brier
        dead = rec.dead_weight
        history = " ".join(f"{b:.2f}" for _, b in rec.history[-8:])
        rows.append(
            f"<tr><td>{esc(sid)}{' &#9888;&#65039;' if dead else ''}</td>"
            f"<td>{rec.uses}</td>"
            f"<td>{mean:.3f}</td>"
            f"<td>{weights.get(sid, 1.0):.2f}x</td>"
            f"<td>{'DEAD WEIGHT' if dead else ('signal' if mean <= 0.25 else 'watch')}</td>"
            f'<td class="muted">{history}</td></tr>'
        )
    table = (
        '<div class="scroll"><table><tr><th>skill</th><th>uses</th><th>mean Brier</th>'
        "<th>selection weight</th><th>verdict</th><th>recent history (Brier per market)</th></tr>"
        + "".join(rows) + "</table></div>"
        '<p class="muted">Brier: lower is better; 0.25 = coin flip. Skills flagged DEAD WEIGHT '
        "consistently underperform the baseline &mdash; deprecate or rewrite them; they were "
        "probably written for an older, weaker model.</p>"
    )

    entries = "".join(
        f"<tr><td>{esc(e.skill_id)}</td><td>{e.brier:.3f}</td><td>{esc(e.verdict)}</td></tr>"
        for e in report.entries
    ) or '<tr><td colspan="3" class="muted">No skill-attributed trades.</td></tr>'

    heat = base.heatmap([
        (sid[:10], min(1.0, (rec.mean_brier or 0.25) / 0.5))
        for sid, rec in list(pipeline.records.items())[:12]
    ])

    body = (
        base.layer(1, "Audit verdict", f"<p>{esc(report.narrative)}</p>{heat}")
        + base.layer(2, "Skill-by-skill Brier history", table, open_=True)
        + base.layer(3, "This market's entries", (
            f'<div class="scroll"><table><tr><th>skill</th><th>Brier</th><th>verdict</th></tr>{entries}</table></div>'
        ))
    )
    return base.page(
        "Skill Audit Report",
        body,
        subtitle=f"Post-resolution audit for market {report.market_id} · meta-calibration loop",
    )
