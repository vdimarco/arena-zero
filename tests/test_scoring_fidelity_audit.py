import unittest
from datetime import timedelta

from brier_zero import (
    EvidenceItem,
    MapFidelityScorer,
    MarketEngine,
    OfficialMap,
    Question,
    ResearchAgent,
    Source,
    brier_index,
    brier_score,
    calibration_curve,
    variance_band,
)
from brier_zero.models import utcnow
from brier_zero.scoring import Leaderboard


class TestScoring(unittest.TestCase):
    def test_brier_score_bounds(self):
        self.assertEqual(brier_score(1.0, True), 0.0)
        self.assertEqual(brier_score(0.0, True), 1.0)
        self.assertEqual(brier_score(0.5, True), 0.25)

    def test_brier_index_rewards_beating_consensus(self):
        # right when the crowd was wrong > right with the crowd
        contrarian = brier_index(0.8, True, consensus_at_close=0.3)
        conformist = brier_index(0.8, True, consensus_at_close=0.8)
        self.assertGreater(contrarian, conformist)
        self.assertTrue(0 <= contrarian <= 100)

    def test_leaderboard_reputation_bounds(self):
        lb = Leaderboard()
        for _ in range(50):
            lb.record("winner", 0.95, True)
            lb.record("loser", 0.95, False)
        self.assertLessEqual(lb.profile("winner").reputation, lb.max_reputation)
        self.assertGreaterEqual(lb.profile("loser").reputation, lb.min_reputation)
        rankings = lb.rankings()
        self.assertEqual(rankings[0].agent_id, "winner")

    def test_calibration_curve(self):
        pairs = [(0.9, True)] * 9 + [(0.9, False)]
        buckets = calibration_curve(pairs)
        b = buckets[9]  # 0.9..1.0
        self.assertEqual(b.forecasts, 10)
        self.assertAlmostEqual(b.hit_rate, 0.9)


class TestFidelity(unittest.TestCase):
    def _market_with_divergence(self):
        engine = MarketEngine()
        q = Question(
            text="Will milestone M ship on time?",
            resolution_criteria="Resolves YES if shipped by close.",
            close_at=utcnow() + timedelta(days=10),
            context="We assume the vendor delivers early.",
        )
        m = engine.create_market(q, OfficialMap(
            text="Roadmap says on track.",
            claimed_probability=0.9,
            as_of=utcnow() - timedelta(days=90),
        ))
        engine.run_restatement(m)
        engine.review_restatement(m, {})
        agent = ResearchAgent("skeptic")
        engine.place_trade(m, agent.trade(agent.assess([
            EvidenceItem(Source("fresh evidence", "https://reuters.com/f",
                                "vendor slipped", published_at=utcnow() - timedelta(days=1)),
                         supports_yes=False, strength=0.9),
        ])))
        return engine, m

    def test_low_fidelity_on_divergent_market(self):
        _, m = self._market_with_divergence()
        self.assertIsNotNone(m.fidelity)
        self.assertLess(m.fidelity.score, 60)
        self.assertTrue(m.fidelity.contradicted)
        self.assertTrue(m.fidelity.stale, "90-day-old map vs day-old evidence should be stale")

    def test_variance_band_widens_with_low_fidelity(self):
        lo_band = variance_band(20, 0.5)
        hi_band = variance_band(95, 0.5)
        self.assertGreater(lo_band[1] - lo_band[0], hi_band[1] - hi_band[0])

    def test_perfect_map_scores_high(self):
        scorer = MapFidelityScorer()
        engine = MarketEngine()
        q = Question(
            text="Will X happen?",
            resolution_criteria="Resolves YES if X.",
            close_at=utcnow() + timedelta(days=5),
        )
        m = engine.create_market(q)
        engine.run_restatement(m)
        engine.review_restatement(m, {})
        report = scorer.score(m, price=None)
        self.assertGreaterEqual(report.score, 60)


class TestSkillAudit(unittest.TestCase):
    def test_dead_weight_flagging_and_weights(self):
        engine = MarketEngine()
        good = ResearchAgent("good_agent", skill_ids=["skill_solid"])
        bad = ResearchAgent("bad_agent", skill_ids=["skill_dead"])
        for i in range(3):
            q = Question(
                text=f"Will event {i} happen?",
                resolution_criteria="Resolves YES if it happens.",
                close_at=utcnow() + timedelta(days=1),
            )
            m = engine.create_market(q)
            engine.run_restatement(m)
            engine.review_restatement(m, {})
            engine.place_trade(m, good.trade(good.assess(
                [EvidenceItem(Source("s", "https://reuters.com/s", "snippet"), True, 0.9)])))
            engine.place_trade(m, bad.trade(bad.assess(
                [EvidenceItem(Source("s", "https://reuters.com/s", "snippet"), False, 0.9)])))
            engine.close(m)
            report = engine.resolve(m, outcome=True)
        self.assertIn("skill_dead", report.dead_weight)
        self.assertNotIn("skill_solid", report.dead_weight)
        weights = engine.skill_audit.selection_weights()
        self.assertGreater(weights["skill_solid"], weights["skill_dead"])
        self.assertGreaterEqual(weights["skill_dead"], 0.1)


if __name__ == "__main__":
    unittest.main()
