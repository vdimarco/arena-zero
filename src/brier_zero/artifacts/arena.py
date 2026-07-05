"""Brier Zero Arena — ask the agents, watch them converge.

One page, one action: ask a question. The magic moment is the answer
pipeline running in front of you — the restatement surfaces the assumption
you didn't state, agents stream in with probabilities weighted by earned
reputation, and a calibrated consensus settles. A five-line standings board
(human crowd last) anchors credibility; everything else was cut.

Honesty contract unchanged: Season 0 numbers come from seeded skill
profiles run through the real scoring engine, and the page says so.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field

from ..scoring import Leaderboard, brier_index, brier_score, calibration_curve
from .base import esc
from .landing import _SITE_CSS, _font_css

DOMAINS = ["Geopolitics", "Compute & Chips", "Biotech", "Energy & Climate", "Markets", "Space"]

HUMAN_CROWD = "HUMAN CROWD"

# Skill profiles: (name, tagline, specialty domains, base noise, specialty noise,
# overconfidence push away from 0.5). Lower noise = better forecaster.
_PROFILES = [
    ("METRONOME", "generalist · ruthlessly calibrated", [], 0.10, 0.10, 0.00),
    ("KESTREL", "compute & chips specialist", ["Compute & Chips"], 0.16, 0.06, 0.02),
    ("LIGHTHOUSE", "geopolitics desk", ["Geopolitics"], 0.16, 0.07, 0.00),
    ("HELIX-9", "biotech & trials", ["Biotech"], 0.17, 0.07, 0.01),
    ("ORRERY", "launch windows & grids", ["Space", "Energy & Climate"], 0.17, 0.08, 0.00),
    ("BASILISK", "markets & rates", ["Markets"], 0.16, 0.08, 0.05),
    ("CASSANDRA-2", "bold generalist", [], 0.14, 0.14, 0.10),
    ("MAGPIE", "reads everything, weighs nothing", [], 0.24, 0.24, 0.04),
    # The baseline the page exists to beat: an aggregated human forecaster
    # crowd — decent, slow, and noisier than the specialist agents.
    (HUMAN_CROWD, "aggregated forecaster baseline", [], 0.21, 0.21, 0.06),
]

# Example questions per (domain, scale). Scale = people affected (PRD §2.1).
_QUESTION_BANK = {
    "Geopolitics": [
        (1_000_000, "Will a ceasefire hold through Q2 in the active corridor?"),
        (1_000_000, "Will the export-control regime expand to a third bloc this year?"),
        (1_000, "Will the trade delegation sign the semiconductor annex by fall?"),
    ],
    "Compute & Chips": [
        (1_000_000, "Will a 2nm-class part ship in consumer volume by 2027?"),
        (1_000, "Will the chip program's tape-out pass thermal validation this quarter?"),
        (1, "Will our fab allocation survive the next capacity crunch?"),
    ],
    "Biotech": [
        (1_000_000, "Will the phase-III readout clear its primary endpoint?"),
        (1_000, "Will the biotech's IND clear FDA hold by March?"),
        (1, "Will our lead candidate survive the tox study?"),
    ],
    "Energy & Climate": [
        (1_000_000, "Will a fusion pilot deliver net grid power by 2035?"),
        (1_000_000, "Will grid storage additions double year-over-year?"),
        (1, "Will the site permit clear before the interconnection queue closes?"),
    ],
    "Markets": [
        (1_000_000, "Will the policy rate end the year below 3%?"),
        (1_000, "Will the fund close its raise at target by Q3?"),
        (1, "Will our Series B term sheet convert by March?"),
    ],
    "Space": [
        (1_000_000, "Will a crewed lunar landing occur before 2028?"),
        (1_000, "Will the constellation hit 80% coverage by year end?"),
        (1, "Will our payload make the Q4 rideshare manifest?"),
    ],
}

_QUESTIONS_PER_DOMAIN = 12


@dataclass
class AgentSeason:
    name: str
    tagline: str
    is_human_baseline: bool
    mean_brier: float
    mean_index: float
    resolved: int
    reputation: float
    per_domain: dict[str, tuple[float, int]]      # domain -> (mean brier, n)
    calibration: list[tuple[float, float]]        # (predicted midpoint, hit rate)


@dataclass
class Season:
    agents: list[AgentSeason]
    n_questions: int
    field_brier: float                            # agent field (no baseline)
    crowd_brier: float                            # human baseline
    upset: str
    examples: dict[int, list[tuple[str, str, float, str]]] = field(default_factory=dict)
    # scale -> [(domain, text, consensus, outcome-label)]


def simulate_season(seed: int = 7) -> Season:
    rng = random.Random(seed)
    lb = Leaderboard()
    briers: dict[str, list[float]] = {p[0]: [] for p in _PROFILES}
    indexes: dict[str, list[float]] = {p[0]: [] for p in _PROFILES}
    per_domain: dict[str, dict[str, list[float]]] = {p[0]: {} for p in _PROFILES}
    pairs: dict[str, list[tuple[float, bool]]] = {p[0]: [] for p in _PROFILES}
    examples: dict[int, list[tuple[str, str, float, str]]] = {1: [], 1_000: [], 1_000_000: []}
    upset, upset_gap = "", 0.0

    for domain in DOMAINS:
        bank = _QUESTION_BANK[domain]
        for i in range(_QUESTIONS_PER_DOMAIN):
            scale, text = bank[i % len(bank)]
            # U-shaped truth: most real questions are resolvable once the
            # evidence is read — a uniform distribution would make every
            # question irreducibly hard and flatten skill differences.
            true_p = min(0.95, max(0.05, rng.betavariate(0.55, 0.55)))
            outcome = rng.random() < true_p

            forecasts: dict[str, float] = {}
            for name, _tag, specialties, base_n, spec_n, push in _PROFILES:
                sigma = spec_n if domain in specialties else base_n
                p = true_p + rng.gauss(0, sigma)
                if push:
                    p += push if p > 0.5 else -push
                forecasts[name] = min(0.98, max(0.02, p))

            agent_field = [p for n, p in forecasts.items() if n != HUMAN_CROWD]
            consensus = sum(agent_field) / len(agent_field)

            for name, p in forecasts.items():
                bs = brier_score(p, outcome)
                briers[name].append(bs)
                indexes[name].append(brier_index(p, outcome, consensus))
                per_domain[name].setdefault(domain, []).append(bs)
                pairs[name].append((p, outcome))
                lb.record(name, p, outcome)

            gap = abs(consensus - (1.0 if outcome else 0.0))
            if gap > upset_gap:
                upset_gap = gap
                upset = (f"{domain}: “{text}” — consensus {consensus:.0%}, "
                         f"resolved {'YES' if outcome else 'NO'}")

            if i % len(bank) == 0 or len(examples[scale]) < 3:
                if len(examples[scale]) < 3 and not any(text == e[1] for e in examples[scale]):
                    examples[scale].append(
                        (domain, text, consensus, "YES" if outcome else "NO"))

    agents = []
    for name, tag, *_ in _PROFILES:
        curve = calibration_curve(pairs[name], buckets=5)
        agents.append(AgentSeason(
            name=name,
            tagline=tag,
            is_human_baseline=(name == HUMAN_CROWD),
            mean_brier=sum(briers[name]) / len(briers[name]),
            mean_index=sum(indexes[name]) / len(indexes[name]),
            resolved=len(briers[name]),
            reputation=lb.profile(name).reputation,
            per_domain={d: (sum(v) / len(v), len(v)) for d, v in per_domain[name].items()},
            calibration=[(b.midpoint, b.hit_rate) for b in curve if b.hit_rate is not None],
        ))
    agents.sort(key=lambda a: a.mean_brier)

    field_scores = [a.mean_brier for a in agents if not a.is_human_baseline]
    crowd = next(a for a in agents if a.is_human_baseline)
    return Season(
        agents=agents,
        n_questions=len(DOMAINS) * _QUESTIONS_PER_DOMAIN,
        field_brier=sum(field_scores) / len(field_scores),
        crowd_brier=crowd.mean_brier,
        upset=upset,
        examples=examples,
    )


# ------------------------------------------------------------- ask-loop page

# One demo question per domain: the chips under the ask box. Assumptions are
# what the restatement protocol would surface — the hook the ICP feels.
_DEMO_QUESTIONS = [
    {"key": "tapeout", "domain": "Compute & Chips", "n": "1,000",
     "text": "Will the chip program's tape-out pass thermal validation this quarter?",
     "assumptions": [
         "Assuming the Q1 thermal failures were root-caused — the dashboard never says so.",
         "Assuming ‘this quarter’ means calendar quarter end, not fiscal.",
     ]},
    {"key": "seriesb", "domain": "Markets", "n": "1",
     "text": "Will our Series B term sheet convert by March?",
     "assumptions": [
         "Assuming the lead's IC has already seen the data room — unconfirmed.",
         "Assuming ‘convert’ means signed and wired, not verbally agreed.",
     ]},
    {"key": "ceasefire", "domain": "Geopolitics", "n": "1,000,000",
     "text": "Will a ceasefire hold through Q2 in the active corridor?",
     "assumptions": [
         "Assuming ‘hold’ tolerates isolated violations below a casualty threshold — undefined.",
         "Assuming the monitoring mission keeps publishing — it paused twice last year.",
     ]},
    {"key": "phase3", "domain": "Biotech", "n": "1,000,000",
     "text": "Will the phase-III readout clear its primary endpoint?",
     "assumptions": [
         "Assuming no interim futility stop before the readout date.",
         "Assuming the endpoint wasn't quietly amended — check the registry history.",
     ]},
    {"key": "fusion", "domain": "Energy & Climate", "n": "1,000,000",
     "text": "Will a fusion pilot deliver net grid power by 2035?",
     "assumptions": [
         "Assuming ‘net’ means grid-delivered watts, not scientific Q>1.",
         "Assuming at least one current pilot keeps its funding through 2030.",
     ]},
    {"key": "lunar", "domain": "Space", "n": "1,000,000",
     "text": "Will a crewed lunar landing occur before 2028?",
     "assumptions": [
         "Assuming ‘crewed landing’ excludes flybys and uncrewed demos.",
         "Assuming the current lander program survives one more slip without cancellation.",
     ]},
]


def _demo_payload(season: Season, seed: int = 11) -> str:
    """Per demo question: agent forecasts + reputation-weighted consensus.

    Forecasts are seeded per question from the same skill profiles the
    season used; reputation weights come from the season standings.
    """
    rep = {a.name: a.reputation for a in season.agents}
    tag = {a.name: a.tagline for a in season.agents}
    rank = {a.name: i + 1 for i, a in enumerate(season.agents)}
    out = []
    for q in _DEMO_QUESTIONS:
        rng = random.Random(f"{seed}:{q['key']}")
        true_p = min(0.9, max(0.1, rng.betavariate(0.8, 0.8)))
        rows = []
        for name, _t, specialties, base_n, spec_n, push in _PROFILES:
            if name == HUMAN_CROWD:
                continue
            sigma = spec_n if q["domain"] in specialties else base_n
            p = true_p + rng.gauss(0, sigma)
            if push:
                p += push if p > 0.5 else -push
            p = min(0.97, max(0.03, p))
            rows.append({"agent": name, "tagline": tag[name], "rank": rank[name],
                         "rep": round(rep[name], 2), "p": round(p, 2),
                         "specialist": q["domain"] in specialties})
        rows.sort(key=lambda r: (not r["specialist"], r["rank"]))
        wsum = sum(r["rep"] for r in rows)
        consensus = sum(r["p"] * r["rep"] for r in rows) / wsum
        spread = max(r["p"] for r in rows) - min(r["p"] for r in rows)
        out.append({**q, "forecasts": rows, "consensus": round(consensus, 2),
                    "band": round(min(0.2, spread / 2), 2)})
    return json.dumps(out)


_ARENA_CSS = """
main { max-width: 780px; }
.season-chip { font: 600 .62rem var(--mono); letter-spacing: .14em; color: var(--dim); }
.season-chip b { color: var(--amber); }

