"""BZ-302: Post-Resolution Skill Audit Pipeline — the meta-calibration loop.

After every market resolution, audit which research skills (source-weighting
heuristics, domain methodologies) produced accurate signals and which were
noise. Skills that consistently underperform the coin-flip baseline are
flagged as dead weight and down-weighted for future skill selection.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import Market
from .scoring import brier_score

_BASELINE = 0.25            # brier score of always answering 0.5
_DEAD_WEIGHT_MIN_USES = 3   # don't condemn a skill on one bad market


@dataclass
class SkillRecord:
    skill_id: str
    uses: int = 0
    brier_sum: float = 0.0
    history: list[tuple[str, float]] = field(default_factory=list)  # (market_id, brier)

    @property
    def mean_brier(self) -> float | None:
        return self.brier_sum / self.uses if self.uses else None

    @property
    def dead_weight(self) -> bool:
        return (
            self.uses >= _DEAD_WEIGHT_MIN_USES
            and self.mean_brier is not None
            and self.mean_brier > _BASELINE
        )

    @property
    def weight(self) -> float:
        """Selection weight for future markets: 1.0 neutral, <1 shrinking.

        edge = baseline - mean_brier; a skill 0.1 better than coin-flip gets
        1.4x, one 0.1 worse gets 0.6x, floored so recovery stays possible.
        """
        if self.mean_brier is None:
            return 1.0
        return max(0.1, 1.0 + 4 * (_BASELINE - self.mean_brier))


@dataclass
class SkillAuditEntry:
    skill_id: str
    market_id: str
    brier: float
    verdict: str  # "signal" | "noise"


@dataclass
class SkillAuditReport:
    market_id: str
    entries: list[SkillAuditEntry]
    dead_weight: list[str]
    narrative: str


class SkillAuditPipeline:
    def __init__(self) -> None:
        self.records: dict[str, SkillRecord] = {}

    def record_for(self, skill_id: str) -> SkillRecord:
        if skill_id not in self.records:
            self.records[skill_id] = SkillRecord(skill_id=skill_id)
        return self.records[skill_id]

    def audit(self, market: Market) -> SkillAuditReport:
        """Run after resolution: attribute each trade's Brier score to the
        skills that produced it, update running records, flag dead weight."""
        if market.resolution is None:
            raise ValueError("skill audit runs on resolved markets")
        outcome = market.resolution.outcome
        entries: list[SkillAuditEntry] = []
        for trade in market.trades:
            bs = brier_score(trade.probability, outcome)
            for skill_id in trade.skill_ids:
                rec = self.record_for(skill_id)
                rec.uses += 1
                rec.brier_sum += bs
                rec.history.append((market.id, bs))
                entries.append(
                    SkillAuditEntry(
                        skill_id=skill_id,
                        market_id=market.id,
                        brier=bs,
                        verdict="signal" if bs <= _BASELINE else "noise",
                    )
                )
        dead = sorted(r.skill_id for r in self.records.values() if r.dead_weight)
        narrative = self._narrative(entries, dead)
        return SkillAuditReport(market_id=market.id, entries=entries, dead_weight=dead, narrative=narrative)

    def selection_weights(self) -> dict[str, float]:
        """Feed audit results back into skill selection (BZ-302 requirement)."""
        return {sid: rec.weight for sid, rec in self.records.items()}

    @staticmethod
    def _narrative(entries: list[SkillAuditEntry], dead: list[str]) -> str:
        if not entries:
            return "No skill-attributed trades to audit."
        signal = sum(1 for e in entries if e.verdict == "signal")
        head = f"{signal}/{len(entries)} skill applications beat the coin-flip baseline."
        if dead:
            head += (
                f" Dead weight flagged: {', '.join(dead)} — written for an older/weaker "
                "model or a territory that has moved; deprecate or rewrite."
            )
        return head
