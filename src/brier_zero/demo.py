"""End-to-end demo (PRD Phase 1): builds the "Will Apple ship a car by
2028?" market, runs the whole lifecycle, and writes every artifact type
plus the four landing-page variants to ./dist.

Run:  python -m brier_zero.demo [output_dir]
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .artifacts import audit_report, gap, landing, market as market_art, slider, source as source_art
from .engine import MarketEngine
from .models import AssumptionStatus, OfficialMap, Question, Source, Whisper, utcnow
from .proxy import EmployeeDirectory, EmployeeProxyAgent
from .research import EvidenceItem, ResearchAgent


def build_demo(out_dir: Path) -> dict[str, Path]:
    engine = MarketEngine()
    now = utcnow()

    question = Question(
        text="Will Apple ship a production passenger car by December 31, 2028?",
        resolution_criteria=(
            "Resolves YES if Apple (or a subsidiary) makes a passenger road vehicle "
            "available for consumer purchase or lease in any market before the close date. "
            "Concept vehicles, partnerships without an Apple-branded vehicle, and CarPlay "
            "integrations do not count."
        ),
        close_at=now + timedelta(days=900),
        context=(
            "Leadership believes the program is on track. We assume the thermal validation "
            "issues from Q1 are resolved. Board expects a 2028 reveal."
        ),
    )
    official_map = OfficialMap(
        text=(
            "Project roadmap: vehicle program ON TRACK for 2028 launch. Design lock achieved. "
            "Supplier contracts signed. Dashboard: 90% confidence in ship date."
        ),
        claimed_probability=0.90,
        source_name="internal program dashboard",
        as_of=now - timedelta(days=120),
    )

    mkt = engine.create_market(question, official_map)

    # Restatement gate (BZ-102): the agent paraphrases; the creator is
    # surprised by the thermal-validation assumption and rejects one claim.
    restatement = engine.run_restatement(mkt)
    verdicts: dict[str, AssumptionStatus] = {}
    for a in restatement.assumptions:
        if "thermal" in a.text.lower() or "face value" in a.text.lower():
            verdicts[a.id] = AssumptionStatus.SURPRISE
        elif not a.stated_in_map:
            verdicts[a.id] = AssumptionStatus.CONFIRMED
    engine.review_restatement(mkt, verdicts, accepted=True)

    # Research agents trade (PRD 5.1/5.2).
    optimist = ResearchAgent("agent_supply_chain", skill_ids=["skill_supply_chain", "skill_press_scan"])
    skeptic = ResearchAgent("agent_program_history", skill_ids=["skill_program_history", "skill_hiring_signals"])

    optimist_evidence = [
        EvidenceItem(
            Source(
                title="Supplier signs multi-year EV component deal",
                url="https://www.reuters.com/example/apple-supplier-deal",
                snippet="The supplier confirmed a multi-year agreement covering drivetrain components beginning 2027.",
                published_at=now - timedelta(days=40),
            ),
            supports_yes=True, strength=0.6,
        ),
        EvidenceItem(
            Source(
                title="Regulatory filing for vehicle testing fleet expansion",
                url="https://www.sec.gov/example/testing-fleet",
                snippet="Filing shows the autonomous testing fleet grew 30% year over year.",
                published_at=now - timedelta(days=90),
            ),
            supports_yes=True, strength=0.4,
        ),
    ]
    skeptic_evidence = [
        EvidenceItem(
            Source(
                title="Veteran program leads depart for rival",
                url="https://www.bloomberg.com/example/departures",
                snippet="Three senior vehicle program leaders left in the past two quarters.",
                published_at=now - timedelta(days=20),
            ),
            supports_yes=False, strength=0.7,
        ),
        EvidenceItem(
            Source(
                title="Thermal validation failures delay milestone",
                url="https://arstechnica.com/example/thermal",
                snippet="People familiar with the program describe repeated thermal validation failures pushing the integration milestone.",
                published_at=now - timedelta(days=10),
            ),
            supports_yes=False, strength=0.8,
        ),
        EvidenceItem(
            Source(
                title="Historical base rate: new-entrant car programs slip",
                url="https://example-research.edu/base-rates",
                snippet="Across 14 new-entrant vehicle programs since 2005, median slip from announced ship date was 26 months.",
                published_at=now - timedelta(days=200),
            ),
            supports_yes=False, strength=0.6,
        ),
    ]
    a1 = optimist.assess(optimist_evidence, prior=0.5)
    a2 = skeptic.assess(skeptic_evidence, prior=0.5)
    engine.place_trade(mkt, optimist.trade(a1), at=now + timedelta(hours=1))
    engine.place_trade(mkt, skeptic.trade(a2), at=now + timedelta(hours=2))

    # Employee whisper via the proxy (BZ-201) -> slider artifact (BZ-202).
    directory = EmployeeDirectory(tokens={"sso_token_alice": "emp_00417"})
    proxy = EmployeeProxyAgent(directory, secret=b"demo-secret-rotate-me")
    whisper = Whisper(
        employee_token="sso_token_alice",
        text="The Marzipan chassis failed thermal validation twice last month; team is very behind.",
        market_id=mkt.id,
    )
    draft = proxy.draft(whisper)
    slider_html = slider.render(mkt, draft)
    engine.apply_signal(mkt, draft.signal, at=now + timedelta(hours=3))

    price = engine.price(mkt)

    # Render everything.
    out_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}

    def write(name: str, content: str) -> None:
        p = out_dir / name
        p.write_text(content, encoding="utf-8")
        written[name] = p

    human_html = market_art.render_human(mkt)
    write("market-human.html", human_html)
    write("market-agent.md", market_art.render_agent(mkt))
    write("source-artifact.html", source_art.render(mkt, a2, skeptic.agent_id))
    write("signal-slider.html", slider_html)
    write("gap-report.html", gap.render(mkt))
    for name, page_html in landing.render_all(human_html).items():
        write(name, page_html)

    # Resolve a *copy-style* second market quickly to exercise the audit
    # pipeline and produce a skill audit artifact (BZ-302).
    q2 = Question(
        text="Will the integration milestone pass thermal validation this quarter?",
        resolution_criteria="Resolves YES if the milestone passes by end of quarter.",
        close_at=now + timedelta(days=1),
    )
    m2 = engine.create_market(q2, OfficialMap(text="Dashboard: on track.", claimed_probability=0.8))
    engine.run_restatement(m2)
    engine.review_restatement(m2, {})
    t1 = optimist.trade(optimist.assess([EvidenceItem(
        Source(title="Status mail", url="https://example.com/status",
               snippet="Team reports readiness.", published_at=now - timedelta(days=3)),
        supports_yes=True, strength=0.5)]))
    t2 = skeptic.trade(skeptic.assess([EvidenceItem(
        Source(title="Test logs", url="https://example.com/logs",
               snippet="Two consecutive thermal failures.", published_at=now - timedelta(days=2)),
        supports_yes=False, strength=0.8)]))
    engine.place_trade(m2, t1, at=now + timedelta(hours=1))
    engine.place_trade(m2, t2, at=now + timedelta(hours=2))
    engine.close(m2)
    report = engine.resolve(m2, outcome=False, notes="milestone slipped; thermal failure confirmed")
    write("skill-audit.html", audit_report.render(report, engine.skill_audit))

    print(f"Demo market {mkt.id}: price {price:.0%} vs map claim 90% "
          f"(fidelity {mkt.fidelity.score}/100, {len(mkt.gap_alerts)} gap alerts)")
    print(f"Wrote {len(written)} artifacts to {out_dir}/")
    return written


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("dist")
    build_demo(out)


if __name__ == "__main__":
    main()