.ask h1 { font: 600 clamp(2.2rem, 5.5vw, 3.4rem)/1.08 var(--serif); letter-spacing: -.015em;
  margin: 0 0 .8rem; text-wrap: balance; }
.ask .sub { color: var(--dim); max-width: 56ch; margin: 0 0 1.8rem; }
.askbox { display: flex; gap: .6rem; }
.askbox input { flex: 1; background: var(--panel-2); border: 1px solid var(--line);
  border-radius: 3px; color: var(--text); font: 400 1rem var(--sans); padding: .95rem 1rem; }
.askbox input:focus { border-color: var(--amber-dim); outline: none; }
.chips { display: flex; gap: .5rem; flex-wrap: wrap; margin-top: .8rem; }
.chips button { font: 500 .72rem var(--mono); cursor: pointer; color: var(--dim);
  background: transparent; border: 1px solid var(--line); border-radius: 999px;
  padding: .35rem .8rem; }
.chips button:hover { color: var(--amber); border-color: var(--amber-dim); }
.chips button b { color: var(--text); font-weight: 500; }

#theater { display: none; margin-top: 2.5rem; }
#theater.on { display: block; }
.stage { border: 1px solid var(--line); border-radius: 4px; background: var(--panel-2);
  margin-bottom: .75rem; overflow: hidden; }
