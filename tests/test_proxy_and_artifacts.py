import unittest
from datetime import timedelta
from pathlib import Path
import tempfile

from brier_zero import (
    EmployeeDirectory,
    EmployeeProxyAgent,
    EvidenceItem,
    MarketEngine,
    OfficialMap,
    Question,
    ResearchAgent,
    Source,
    Whisper,
)
from brier_zero.artifacts import gap, landing, market as market_art, slider, source as source_art
from brier_zero.models import utcnow
from brier_zero.proxy import VerificationError


def build_market():
    engine = MarketEngine()
    q = Question(
        text="Will the program ship by 2028?",
        resolution_criteria="Resolves YES if a production unit ships before close.",
        close_at=utcnow() + timedelta(days=100),
        context="We assume validation passed.",
    )
    m = engine.create_market(q, OfficialMap(text="on track", claimed_probability=0.9))
    engine.run_restatement(m)
    engine.review_restatement(m, {})
    agent = ResearchAgent("skeptic", skill_ids=["skill_x"])
    assessment = agent.assess([
        EvidenceItem(Source("Report <A&B>", "https://reuters.com/r",
                            'quote with "quotes" & <tags>',
                            published_at=utcnow() - timedelta(days=5)),
                     supports_yes=False, strength=0.8),
    ])
    engine.place_trade(m, agent.trade(assessment))
    return engine, m, agent, assessment


class TestProxy(unittest.TestCase):
    def setUp(self):
        self.directory = EmployeeDirectory(tokens={"tok_ok": "emp_1", "tok_two": "emp_2"})
        self.proxy = EmployeeProxyAgent(self.directory, secret=b"s3cret")

    def test_unverified_token_rejected(self):
        with self.assertRaises(VerificationError):
            self.proxy.draft(Whisper(employee_token="bad", text="x", market_id="mkt_1"))

    def test_pseudonym_stable_within_market_unlinkable_across(self):
        p1 = self.proxy.pseudonym("mkt_1", "emp_1")
        p1_again = self.proxy.pseudonym("mkt_1", "emp_1")
        p_other_market = self.proxy.pseudonym("mkt_2", "emp_1")
        p_other_emp = self.proxy.pseudonym("mkt_1", "emp_2")
        self.assertEqual(p1, p1_again)
        self.assertNotEqual(p1, p_other_market)
        self.assertNotEqual(p1, p_other_emp)

    def test_negative_whisper_yields_negative_delta_and_scrubs_names(self):
        draft = self.proxy.draft(Whisper(
            employee_token="tok_ok",
            text="Project Titan failed thermal validation twice; we are very behind.",
            market_id="mkt_1",
        ))
        self.assertLess(draft.signal.delta, 0)
        self.assertNotIn("Titan", draft.signal.public_rationale)
        self.assertTrue(any("Titan" in t for t in draft.scrubbed_terms))

    def test_explicit_delta_wins(self):
        draft = self.proxy.draft(Whisper(
            employee_token="tok_ok", text="shift it -20% based on what I saw", market_id="m"))
        self.assertAlmostEqual(draft.signal.delta, -0.20)

    def test_signal_nudge_is_bounded(self):
        engine, m, _, _ = build_market()
        before = engine.price(m)
        draft = self.proxy.draft(Whisper(
            employee_token="tok_ok",
            text="definitely failed broken delayed behind worse -99%",
            market_id=m.id,
        ))
        after = engine.apply_signal(m, draft.signal)
        self.assertLessEqual(abs(after - before), 0.15 + 1e-9)


class TestArtifacts(unittest.TestCase):
    def setUp(self):
        self.engine, self.market, self.agent, self.assessment = build_market()

    def assert_selfcontained(self, html):
        self.assertTrue(html.startswith("<!DOCTYPE html>"))
        for marker in ("http-equiv=\"refresh\"", "<link rel=\"stylesheet\"", "src=\"http"):
            self.assertNotIn(marker, html)

    def test_market_artifact_has_four_layers_and_escapes(self):
        html = market_art.render_human(self.market)
        self.assert_selfcontained(html)
        for n in (1, 2, 3, 4):
            self.assertIn(f'data-layer="{n}"', html)
        self.assertIn("&lt;A&amp;B&gt;", html)   # source title escaped
        self.assertNotIn("<A&B>", html)

    def test_agent_markdown_covers_contract(self):
        md = market_art.render_agent(self.market)
        for heading in ("## Intent", "## Constraints", "## Assumptions surfaced",
                        "## Known unknowns", "## Gap alerts"):
            self.assertIn(heading, md)

    def test_source_artifact_hover_and_timeline(self):
        html = source_art.render(self.market, self.assessment, self.agent.agent_id)
        self.assert_selfcontained(html)
        self.assertIn('class="claim"', html)   # hover-to-verify
        self.assertIn("<svg", html)            # timeline
        self.assertIn("side", html)

    def test_slider_artifact_is_interactive(self):
        from brier_zero.proxy import EmployeeDirectory as ED, EmployeeProxyAgent as EPA
        proxy = EPA(ED(tokens={"t": "e"}), secret=b"k")
        draft = proxy.draft(Whisper(employee_token="t", text="behind -10%", market_id=self.market.id))
        html = slider.render(self.market, draft)
        self.assert_selfcontained(html)
        self.assertIn('type="range"', html)
        self.assertIn(draft.signal.pseudonym, html)

    def test_gap_report_renders(self):
        html = gap.render(self.market)
        self.assert_selfcontained(html)
        self.assertIn("Map Fidelity", html)

    def test_landing_analytics_deployed_only(self):
        demo = market_art.render_human(self.market)
        deployed = landing.render_variant(landing.VARIANTS[0], demo)
        self.assertIn("posthog.init", deployed)
        self.assertIn("waitlist_signup", deployed)
        preview = landing.render_artifact_preview(demo)
        self.assertNotIn("posthog.init", preview)
        self.assertNotIn("array.js", preview)

    def test_landing_variants_and_router(self):
        demo = market_art.render_human(self.market)
        pages = landing.render_all(demo)
        self.assertEqual(set(pages), {"index.html", "landing-a.html", "landing-b.html",
                                      "landing-c.html", "landing-d.html"})
        for key in ("a", "b", "c", "d"):
            page = pages[f"landing-{key}.html"]
            self.assert_selfcontained(page)
            self.assertIn(f'data-variant="{key}"', page)
            self.assertIn("iframe srcdoc=", page)   # embedded live demo
            self.assertIn("waitlist", page)
        self.assertIn("bz_variant", pages["index.html"])


class TestDemoPipeline(unittest.TestCase):
    def test_demo_builds_all_artifacts(self):
        from brier_zero.demo import build_demo
        with tempfile.TemporaryDirectory() as td:
            written = build_demo(Path(td))
            expected = {"market-human.html", "market-agent.md", "source-artifact.html",
                        "signal-slider.html", "gap-report.html", "skill-audit.html",
                        "index.html", "landing-a.html", "landing-b.html",
                        "landing-c.html", "landing-d.html", "arena.html"}
            self.assertEqual(set(written), expected)
            for p in written.values():
                self.assertGreater(p.stat().st_size, 500)


if __name__ == "__main__":
    unittest.main()
