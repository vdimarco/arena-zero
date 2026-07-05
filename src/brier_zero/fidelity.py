"""BZ-301: Map Fidelity Scoring Engine.

Scores the Official Map (roadmap/dashboard/press line) against the
Territory (what agents actually found: restatement assumptions, trade
rationales, sources, employee signals) and reports where the map is
silent, wrong, or stale.

Score model (0-100, higher = the map can be trusted):
  start at 100, subtract per defect —
    silent:       map never mentions a load-bearing territory item   (-8 each)
    contradicted: map claim disputed by high-confidence evidence     (-15 each)
    stale:        map is dated before the newest strong evidence     (-10)
    surprise:     assumption that surprised the creator in review    (-12 each)
    rejected:     assumption the creator says is flat wrong          (-15 each)
    divergence:   |market price - map claimed probability| scaled    (-0..30)
The floor is 0. Markets with a low score should be *displayed* as
high-variance regardless of agent confidence (PRD 7.4).
"""

from __future__ import annotations

from datetime import timedelta

from .models import (
    AssumptionStatus,
    FidelityReport,
    Market,
    OfficialMap,
)

_PENALTY_SILENT = 8
_PENALTY_CONTRADICTED = 15
_PENALTY_STALE = 10
_PENALTY_SURPRISE = 12
_PENALTY_REJECTED = 15
_MAX_DIVERGENCE_PENALTY = 30


class MapFidelityScorer:
    def __init__(self, contradiction_confidence: float = 0.6, staleness: timedelta = timedelta(days=30)):
        self.contradiction_confidence = contradiction_confidence
        self.staleness = staleness

    def score(self, market: Market, price: float | None = None) -> FidelityReport:
        om = market.official_map
        assumptions = market.restatement.assumptions if market.restatement else []

        silent = [a.text for a in assumptions if not a.stated_in_map]
        surprises = [a for a in assumptions if a.status is AssumptionStatus.SURPRISE]
        rejected = [a for a in assumptions if a.status is AssumptionStatus.REJECTED]

        contradicted = self._contradictions(market, om, price)
        stale = self._staleness(market, om)

        penalty = (
            _PENALTY_SILENT * len(silent)
            + _PENALTY_CONTRADICTED * len(contradicted)
            + _PENALTY_STALE * len(stale)
            + _PENALTY_SURPRISE * len(surprises)
            + _PENALTY_REJECTED * len(rejected)
            + self._divergence_penalty(om, price)
        )
        score = max(0, 100 - int(round(penalty)))

        narrative = self._narrative(score, silent, contradicted, stale, surprises, rejected)
        report = FidelityReport(
            score=score,
            silent=silent,
            contradicted=contradicted,
            stale=stale,
            surfaced_assumptions=list(assumptions),
            narrative=narrative,
        )
        market.fidelity = report
        return report

    def _contradictions(self, market: Market, om: OfficialMap | None, price: float | None) -> list[str]:
        """Map claims disputed by evidence.

        Without NLP entailment we use the honest structural signal we do
        have: the map asserts a probability while high-confidence sources
        back trades priced far away from it.
        """
        if om is None or om.claimed_probability is None:
            return []
        out = []
        for trade in market.trades:
            if abs(trade.probability - om.claimed_probability) < 0.3:
                continue
            for s in trade.sources:
                if s.confidence >= self.contradiction_confidence:
                    out.append(
                        f"Map says P={om.claimed_probability:.0%}; {s.title} ({s.domain}, "
                        f"trust {s.confidence:.0%}) supports P={trade.probability:.0%}: \"{s.snippet}\""
                    )
        return out

    def _staleness(self, market: Market, om: OfficialMap | None) -> list[str]:
        if om is None or om.as_of is None:
            return []
        newest = max(
            (s.published_at for s in market.sources if s.published_at is not None),
            default=None,
        )
        if newest is not None and newest - om.as_of > self.staleness:
            days = (newest - om.as_of).days
            return [
                f"Official map is dated {om.as_of.date().isoformat()} but the newest strong "
                f"evidence is {days} days newer ({newest.date().isoformat()}). The map may be stale."
            ]
        return []

    @staticmethod
    def _divergence_penalty(om: OfficialMap | None, price: float | None) -> float:
        if om is None or om.claimed_probability is None or price is None:
            return 0.0
        return min(1.0, abs(price - om.claimed_probability)) * _MAX_DIVERGENCE_PENALTY

    @staticmethod
    def _narrative(score, silent, contradicted, stale, surprises, rejected) -> str:
        if score >= 80:
            head = f"Map fidelity {score}/100: the official map broadly matches the territory."
        elif score >= 50:
            head = f"Map fidelity {score}/100: the map has real blind spots — treat confident numbers as high-variance."
        else:
            head = f"Map fidelity {score}/100: the map materially diverges from the territory. Do not plan on it."
        parts = [head]
        if silent:
            parts.append(f"{len(silent)} load-bearing item(s) the map never mentions.")
        if contradicted:
            parts.append(f"{len(contradicted)} map claim(s) disputed by high-confidence evidence.")
        if stale:
            parts.append("The map is stale relative to the evidence.")
        if surprises:
            parts.append(f"{len(surprises)} assumption(s) surprised the market creator.")
        if rejected:
            parts.append(f"{len(rejected)} assumption(s) were rejected as wrong.")
        return " ".join(parts)


def variance_band(fidelity_score: int, price: float) -> tuple[float, float]:
    """PRD 7.4: display confidence proportional to fidelity.

    A low-fidelity market is shown as a wide probability band even if
    agents are confident. Returns (lo, hi) clamped to [0.01, 0.99].
    """
    half_width = (100 - fidelity_score) / 100 * 0.25
    return (max(0.01, price - half_width), min(0.99, price + half_width))