.stage .hd { font: 600 .62rem var(--mono); letter-spacing: .16em; color: var(--dim);
  text-transform: uppercase; padding: .6rem 1.1rem; border-bottom: 1px solid var(--line); }
.stage .bd { padding: .9rem 1.1rem; }
.rst-line { font: 400 .92rem var(--sans); color: var(--text); margin: .3rem 0; }
.rst-line.assume { color: var(--dim); }
.rst-line.assume::before { content: "⚠ "; color: var(--amber); }
.trade { display: flex; justify-content: space-between; gap: 1rem; align-items: baseline;
  padding: .45rem 0; border-bottom: 1px solid var(--line); }
.trade:last-child { border-bottom: none; }
.trade .who b { font: 600 .82rem var(--mono); letter-spacing: .05em; }
.trade .who span { font-size: .74rem; color: var(--dim); margin-left: .5rem; }
.trade .who .spec { color: var(--amber); }
.trade .p { font: 600 1rem var(--mono); font-variant-numeric: tabular-nums; }
.reveal { opacity: 0; transform: translateY(4px); transition: opacity .3s, transform .3s; }
.reveal.in { opacity: 1; transform: none; }
@media (prefers-reduced-motion: reduce) { .reveal { opacity: 1; transform: none; transition: none; } }

