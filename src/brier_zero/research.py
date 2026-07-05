"""Research Agent scaffolding (PRD 5.2): evidence in, assessment out.

The evidence engine is deliberately split from I/O: callers hand in
already-fetched documents (public sources, internal docs), the agent
scores credibility, synthesizes a probability assessment, and produces the
trade payload. Web scraping lives outside this module so the core stays
deterministic and testable; an LLM-backed assessor can be plugged in the
same way as the restater.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from .models import Source, Trade

# Domain reputation prior: neutral 0.5, well-known primary/press domains up,
# unknown blogs down. Extend freely — this is a prior, not a verdict.
_DOMAIN_PRIORS = {
    "reuters.com": 0.85, "apnews.com": 0.85, "bloomberg.com": 0.8,
    "wsj.com": 0.8, "ft.com": 0.8, "nytimes.com": 0.75, "arstechnica.com": 0.7,
    "sec.gov": 0.95, "gov": 0.85, "edu": 0.7,
    "github.com": 0.65, "arxiv.org": 0.7,
    "twitter.com": 0.35, "x.com": 0.35, "reddit.com": 0.35, "medium.com": 0.4,
}


def credibility(source: Source, now: datetime | None = None) -> float:
    """Domain reputation + recency -> 0..1 trust rating (PRD: 'not just
    citations, but trust ratings')."""
    now = now or datetime.now(timezone.utc)
    prior = _DOMAIN_PRIORS.get(source.domain, 0.5)
    if prior == 0.5:  # try TLD fallback
        tld = source.domain.rsplit(".", 1)[-1] if "." in source.domain else ""
        prior = _DOMAIN_PRIORS.get(tld, 0.5)
    score = prior
    if source.published_at is not None:
        age = now - source.published_at
        if age <= timedelta(days=30):
            score = min(1.0, score + 0.1)
        elif age > timedelta(days=365):
            score = max(0.0, score - 0.15)
    return round(score, 3)


@dataclass
class EvidenceItem:
    source: Source
    supports_yes: bool          # does this evidence push toward YES?
    strength: float = 0.5       # 0..1 how strongly, per the analyst/agent


@dataclass
class Assessment:
    probability: float
    rationale: str
    sources: list[Source]
    skill_ids: list[str]
    evidence: list[EvidenceItem] = field(default_factory=list)


class ResearchAgent:
    """Synthesizes evidence into a probability via credibility-weighted
    log-odds pooling, then emits a Trade for the market engine."""

    def __init__(self, agent_id: str, skill_ids: list[str] | None = None):
        self.agent_id = agent_id
        self.skill_ids = skill_ids or []

    def assess(self, evidence: list[EvidenceItem], prior: float = 0.5) -> Assessment:
        import math
        odds = math.log(prior / (1 - prior))
        for item in evidence:
            item.source.confidence = credibility(item.source)
            direction = 1.0 if item.supports_yes else -1.0
            # weight: how strong the evidence is x how much we trust the source
            odds += direction * 2.0 * item.strength * item.source.confidence
        probability = 1 / (1 + math.exp(-odds))
        probability = min(0.99, max(0.01, probability))
        yes_n = sum(1 for e in evidence if e.supports_yes)
        rationale = (
            f"Pooled {len(evidence)} evidence item(s) ({yes_n} supporting YES) weighted by "
            f"source trust; posterior P={probability:.0%}."
        )
        return Assessment(
            probability=round(probability, 4),
            rationale=rationale,
            sources=[e.source for e in evidence],
            skill_ids=list(self.skill_ids),
            evidence=evidence,
        )

    def trade(self, assessment: Assessment) -> Trade:
        return Trade(
            agent_id=self.agent_id,
            probability=assessment.probability,
            rationale=assessment.rationale,
            skill_ids=assessment.skill_ids,
            sources=assessment.sources,
        )
