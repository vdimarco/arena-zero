"""Brier scoring, difficulty-adjusted Brier Index, calibration, leaderboard.

Brier score for a binary outcome: (p - o)^2 where o is 1.0/0.0.
Lower is better; 0.25 is the score of a permanently uncertain (p=0.5) agent.

The Brier Index (PRD 5.6) rescales to 0..100% where 50% means "no better
than always saying 50/50", 100% is perfect, and it is difficulty-adjusted:
beating the market consensus at close is worth more on questions where the
consensus itself was badly calibrated.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import AgentProfile


def brier_score(probability: float, outcome: bool) -> float:
    o = 1.0 if outcome else 0.0
    return (probability - o) ** 2


def brier_index(probability: float, outcome: bool, consensus_at_close: float | None = None) -> float:
    """0..100 difficulty-adjusted score.

    Base: 100 * (1 - bs/0.25) clamped to [0, 100] — i.e. skill over coin-flip.
    Difficulty adjustment: shift by how much the agent beat (or lost to)
    the closing consensus, so being right when the crowd was wrong pays more.
    """
    bs = brier_score(probability, outcome)
    base = max(0.0, min(100.0, 100.0 * (1.0 - bs / 0.25)))
    if consensus_at_close is None:
        return base
    edge = brier_score(consensus_at_close, outcome) - bs   # >0: beat consensus
    adjusted = base + 50.0 * edge / 0.25
    return max(0.0, min(100.0, adjusted))


@dataclass
class CalibrationBucket:
    lo: float
    hi: float
    forecasts: int = 0
    hits: int = 0

    @property
    def midpoint(self) -> float:
        return (self.lo + self.hi) / 2

    @property
    def hit_rate(self) -> float | None:
        return self.hits / self.forecasts if self.forecasts else None


def calibration_curve(pairs: list[tuple[float, bool]], buckets: int = 10) -> list[CalibrationBucket]:
    """Bucket (probability, outcome) pairs to measure calibration."""
    out = [CalibrationBucket(i / buckets, (i + 1) / buckets) for i in range(buckets)]
    for p, o in pairs:
        idx = min(int(p * buckets), buckets - 1)
        out[idx].forecasts += 1
        out[idx].hits += 1 if o else 0
    return out


@dataclass
class Leaderboard:
    """Tracks agent reputation across resolved markets (PRD 5.6).

    Reputation is a multiplicative trade weight: agents that persistently
    beat the coin-flip baseline gain weight, agents that lose it shed weight.
    Bounded so no agent can dominate or be silenced entirely.
    """
    profiles: dict[str, AgentProfile] = field(default_factory=dict)
    min_reputation: float = 0.2
    max_reputation: float = 5.0

    def profile(self, agent_id: str) -> AgentProfile:
        if agent_id not in self.profiles:
            self.profiles[agent_id] = AgentProfile(agent_id=agent_id)
        return self.profiles[agent_id]

    def record(self, agent_id: str, probability: float, outcome: bool) -> float:
        """Record a resolved forecast; returns the agent's new reputation."""
        prof = self.profile(agent_id)
        bs = brier_score(probability, outcome)
        prof.resolved_count += 1
        prof.brier_sum += bs
        # 0.25 = coin-flip baseline. Better than baseline -> multiply up.
        factor = 1.0 + (0.25 - bs)
        prof.reputation = max(self.min_reputation, min(self.max_reputation, prof.reputation * factor))
        return prof.reputation

    def rankings(self, public: bool = True) -> list[AgentProfile]:
        ranked = sorted(
            (p for p in self.profiles.values() if p.resolved_count > 0),
            key=lambda p: (p.mean_brier if p.mean_brier is not None else 1.0),
        )
        if public:
            return ranked
        return sorted(self.profiles.values(), key=lambda p: -p.reputation)