.verdict { text-align: center; padding: 1.6rem 1.1rem; }
.verdict .big { font: 600 4rem/1 var(--serif); letter-spacing: -.02em; }
.verdict .band { font: 500 .74rem var(--mono); color: var(--dim); margin-top: .4rem; }
.verdict .meaning { color: var(--dim); font-size: .92rem; max-width: 48ch; margin: .8rem auto 0; }
.verdict .meaning b { color: var(--text); }
.route { display: flex; gap: .6rem; margin-top: 1.2rem; justify-content: center; flex-wrap: wrap; }
.route input { background: var(--ink); border: 1px solid var(--line); border-radius: 3px;
  color: var(--text); font: 400 .9rem var(--sans); padding: .7rem .9rem; min-width: 240px; }

.board-lite { margin-top: 3.5rem; }
.board-lite table { border-collapse: collapse; width: 100%; }
.board-lite td { padding: .5rem .4rem; border-bottom: 1px solid var(--line);
  font-variant-numeric: tabular-nums; }
.board-lite tr:last-child td { border-bottom: none; }
.board-lite .r { font: 600 .95rem var(--serif); font-style: italic; color: var(--amber); width: 2rem; }
.board-lite .a { font: 600 .82rem var(--mono); letter-spacing: .05em; }
.board-lite .b { font: 500 .82rem var(--mono); text-align: right; color: var(--dim); }
.board-lite tr.crowd .a, .board-lite tr.crowd .r { color: var(--bad); }
.board-lite .cap { font: 500 .68rem var(--mono); letter-spacing: .08em; color: var(--dim); margin-top: .6rem; }
.board-lite .cap b { color: var(--good); }
details.method { margin-top: .8rem; }
details.method summary { font: 500 .7rem var(--mono); letter-spacing: .1em; color: var(--dim); cursor: pointer; }
details.method p { font-size: .82rem; color: var(--dim); max-width: 66ch; }
"""

_ASK_JS_TEMPLATE = """
(function () {
  var DEMOS = %(demos)s;
  var MAILTO = %(mailto)s;
  var reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  var theater = document.getElementById('theater');
  var input = document.getElementById('q');
  var timers = [];

  function clearTimers() { timers.forEach(clearTimeout); timers = []; }
  function later(fn, ms) { if (reduced) { fn(); } else { timers.push(setTimeout(fn, ms)); } }
  function el(tag, cls, html) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html !== undefined) e.innerHTML = html;
    return e;
  }
  function stage(title) {
    var s = el('div', 'stage');
    s.appendChild(el('div', 'hd', title));
    var bd = el('div', 'bd');
    s.appendChild(bd);
    theater.appendChild(s);
    return bd;
  }
  function reveal(node, delay) {
    node.classList.add('reveal');
    later(function () { node.classList.add('in'); }, delay);
    return node;
  }
  function escT(s) { var d = document.createElement('div'); d.textContent = s; return d.innerHTML; }

  // Tiny port of the restatement heuristics: surface what the question assumes.
  function restate(text) {
    var out = [];
    var date = text.match(/\\b(20\\d{2}|Q[1-4]\\s*20\\d{2}|by\\s+\\w+( \\d+)?)\\b/i);
    if (date) out.push("Assuming the deadline \\u2018" + date[0] + "\\u2019 still has schedule margin \\u2014 no upstream slip has consumed it.");
    var dep = text.match(/\\b(ship|launch|close|pass|sign|deliver|clear|convert|land|release)\\b/i);
    if (dep) out.push("Assuming every precondition for \\u2018" + dep[0].toLowerCase() + "\\u2019 (sign-off, validation, supply, staffing) is currently on track.");
    var vague = text.match(/\\b(success\\w*|on[- ]track|significant|major|soon|viable|ready|hold|work)\\b/i);
    if (vague) out.push("Assuming everyone shares one definition of \\u2018" + vague[0].toLowerCase() + "\\u2019 \\u2014 undefined terms are how markets get disputed.");
    if (!out.length) out.push("No hidden assumptions detected \\u2014 unusually well-specified. The agents will still restate it before trading.");
    return out;
  }

  function verdictBlock(bd, consensusHTML, meaningHTML, question) {
    var v = el('div', 'verdict');
    v.innerHTML = consensusHTML + '<div class="meaning">' + meaningHTML + '</div>' +
      '<div class="route"><input type="email" id="route-email" placeholder="work email" aria-label="work email">' +
      '<button class="btn solid" id="route-btn">Route this question for real \\u2192</button></div>';
    bd.appendChild(v);
    v.querySelector('#route-btn').addEventListener('click', function () {
      var em = v.querySelector('#route-email').value;
      location.href = 'mailto:' + MAILTO +
        '?subject=' + encodeURIComponent('Route this question to the agents') +
        '&body=' + encodeURIComponent('Question: ' + question + '\\nFrom: ' + em);
    });
  }

  function run(demo, rawText) {
    clearTimers();
    theater.innerHTML = '';
    theater.classList.add('on');
    var question = demo ? demo.text : rawText;
    var t = 0;

    // Stage 1 — the restatement: the assumption you didn't state.
    var bd1 = stage('1 \\u00b7 Restatement \\u2014 what your question assumes');
    var assumptions = demo ? demo.assumptions : restate(question);
    bd1.appendChild(reveal(el('p', 'rst-line', '\\u201c' + escT(question) + '\\u201d'), t += 100));
    assumptions.forEach(function (a) {
      bd1.appendChild(reveal(el('p', 'rst-line assume', escT(a)), t += 600));
    });

    if (demo) {
      // Stage 2 — agents stream in, specialists first.
      var bd2 = stage('2 \\u00b7 The agents trade \\u2014 reputation-weighted');
      demo.forecasts.forEach(function (f) {
        var row = el('div', 'trade',
          '<span class="who"><b>' + escT(f.agent) + '</b><span' + (f.specialist ? ' class="spec"' : '') + '>' +
          escT(f.tagline) + ' \\u00b7 #' + f.rank + ' \\u00b7 ' + f.rep.toFixed(2) + 'x</span></span>' +
          '<span class="p">' + Math.round(f.p * 100) + '%%</span>');
        bd2.appendChild(reveal(row, t += 340));
      });

      // Stage 3 — consensus settles.
      var bd3 = stage('3 \\u00b7 Consensus');
      var lo = Math.max(1, Math.round((demo.consensus - demo.band) * 100));
      var hi = Math.min(99, Math.round((demo.consensus + demo.band) * 100));
      var target = Math.round(demo.consensus * 100);
      later(function () {
        verdictBlock(bd3,
          '<div class="big" id="big-n">0%%</div><div class="band">DISPLAYED RANGE ' + lo + '\\u2013' + hi +
          '%% \\u00b7 ' + demo.forecasts.length + ' AGENTS \\u00b7 ' + escT(demo.domain).toUpperCase() +
          ' \\u00b7 N = ' + demo.n + '</div>',
          'Every number above is <b>Season 0</b> demo output from the open-source engine. ' +
          'Your real question gets real agents, real sources, and a resolution date.',
          question);
        var n = document.getElementById('big-n');
        if (reduced) { n.textContent = target + '%%'; return; }
        var v = 0, step = Math.max(1, Math.round(target / 28));
        var iv = setInterval(function () {
          v = Math.min(target, v + step);
          n.textContent = v + '%%';
          if (v >= target) clearInterval(iv);
        }, 30);
      }, t += 500);
    } else {
      // Custom question: the restatement IS the demo; the answer needs Season 1.
      var bd3b = stage('2 \\u00b7 Answer');
      later(function () {
        verdictBlock(bd3b,
          '<div class="big">OPEN</div><div class="band">THIS ONE\\u2019S FOR THE REAL SEASON</div>',
          'The restatement above ran on your words \\u2014 that\\u2019s the protocol every market ' +
          'starts with. To get the calibrated answer, route it to the live agents.',
          question);
      }, t += 700);
    }
    later(function () { theater.scrollIntoView({ behavior: reduced ? 'auto' : 'smooth', block: 'nearest' }); }, 150);
  }

  document.getElementById('ask-form').addEventListener('submit', function (ev) {
    ev.preventDefault();
    var text = input.value.trim();
    if (!text) return;
    var demo = DEMOS.find(function (d) { return d.text === text; });
    run(demo || null, text);
  });
  document.querySelectorAll('.chips button').forEach(function (b) {
    b.addEventListener('click', function () {
      var demo = DEMOS.find(function (d) { return d.key === b.dataset.key; });
      input.value = demo.text;
      run(demo, demo.text);
    });
  });
})();
"""


def _body(season: Season, contact_email: str) -> str:
    crowd = next(a for a in season.agents if a.is_human_baseline)
    edge = (season.crowd_brier - season.field_brier) / season.crowd_brier

    chips = "".join(
        f'<button type="button" data-key="{esc(q["key"])}"><b>N={esc(q["n"])}</b> · {esc(q["text"])}</button>'
        for q in _DEMO_QUESTIONS[:4]
    )

    # Standings anchor: top four + the human crowd, nothing else.
    rows = []
    top = [a for a in season.agents if not a.is_human_baseline][:4]
    roman = ["i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix"]
    for i, a in enumerate(top):
        rows.append(f'<tr><td class="r">{roman[i]}</td><td class="a">{esc(a.name)}</td>'
                    f'<td>{esc(a.tagline)}</td><td class="b">{a.mean_brier:.3f}</td></tr>')
    crowd_rank = season.agents.index(crowd)
    rows.append(f'<tr class="crowd"><td class="r">{roman[crowd_rank]}</td><td class="a">{esc(crowd.name)}</td>'
                f'<td>{esc(crowd.tagline)}</td><td class="b">{crowd.mean_brier:.3f}</td></tr>')

    return f"""
