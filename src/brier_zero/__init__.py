"""Brier Zero — Map/Territory Detection Engine.

Agent-only prediction markets that emit self-contained HTML intelligence
artifacts, detect where the official map diverges from the territory, and
audit their own research skills after every resolution.
"""

from .audit import SkillAuditPipeline
from .engine import MarketEngine
from .fidelity import MapFidelityScorer, variance_band
from .models import (
    Assumption,
    AssumptionStatus,
    Market,
    MarketStatus,
    MapTerritoryRisk,
    OfficialMap,
    Question,
    Signal,
    Source,
    Trade,
    Whisper,
)
from .proxy import EmployeeDirectory, EmployeeProxyAgent
from .research import EvidenceItem, ResearchAgent, credibility
from .restatement import HeuristicRestater, RestatementProtocol
from .scoring import Leaderboard, brier_index, brier_score, calibration_curve

__version__ = "0.1.0"

__all__ = [
    "Assumption", "AssumptionStatus", "EmployeeDirectory", "EmployeeProxyAgent",
    "EvidenceItem", "HeuristicRestater", "Leaderboard", "MapFidelityScorer",
    "MapTerritoryRisk", "Market", "MarketEngine", "MarketStatus", "OfficialMap",
    "Question", "ResearchAgent", "RestatementProtocol", "Signal", "SkillAuditPipeline",
    "Source", "Trade", "Whisper", "brier_index", "brier_score", "calibration_curve",
    "credibility", "variance_band",
]
