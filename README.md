# Brier Zero

**The Map/Territory Detection Engine** — an agent-only prediction market that
produces self-contained, interactive HTML intelligence artifacts, detects where
an organization's internal map (roadmaps, dashboards, official narratives)
diverges from the territory (ground truth, employee knowledge, market reality),
and audits its own research skills after every resolution.

> Weak teams fail loudly. Strong teams fail quietly, propagating bad
> assumptions across multi-quarter plans. The map is never inspected against
> the territory until it is too late.

See [PRD v2.0](https://linear.app/0x56/document/prd-v20-brier-zero-mapterritory-engine-df298f12b710)
for the full product spec.

## How it works

1. **A human creates a market**: a question, resolution criteria, a close date,
   and optionally the *official map* (what the dashboard/roadmap claims).
2. **Restatement gate (BZ-102)**: before the market opens, the research agent
   must restate the question and surface its load-bearing assumptions. If a
   surfaced assumption surprises the creator — or the creator corrects the
   restatement — the market is flagged **high map/territory risk** and a gap
   alert is recorded. A surprised founder is a gap detected early.
3. **Agents trade** (humans never do): research agents score source
   credibility, pool evidence into a probability, and place trades. Price is a
   reputation-weighted aggregate.
4. **Employees whisper (BZ-201)**: SSO-verified employees guide a proxy agent
   with natural-language whispers. The proxy converts them into bounded,
   pseudonymous probability signals — HMAC pseudonyms are stable within a
   market but unlinkable across markets. The market gets the signal; the
   journalist doesn't get the leak.
5. **The meta layer (BZ-301)**: every reprice recomputes the **Map Fidelity
   Score** (0–100) — where the map is silent, contradicted, or stale — and a
   >30% price/map divergence auto-generates a Map/Territory Gap Analysis.
   Displayed confidence is widened proportionally to lost fidelity: a
   confident agent with a bad map is dangerous.
6. **Resolution & meta-calibration (BZ-302)**: Brier scores update agent
   reputation and feed the skill audit pipeline, which flags "dead weight"
   research skills and down-weights them for future markets.

Every output is an **artifact, not a conversation** (BZ-101/103/202): a single
HTML file with 4-layer progressive disclosure (executive summary → chart &
signals → full reasoning & hover-to-verify sources → raw data & audit trail),
plus a structured `market-agent.md` for the next agent session.

## Quick start

```bash
# no dependencies beyond Python 3.10+
PYTHONPATH=src python3 -m brier_zero.demo dist
open dist/market-human.html      # the flagship artifact
open dist/index.html             # landing page A/B router (BZ-303)
```

```bash
PYTHONPATH=src python3 -m unittest discover -s tests   # run tests
```

## Library sketch

```python
from brier_zero import (MarketEngine, Question, OfficialMap, ResearchAgent,
                        EvidenceItem, Source, EmployeeDirectory,
                        EmployeeProxyAgent, Whisper)

engine = MarketEngine()
market = engine.create_market(
    Question(text="Will X ship by 2028?",
             resolution_criteria="Resolves YES if a production unit ships.",
             close_at=close_date),
    OfficialMap(text="Dashboard: on track.", claimed_probability=0.9),
)
engine.run_restatement(market)                     # BZ-102 gate
engine.review_restatement(market, verdicts)        # creator reviews assumptions

agent = ResearchAgent("skeptic", skill_ids=["skill_supply_chain"])
engine.place_trade(market, agent.trade(agent.assess(evidence)))

proxy = EmployeeProxyAgent(EmployeeDirectory(tokens=sso_tokens), secret=key)
draft = proxy.draft(Whisper(employee_token=tok, text="thermal failed twice", market_id=market.id))
engine.apply_signal(market, draft.signal)          # bounded ±15% nudge

engine.close(market)
audit = engine.resolve(market, outcome=False)      # Brier scoring + skill audit
```

## Repository layout

```
src/brier_zero/
  models.py       domain objects (Market, Question, OfficialMap, Signal, …)
  engine.py       market lifecycle: restatement gate → trading → resolution
  scoring.py      Brier score, difficulty-adjusted Brier Index, leaderboard
  restatement.py  BZ-102 restatement protocol (pluggable restater)
  fidelity.py     BZ-301 map fidelity scoring + variance band
  research.py     research agent: source credibility, evidence pooling
  proxy.py        BZ-201 employee proxy: SSO verify → pseudonymous signal
  audit.py        BZ-302 post-resolution skill audit pipeline
  artifacts/      BZ-101/103/202/303 self-contained HTML renderers + landing
  demo.py         end-to-end demo market ("Will Apple ship a car by 2028?")
tests/            unittest suite (no external deps)
```

## Design constraints

- **Agent-only trading.** No human trades, no payouts, no gambling surface —
  Brier score is a research metric.
- **Self-contained artifacts.** No CDN, no backend, no login; inline CSS/JS;
  works as an email attachment.
- **Pluggable intelligence.** The heuristic restater / whisper interpreter /
  evidence assessor are deterministic baselines behind small interfaces —
  swap in LLM-backed implementations without touching the engine.
- **Stdlib only.** The core has zero runtime dependencies.

## License

TBD (will be a FOSS license; tracked in 0X5-6).
