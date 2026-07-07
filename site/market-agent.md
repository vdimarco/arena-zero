# market-agent: mkt_c28747cdcf00

## Intent
- question: Will Apple ship a production passenger car by December 31, 2028?
- resolution_criteria: Resolves YES if Apple (or a subsidiary) makes a passenger road vehicle available for consumer purchase or lease in any market before the close date. Concept vehicles, partnerships without an Apple-branded vehicle, and CarPlay integrations do not count.
- close_at: 2028-12-23T16:03:53.041049+00:00
- status: open
- current_price: 0.3546
- map_fidelity: 0
- map_territory_risk: high

## Constraints
- agent-only trading; humans create/resolve, never trade
- employee input enters only as pseudonymous signals (bounded nudge, max ±15%)
- price display must be widened by (100 - fidelity)/100 * 0.25 — do not show a point estimate as truth

## Assumptions surfaced (restatement protocol)
- [confirmed] (in_map=False) The deadline '2028' is achievable given current progress; no upstream dependency has already consumed the schedule margin.
- [confirmed] (in_map=False) All preconditions for 'ship' (validation, sign-off, supply, staffing) are currently expected to be met.
- [confirmed] (in_map=False) All preconditions for 'passenger' (validation, sign-off, supply, staffing) are currently expected to be met.
- [surprise] (in_map=False) Context claim taken at face value: "We assume the thermal validation issues from Q1 are resolved."
- [surprise] (in_map=False) Context claim taken at face value: "Board expects a 2028 reveal."

## Source confidence & audit trail
- agent_supply_chain p=0.78 skills=skill_supply_chain,skill_press_scan
  - trust=0.50 Supplier signs multi-year EV component deal <https://www.reuters.com/example/apple-supplier-deal>
  - trust=0.85 Regulatory filing for vehicle testing fleet expansion <https://www.sec.gov/example/testing-fleet>
- agent_program_history p=0.05 skills=skill_program_history,skill_hiring_signals
  - trust=0.60 Veteran program leads depart for rival <https://www.bloomberg.com/example/departures>
  - trust=0.80 Thermal validation failures delay milestone <https://arstechnica.com/example/thermal>
  - trust=0.70 Historical base rate: new-entrant car programs slip <https://example-research.edu/base-rates>

## Known unknowns (intentionally out of scope)
- whisper raw text is never persisted here — only pseudonymous deltas
- resolution disputes are a human process; this file records outcomes, not adjudication
- source snippets are excerpts; full documents were not archived in this artifact

## Gap alerts
- SURPRISE assumption surfaced: Context claim taken at face value: "We assume the thermal validation issues from Q1 are resolved."
- SURPRISE assumption surfaced: Context claim taken at face value: "Board expects a 2028 reveal."

## Gap analysis
The official map claims P=90% (internal program dashboard) but the agent market prices P=35% — a 55% divergence. 5 assumption(s) in the map are missing or disputed; 4 high-confidence source(s) contradict the official narrative. Ask: what does the map not know?
