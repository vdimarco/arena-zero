"""Core domain models for Brier Zero.

The vocabulary follows PRD v2.0: a human creates a *market* around a
*question* and an *official map* (the org's stated belief). Agents trade
probabilities into the market; verified employees nudge it through
pseudonymous *signals*. Everything downstream (fidelity scoring, artifacts,
skill audits) consumes these models.
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class MarketStatus(enum.Enum):
    DRAFT = "draft"                          # question written, restatement not yet done
    RESTATEMENT_REVIEW = "restatement_review"  # agent restated; awaiting creator review
    OPEN = "open"                            # finalized; agents may trade
    CLOSED = "closed"                        # past close date; awaiting resolution
    RESOLVED = "resolved"


class MapTerritoryRisk(enum.Enum):
    LOW = "low"
    HIGH = "high"  # restatement surprised the creator, or was rejected/corrected


class AssumptionStatus(enum.Enum):
    UNREVIEWED = "unreviewed"
    CONFIRMED = "confirmed"      # creator: "yes, that assumption holds"
    SURPRISE = "surprise"        # creator: "I never thought about that" -> gap
    REJECTED = "rejected"        # creator: "that assumption is wrong" -> gap


@dataclass
class Source:
    """A piece of evidence a research agent read."""
    title: str
    url: str
    snippet: str                       # the exact text the claim rests on
    published_at: datetime | None = None
    domain: str = ""
    confidence: float = 0.5            # 0..1 trust rating, set by credibility scoring
    id: str = field(default_factory=lambda: new_id("src"))

    def __post_init__(self) -> None:
        if not self.domain and "//" in self.url:
            self.domain = self.url.split("//", 1)[1].split("/", 1)[0]


@dataclass
class Assumption:
    """A load-bearing belief surfaced by the restatement protocol."""
    text: str
    stated_in_map: bool = False        # did the official map mention this at all?
    status: AssumptionStatus = AssumptionStatus.UNREVIEWED
    surfaced_by: str = "research_agent"
    id: str = field(default_factory=lambda: new_id("asm"))


@dataclass
class Restatement:
    """BZ-102: the agent's paraphrase of the question plus its assumptions."""
    paraphrase: str
    assumptions: list[Assumption]
    interpretation_notes: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=utcnow)
    # Filled in by creator review:
    reviewed: bool = False
    accepted: bool = False
    correction: str = ""

    @property
    def surprises(self) -> list[Assumption]:
        return [a for a in self.assumptions if a.status is AssumptionStatus.SURPRISE]

    @property
    def rejected(self) -> list[Assumption]:
        return [a for a in self.assumptions if a.status is AssumptionStatus.REJECTED]


@dataclass
class OfficialMap:
    """The org's stated belief: roadmap excerpt, dashboard, press line."""
    text: str
    claimed_probability: float | None = None   # e.g. dashboard says "90% on track"
    source_name: str = "roadmap"
    as_of: datetime | None = None


@dataclass
class Question:
    text: str
    resolution_criteria: str
    close_at: datetime
    created_at: datetime = field(default_factory=utcnow)
    context: str = ""                  # optional human-provided links/constraints
    id: str = field(default_factory=lambda: new_id("q"))


@dataclass
class Trade:
    agent_id: str
    probability: float                 # agent's asserted P(yes), 0..1
    rationale: str
    skill_ids: list[str] = field(default_factory=list)  # research skills used
    sources: list[Source] = field(default_factory=list)
    at: datetime = field(default_factory=utcnow)
    id: str = field(default_factory=lambda: new_id("trd"))

    def __post_init__(self) -> None:
        if not 0.0 <= self.probability <= 1.0:
            raise ValueError(f"probability must be in [0,1], got {self.probability}")


@dataclass
class Whisper:
    """Raw, attributed employee input. Never leaves the proxy layer."""
    employee_token: str                # SSO-verified identity token
    text: str                          # e.g. "recent thermal tests failed twice"
    market_id: str


@dataclass
class Signal:
    """Pseudonymized output of the proxy agent — safe to enter the market."""
    pseudonym: str                     # stable per (market, employee), unlinkable across markets
    delta: float                       # probability adjustment, -1..1
    confidence: float                  # 0..1
    public_rationale: str              # scrubbed one-liner, no identifying detail
    at: datetime = field(default_factory=utcnow)
    id: str = field(default_factory=lambda: new_id("sig"))


@dataclass
class AgentProfile:
    agent_id: str
    reputation: float = 1.0            # multiplicative trade weight, updated on resolution
    resolved_count: int = 0
    brier_sum: float = 0.0

    @property
    def mean_brier(self) -> float | None:
        return self.brier_sum / self.resolved_count if self.resolved_count else None


@dataclass
class GapAnalysis:
    """Auto-generated when market price diverges from the official map."""
    divergence: float                  # |price - map claim|
    missing_assumptions: list[Assumption]
    contradictions: list[str]          # map claims contradicted by evidence
    narrative: str
    created_at: datetime = field(default_factory=utcnow)


@dataclass
class FidelityReport:
    """BZ-301 output: how well the official map matches the territory."""
    score: int                         # 0..100 map fidelity
    silent: list[str]                  # territory items the map never mentions
    contradicted: list[str]            # map claims evidence disputes
    stale: list[str]                   # map claims older than territory updates
    surfaced_assumptions: list[Assumption]
    narrative: str


@dataclass
class Resolution:
    outcome: bool
    resolved_at: datetime = field(default_factory=utcnow)
    resolved_by: str = "human"
    notes: str = ""


@dataclass
class Market:
    question: Question
    official_map: OfficialMap | None = None
    status: MarketStatus = MarketStatus.DRAFT
    risk: MapTerritoryRisk = MapTerritoryRisk.LOW
    restatement: Restatement | None = None
    trades: list[Trade] = field(default_factory=list)
    signals: list[Signal] = field(default_factory=list)
    price_history: list[tuple[datetime, float]] = field(default_factory=list)
    fidelity: FidelityReport | None = None
    gap_analysis: GapAnalysis | None = None
    gap_alerts: list[str] = field(default_factory=list)
    resolution: Resolution | None = None
    id: str = field(default_factory=lambda: new_id("mkt"))

    @property
    def sources(self) -> list[Source]:
        return [s for t in self.trades for s in t.sources]
