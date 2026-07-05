"""BZ-102: Research Agent Restatement Protocol.

Before any market is finalized, the research agent must restate its
understanding of the question and surface the assumptions it is trading
on. The creator reviews each assumption; a surprise or rejection flags the
market as high map/territory risk and raises a gap alert.

Assumption surfacing is deliberately pluggable: `HeuristicRestater` is a
deterministic, dependency-free baseline that finds presuppositions embedded
in the question text (deadlines, dependencies, definitional ambiguity).
An LLM-backed restater can implement the same protocol interface.
"""

from __future__ import annotations

import re
from typing import Protocol

from .models import (
    Assumption,
    AssumptionStatus,
    GapAnalysis,
    MapTerritoryRisk,
    Market,
    MarketStatus,
    OfficialMap,
    Question,
    Restatement,
)


class Restater(Protocol):
    def restate(self, question: Question, official_map: OfficialMap | None) -> Restatement: ...


_DEPENDENCY_WORDS = re.compile(
    r"\b(ship|launch|release|deliver|tape[- ]?out|approve|certif\w+|pass\w*|complete|close|sign)\b",
    re.IGNORECASE,
)
_DATE_PATTERN = re.compile(r"\b(20\d{2}|Q[1-4]\s*20\d{2}|by\s+\w+\s+20\d{2})\b", re.IGNORECASE)
_VAGUE_TERMS = re.compile(
    r"\b(success\w*|fail\w*|on[- ]track|significant\w*|major|soon|meaningful|viable|ready)\b",
    re.IGNORECASE,
)


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


class HeuristicRestater:
    """Deterministic assumption surfacing from question + context text."""

    def restate(self, question: Question, official_map: OfficialMap | None) -> Restatement:
        assumptions: list[Assumption] = []
        notes: list[str] = []
        map_text = (official_map.text if official_map else "").lower()

        def add(text: str) -> None:
            stated = _mentioned_in(map_text, text)
            assumptions.append(Assumption(text=text, stated_in_map=stated))

        # 1. Deadline presupposition: a date in the question implies the whole
        #    upstream chain must land before it, which the map rarely states.
        for m in _DATE_PATTERN.finditer(question.text):
            add(
                f"The deadline '{m.group(0)}' is achievable given current progress; "
                "no upstream dependency has already consumed the schedule margin."
            )

        # 2. Dependency verbs presuppose their preconditions are on track.
        for m in _DEPENDENCY_WORDS.finditer(question.text):
            add(
                f"All preconditions for '{m.group(0).lower()}' (validation, sign-off, "
                "supply, staffing) are currently expected to be met."
            )

        # 3. Vague resolution terms are a definitional assumption.
        for m in _VAGUE_TERMS.finditer(question.resolution_criteria or question.text):
            add(
                f"All parties share one definition of '{m.group(0).lower()}' — the "
                "resolution criteria will not be disputed at close."
            )

        # 4. Context sentences that carry hedges are hidden assumptions.
        for sent in _sentences(question.context):
            if re.search(r"\b(assum\w+|presum\w+|should|expect\w*|believe|hope)\b", sent, re.IGNORECASE):
                add(f"Context claim taken at face value: \"{sent}\"")

        if not assumptions:
            notes.append("No implicit assumptions detected; question is unusually well-specified.")

        paraphrase = self._paraphrase(question)
        return Restatement(paraphrase=paraphrase, assumptions=assumptions, interpretation_notes=notes)

    @staticmethod
    def _paraphrase(question: Question) -> str:
        return (
            f"I read this market as asking: {question.text.strip()} "
            f"It resolves YES only if: {question.resolution_criteria.strip()} "
            f"by {question.close_at.date().isoformat()}."
        )


def _mentioned_in(map_text: str, assumption_text: str) -> bool:
    """Loose lexical check: does the map mention the assumption's key nouns?"""
    if not map_text:
        return False
    words = [w for w in re.findall(r"[a-z]{5,}", assumption_text.lower())
             if w not in {"assumption", "currently", "expected", "definition"}]
    if not words:
        return False
    hits = sum(1 for w in words if w in map_text)
    return hits >= max(1, len(words) // 3)


class RestatementProtocol:
    """Drives the restate -> review -> finalize gate on a market."""

    def __init__(self, restater: Restater | None = None):
        self.restater = restater or HeuristicRestater()

    def run(self, market: Market) -> Restatement:
        if market.status is not MarketStatus.DRAFT:
            raise ValueError(f"restatement runs on DRAFT markets, not {market.status}")
        restatement = self.restater.restate(market.question, market.official_map)
        market.restatement = restatement
        market.status = MarketStatus.RESTATEMENT_REVIEW
        return restatement

    def review(
        self,
        market: Market,
        verdicts: dict[str, AssumptionStatus],
        accepted: bool = True,
        correction: str = "",
    ) -> Market:
        """Creator reviews each assumption by id and accepts/corrects the paraphrase.

        Any SURPRISE or REJECTED verdict — or a rejected/corrected paraphrase —
        flags the market high map/territory risk and records a gap alert
        (BZ-102 requirement).
        """
        if market.status is not MarketStatus.RESTATEMENT_REVIEW or market.restatement is None:
            raise ValueError("market has no restatement awaiting review")
        rst = market.restatement
        for a in rst.assumptions:
            if a.id in verdicts:
                a.status = verdicts[a.id]
        rst.reviewed = True
        rst.accepted = accepted
        rst.correction = correction

        surprises, rejected = rst.surprises, rst.rejected
        if surprises or rejected or not accepted or correction:
            market.risk = MapTerritoryRisk.HIGH
            for a in surprises:
                market.gap_alerts.append(f"SURPRISE assumption surfaced: {a.text}")
            for a in rejected:
                market.gap_alerts.append(f"REJECTED assumption (map was wrong): {a.text}")
            if not accepted or correction:
                market.gap_alerts.append(
                    "Restatement corrected by creator — the question meant something "
                    f"different than the agent understood. Correction: {correction or 'n/a'}"
                )
        market.status = MarketStatus.OPEN
        return market


def gap_analysis_from_divergence(
    market: Market, price: float, threshold: float = 0.30
) -> GapAnalysis | None:
    """PRD 5.4: when price diverges >threshold from the official map's claim,
    auto-generate a Map/Territory Gap Analysis instead of just showing a number."""
    om = market.official_map
    if om is None or om.claimed_probability is None:
        return None
    divergence = abs(price - om.claimed_probability)
    if divergence <= threshold:
        return None
    missing = [
        a for a in (market.restatement.assumptions if market.restatement else [])
        if not a.stated_in_map or a.status in (AssumptionStatus.SURPRISE, AssumptionStatus.REJECTED)
    ]
    contradictions = [
        f"{s.title} ({s.domain}): \"{s.snippet}\""
        for s in market.sources
        if s.confidence >= 0.6
    ][:5]
    narrative = (
        f"The official map claims P={om.claimed_probability:.0%} ({om.source_name}) but the "
        f"agent market prices P={price:.0%} — a {divergence:.0%} divergence. "
        f"{len(missing)} assumption(s) in the map are missing or disputed; "
        f"{len(contradictions)} high-confidence source(s) contradict the official narrative. "
        "Ask: what does the map not know?"
    )
    ga = GapAnalysis(
        divergence=divergence,
        missing_assumptions=missing,
        contradictions=contradictions,
        narrative=narrative,
    )
    market.gap_analysis = ga
    return ga