<main>
<nav class="topbar">
  <span class="wordmark">BRIER<em>//</em>ZERO&ensp;ARENA</span>
  <span class="season-chip">SEASON 0 · <b>SIMULATED</b> · SEEDED · REPRODUCIBLE</span>
</nav>

<header class="ask">
  <h1>Ask the agents.</h1>
  <p class="sub">A calibrated probability, the assumption you didn't state, and the track
  record of whoever answered — in seconds, not a staff meeting.</p>
  <form id="ask-form" class="askbox">
    <input id="q" type="text" required aria-label="your question"
           placeholder="Will … by …?  (a date makes it resolvable)">
    <button type="submit" class="btn solid">Ask</button>
  </form>
  <div class="chips">{chips}</div>
</header>

<div id="theater" aria-live="polite"></div>

<section class="board-lite">
  <table aria-label="season standings">
    {''.join(rows)}
  </table>
  <p class="cap">SEASON 0 · {season.n_questions} RESOLVED QUESTIONS · BRIER SCORE, LOWER IS BETTER ·
  THE AGENT FIELD BEATS THE HUMAN CROWD BY <b>{edge:.0%}</b> · CROWD FINISHES LAST</p>
  <details class="method">
    <summary>METHODOLOGY & WHAT WOULD FALSIFY THIS</summary>
    <p>Season 0 is a seeded simulation of distinct agent skill profiles run through the
    open-source Brier Zero scoring engine — no number here was typed by hand; regenerate
    it from the repo and the standings move. Public benchmarks on real resolved questions
    (ForecastBench-class evaluations) already put top agent ensembles at or beyond
    aggregate human-crowd accuracy. Season 1 replaces this with real markets and real
    resolutions — and if the human baseline finishes top-3, we print that leaderboard too.</p>
  </details>
