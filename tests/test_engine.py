import unittest
from datetime import timedelta

from brier_zero import (
    AssumptionStatus,
    EvidenceItem,
    MapTerritoryRisk,
    MarketEngine,
    MarketStatus,
    OfficialMap,
    Question,
    ResearchAgent,
    Source,
)
from brier_zero.models import utcnow


def make_question(**kw):
    defaults = dict(
        text="Will the project ship by 2028?",
        resolution_criteria="Resolves YES if a production unit is sold before close.",
        close_at=utcnow() + timedelta(days=30),
        context="We assume thermal validation already passed.",
    )
    defaults.update(kw)
    return Question(**defaults)


def open_market(engine, market):
    engine.run_restatement(market)
    engine.review_restatement(market, {})
    return market


class TestMarketLifecycle(unittest.TestCase):
    def setUp(self):
        self.engine = MarketEngine()

    def test_question_validation(self):
        with self.assertRaises(ValueError):
            self.engine.create_market(make_question(text="This is not a question."))
        with self.assertRaises(ValueError):
            self.engine.create_market(make_question(resolution_criteria="  "))
        with self.assertRaises(ValueError):
            self.engine.create_market(make_question(close_at=utcnow() - timedelta(days=1)))

    def test_restatement_gate_blocks_trading(self):
        m = self.engine.create_market(make_question())
        agent = ResearchAgent("a1")
        trade = agent.trade(agent.assess([]))
        with self.assertRaises(ValueError):
            self.engine.place_trade(m, trade)
        self.assertIs(m.status, MarketStatus.DRAFT)

    def test_surprise_flags_high_risk_and_gap_alert(self):
        m = self.engine.create_market(make_question())
        rst = self.engine.run_restatement(m)
        self.assertIs(m.status, MarketStatus.RESTATEMENT_REVIEW)
        self.assertTrue(rst.assumptions, "heuristic restater should surface assumptions")
        verdicts = {rst.assumptions[0].id: AssumptionStatus.SURPRISE}
        self.engine.review_restatement(m, verdicts)
        self.assertIs(m.risk, MapTerritoryRisk.HIGH)
        self.assertTrue(any("SURPRISE" in g for g in m.gap_alerts))
        self.assertIs(m.status, MarketStatus.OPEN)

    def test_correction_triggers_gap_alert(self):
        m = self.engine.create_market(make_question())
        self.engine.run_restatement(m)
        self.engine.review_restatement(m, {}, accepted=False, correction="question means EU launch only")
        self.assertIs(m.risk, MapTerritoryRisk.HIGH)
        self.assertTrue(any("corrected" in g for g in m.gap_alerts))

    def test_price_aggregation_reputation_weighted(self):
        m = open_market(self.engine, self.engine.create_market(make_question()))
        a1, a2 = ResearchAgent("hi_rep"), ResearchAgent("lo_rep")
        self.engine.leaderboard.profile("hi_rep").reputation = 4.0
        self.engine.leaderboard.profile("lo_rep").reputation = 1.0
        t1 = a1.trade(a1.assess([EvidenceItem(Source("x", "https://reuters.com/x", "s"), True, 0.9)]))
        t2 = a2.trade(a2.assess([EvidenceItem(Source("y", "https://reuters.com/y", "s"), False, 0.9)]))
        self.engine.place_trade(m, t1)
        price = self.engine.place_trade(m, t2)
        # weighted mean must sit closer to the high-reputation agent
        expected = (4.0 * t1.probability + 1.0 * t2.probability) / 5.0
        self.assertAlmostEqual(price, expected, places=6)

    def test_resolution_scores_and_updates_reputation(self):
        m = open_market(self.engine, self.engine.create_market(make_question()))
        good, bad = ResearchAgent("good"), ResearchAgent("bad")
        self.engine.place_trade(m, good.trade(good.assess(
            [EvidenceItem(Source("g", "https://reuters.com/g", "s"), True, 0.9)])))
        self.engine.place_trade(m, bad.trade(bad.assess(
            [EvidenceItem(Source("b", "https://reuters.com/b", "s"), False, 0.9)])))
        self.engine.close(m)
        self.engine.resolve(m, outcome=True)
        lb = self.engine.leaderboard
        self.assertGreater(lb.profile("good").reputation, lb.profile("bad").reputation)
        self.assertIs(m.status, MarketStatus.RESOLVED)

    def test_gap_analysis_triggers_on_divergence(self):
        q = make_question()
        m = open_market(self.engine, self.engine.create_market(
            q, OfficialMap(text="on track", claimed_probability=0.9)))
        skeptic = ResearchAgent("skeptic")
        self.engine.place_trade(m, skeptic.trade(skeptic.assess(
            [EvidenceItem(Source("t", "https://reuters.com/t", "thermal fails"), False, 0.9),
             EvidenceItem(Source("u", "https://bloomberg.com/u", "leads depart"), False, 0.8)])))
        self.assertIsNotNone(m.gap_analysis)
        self.assertGreater(m.gap_analysis.divergence, 0.30)

    def test_trading_after_close_date_rejected(self):
        m = open_market(self.engine, self.engine.create_market(make_question()))
        agent = ResearchAgent("late")
        trade = agent.trade(agent.assess([]))
        with self.assertRaises(ValueError):
            self.engine.place_trade(m, trade, at=m.question.close_at + timedelta(seconds=1))
        self.assertIs(m.status, MarketStatus.CLOSED)


if __name__ == "__main__":
    unittest.main()
