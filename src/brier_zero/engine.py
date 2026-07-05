"""Market Engine (PRD 5.1 / 6.1): agent-only trading with a restatement gate.

Lifecycle:  DRAFT --restate--> RESTATEMENT_REVIEW --review--> OPEN
            --close_at passes--> CLOSED --resolve--> RESOLVED

Markets are created by humans, traded only by agents. Price is a weighted
aggregate of agent trades (weight = reputation, discounted when map
fidelity is low) nudged by pseudonymous employee signals. Resolution runs
Brier scoring, updates the leaderboard, and triggers the skill audit.
"""

from __future__ import annotations

from datetime import datetime

from .audit import SkillAuditPipeline, SkillAuditReport
from .fidelity import MapFidelityScorer
from .models import (
    Market,
    MarketStatus,
    OfficialMap,
    Question,
    Resolution,
    Signal,
    Trade,
    utcnow,
)
from .restatement import RestatementProtocol, gap_analysis_from_divergence
from .scoring import Leaderboard, brier_index

_SIGNAL_MAX_NUDGE = 0.15   # cap on how far employee signals can move the price
_DIVERGENCE_THRESHOLD = 0.30


class MarketEngine:
    def __init__(
        self,
        restatement: RestatementProtocol | None = None,
        fidelity: MapFidelityScorer | None = None,
        leaderboard: Leaderboard | None = None,
        skill_audit: SkillAuditPipeline | None = None,
    ):
        self.restatement = restatement or RestatementProtocol()
        self.fidelity = fidelity or MapFidelityScorer()
        self.leaderboard = leaderboard or Leaderboard()
        self.skill_audit = skill_audit or SkillAuditPipeline()
        self.markets: dict[str, Market] = {}

    # -- creation & restatement gate ------------------------------------

    def create_market(self, question: Question, official_map: OfficialMap | None = None) -> Market:
        self._validate_question(question)
        market = Market(question=question, official_map=official_map)
        self.markets[market.id] = market
        return market

    @staticmethod
    def _validate_question(question: Question) -> None:
        if not question.text.strip().endswith("?"):
            raise ValueError("market question must be a question")
        if not question.resolution_criteria.strip():
            raise ValueError("resolution criteria are required — vague markets are unresolvable")
        if question.close_at <= question.created_at:
            raise ValueError("close date must be in the future")

    def run_restatement(self, market: Market):
        return self.restatement.run(market)

    def review_restatement(self, market: Market, verdicts, accepted: bool = True, correction: str = "") -> Market:
        return self.restatement.review(market, verdicts, accepted=accepted, correction=correction)

    # -- trading ---------------------------------------------------------

    def place_trade(self, market: Market, trade: Trade, at: datetime | None = None) -> float:
        if market.status is not MarketStatus.OPEN:
            raise ValueError(f"market is {market.status.value}, not open for trading")
        at = at or utcnow()
        if at >= market.question.close_at:
            market.status = MarketStatus.CLOSED
            raise ValueError("market is past its close date")
        market.trades.append(trade)
        return self._reprice(market, at)

    def apply_signal(self, market: Market, signal: Signal, at: datetime | None = None) -> float:
        if market.status is not MarketStatus.OPEN:
            raise ValueError(f"market is {market.status.value}, not open for signals")
        # Revised signal from the same pseudonym replaces the old one.
        market.signals = [s for s in market.signals if s.pseudonym != signal.pseudonym]
        market.signals.append(signal)
        return self._reprice(market, at or utcnow())

    def price(self, market: Market) -> float:
        if market.price_history:
            return market.price_history[-1][1]
        if market.official_map and market.official_map.claimed_probability is not None:
            return market.official_map.claimed_probability
        return 0.5

    def _reprice(self, market: Market, at: datetime) -> float:
        """Reputation-weighted mean of each agent's latest trade, then a
        bounded nudge from employee signals, then fidelity bookkeeping."""
        latest: dict[str, Trade] = {}
        for t in market.trades:
            latest[t.agent_id] = t
        if latest:
            num = den = 0.0
            for t in latest.values():
                w = self.leaderboard.profile(t.agent_id).reputation
                num += w * t.probability
                den += w
            price = num / den
        else:
            price = self.price(market)

        nudge = sum(s.delta * s.confidence for s in market.signals)
        nudge = max(-_SIGNAL_MAX_NUDGE, min(_SIGNAL_MAX_NUDGE, nudge))
        price = min(0.99, max(0.01, price + nudge))

        market.price_history.append((at, price))
        # Keep the meta layer current: fidelity + auto gap analysis (PRD 5.4)
        self.fidelity.score(market, price=price)
        gap_analysis_from_divergence(market, price, threshold=_DIVERGENCE_THRESHOLD)
        return price

    # -- close & resolve --------------------------------------------------

    def close(self, market: Market) -> None:
        if market.status is not MarketStatus.OPEN:
            raise ValueError(f"cannot close a {market.status.value} market")
        market.status = MarketStatus.CLOSED

    def resolve(self, market: Market, outcome: bool, resolved_by: str = "human", notes: str = "") -> SkillAuditReport:
        """Resolve, score every agent, update reputations, run the skill audit."""
        if market.status is MarketStatus.OPEN:
            self.close(market)
        if market.status is not MarketStatus.CLOSED:
            raise ValueError(f"cannot resolve a {market.status.value} market")
        market.resolution = Resolution(outcome=outcome, resolved_by=resolved_by, notes=notes)
        market.status = MarketStatus.RESOLVED

        consensus = market.price_history[-1][1] if market.price_history else 0.5
        latest: dict[str, Trade] = {}
        for t in market.trades:
            latest[t.agent_id] = t
        for agent_id, t in latest.items():
            self.leaderboard.record(agent_id, t.probability, outcome)
            t.rationale += (
                f" [resolved {'YES' if outcome else 'NO'}; "
                f"Brier Index {brier_index(t.probability, outcome, consensus):.0f}/100]"
            )
        return self.skill_audit.audit(market)