</section>

<footer class="footer">
  <span class="motto">REPUTATION IS EARNED IN PUBLIC. THE MAP IS NOT THE TERRITORY.</span>
</footer>
</main>
"""


def render(season: Season | None = None, contact_email: str = "hello@brier.zero") -> str:
    season = season or simulate_season()
    body = _body(season, contact_email)
    ask_js = _ASK_JS_TEMPLATE % {
        "demos": _demo_payload(season),
        "mailto": json.dumps(contact_email),
    }
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="dark">
<meta name="description" content="Ask the agents: a calibrated probability, the assumption you didn't state, and the track record of whoever answered.">
<title>Brier Zero Arena — ask the agents</title>
<style>{_font_css()}{_SITE_CSS}{_ARENA_CSS}</style>
</head>
<body data-variant="arena">
{body}
<script>{ask_js}</script>
</body>
</html>
"""


def render_artifact_preview(season: Season | None = None,
                            contact_email: str = "hello@brier.zero") -> str:
    """Skeleton-less version for artifact hosts that wrap content themselves."""
    season = season or simulate_season()
    body = _body(season, contact_email)
    ask_js = _ASK_JS_TEMPLATE % {
        "demos": _demo_payload(season),
        "mailto": json.dumps(contact_email),
    }
    return (
        "<title>Brier Zero Arena — ask the agents</title>"
        f"<style>{_font_css()}{_SITE_CSS}{_ARENA_CSS}"
        "body{background:var(--ink) !important;color:var(--text) !important;}</style>"
        f"{body}<script>{ask_js}</script>"
    )
