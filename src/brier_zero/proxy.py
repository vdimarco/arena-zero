"""BZ-201: Employee Proxy Agent — the pseudonymity layer.

Flow: a verified employee submits a *whisper* (attributed, sensitive).
The proxy verifies employment via an SSO-style directory, converts the
whisper into a structured probability *signal*, strips identity behind a
market-scoped pseudonym, and returns a reviewable draft (plus an HTML
Signal Artifact rendered by artifacts.slider). Only the signal — never the
whisper — enters the market.

Pseudonym design: HMAC-SHA256(secret, market_id || employee_id). Stable
within one market (an employee can revise their signal) but unlinkable
across markets, and not reversible without the server-side secret.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass

from .models import Signal, Whisper

_INTENSIFIERS = {
    "definitely": 0.9, "certain": 0.9, "sure": 0.8, "strongly": 0.8,
    "very": 0.7, "likely": 0.6, "probably": 0.6, "repeatedly": 0.7,
    "maybe": 0.4, "slightly": 0.3, "somewhat": 0.4, "might": 0.35,
}
_NEGATIVE = re.compile(
    r"\b(fail\w*|miss\w*|slip\w*|delay\w*|behind|broken?|block\w*|cancel\w*|"
    r"regress\w*|worse|churn\w*|attrition|resign\w*|over budget|red)\b",
    re.IGNORECASE,
)
_POSITIVE = re.compile(
    r"\b(pass\w*|ahead|on[- ]track|green|fixed|resolved|shipp\w*|land\w*|"
    r"succeed\w*|better|beat\w*|early)\b",
    re.IGNORECASE,
)
_EXPLICIT_DELTA = re.compile(r"([+-]?\d{1,2})\s*(?:%|percent|points?|pts?)", re.IGNORECASE)


class VerificationError(Exception):
    pass


@dataclass
class EmployeeDirectory:
    """SSO stand-in: maps opaque login tokens to internal employee ids.

    In production this is an OIDC/SAML verification against the company
    IdP; the interface is the contract — verify() proves employment and
    returns an internal id that never leaves the proxy.
    """
    tokens: dict[str, str]

    def verify(self, token: str) -> str:
        if token not in self.tokens:
            raise VerificationError("SSO verification failed: unknown or expired token")
        return self.tokens[token]


@dataclass
class DraftSignal:
    """What the employee reviews before submission (BZ-201 requirement)."""
    signal: Signal
    explanation: str          # how the whisper was interpreted
    scrubbed_terms: list[str]  # identifying/sensitive fragments that were dropped


class EmployeeProxyAgent:
    def __init__(self, directory: EmployeeDirectory, secret: bytes):
        self.directory = directory
        self.secret = secret

    def pseudonym(self, market_id: str, employee_id: str) -> str:
        digest = hmac.new(self.secret, f"{market_id}|{employee_id}".encode(), hashlib.sha256)
        return f"anon_{digest.hexdigest()[:10]}"

    def draft(self, whisper: Whisper) -> DraftSignal:
        """Verify, interpret, pseudonymize. Nothing enters the market yet."""
        employee_id = self.directory.verify(whisper.employee_token)
        delta, confidence, explanation = self._interpret(whisper.text)
        rationale, scrubbed = self._scrub(whisper.text, delta)
        signal = Signal(
            pseudonym=self.pseudonym(whisper.market_id, employee_id),
            delta=delta,
            confidence=confidence,
            public_rationale=rationale,
        )
        return DraftSignal(signal=signal, explanation=explanation, scrubbed_terms=scrubbed)

    @staticmethod
    def _interpret(text: str) -> tuple[float, float, str]:
        """Whisper text -> (delta, confidence, explanation).

        Deterministic baseline (LLM-swappable): explicit '+15%' style deltas
        win; otherwise direction comes from failure/success vocabulary and
        magnitude from intensifiers.
        """
        m = _EXPLICIT_DELTA.search(text)
        if m:
            delta = max(-1.0, min(1.0, int(m.group(1)) / 100))
            return delta, 0.7, f"Explicit adjustment '{m.group(0)}' taken at face value."

        neg = len(_NEGATIVE.findall(text))
        pos = len(_POSITIVE.findall(text))
        direction = -1.0 if neg > pos else (1.0 if pos > neg else 0.0)
        if direction == 0.0:
            return 0.0, 0.2, "No directional evidence found in whisper; neutral signal."

        confidence = 0.5
        for word, c in _INTENSIFIERS.items():
            if re.search(rf"\b{word}\b", text, re.IGNORECASE):
                confidence = max(confidence, c)
        strength = min(neg + pos, 4) / 4  # more corroborating terms, stronger nudge
        delta = direction * 0.05 * (1 + 3 * strength) * confidence
        label = "downward" if direction < 0 else "upward"
        return round(delta, 4), confidence, (
            f"Whisper reads as {label} evidence ({neg} negative / {pos} positive terms); "
            f"confidence {confidence:.0%} from language strength."
        )

    @staticmethod
    def _scrub(text: str, delta: float) -> tuple[str, list[str]]:
        """Produce an unattributable one-liner. Specific nouns, names, and
        numbers are dropped — the market gets direction, not detail."""
        scrubbed = re.findall(r"\b[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*\b|\d[\d,.]*", text)
        direction = "lower" if delta < 0 else ("higher" if delta > 0 else "unchanged")
        rationale = f"Verified internal signal: probability should be {direction}."
        return rationale, scrubbed
