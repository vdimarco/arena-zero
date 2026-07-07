import json
import unittest

from brier_zero.artifacts import arena


class TestSeasonSimulation(unittest.TestCase):
    def setUp(self):
        self.season = arena.simulate_season(seed=7)

    def test_deterministic(self):
        again = arena.simulate_season(seed=7)
        self.assertEqual(
            [(a.name, round(a.mean_brier, 6)) for a in self.season.agents],
            [(a.name, round(a.mean_brier, 6)) for a in again.agents],
        )

    def test_standings_sorted_by_brier(self):
        briers = [a.mean_brier for a in self.season.agents]
        self.assertEqual(briers, sorted(briers))

    def test_human_baseline_present_and_beaten(self):
        crowd = next(a for a in self.season.agents if a.is_human_baseline)
        self.assertEqual(crowd.name, arena.HUMAN_CROWD)
        # The page's thesis must hold in the shipped season: the agent field
        # (mean of non-baseline agents) beats the human crowd.
        self.assertLess(self.season.field_brier, self.season.crowd_brier)
        beat = [a for a in self.season.agents
                if not a.is_human_baseline and a.mean_brier < crowd.mean_brier]
        self.assertGreaterEqual(len(beat), 5)

    def test_domain_scoped_podiums_differ(self):
        # Credibility is domain-scoped: at least two domains crown different leaders.
        def leader(domain):
            ranked = sorted(
                (a for a in self.season.agents if domain in a.per_domain),
                key=lambda a: a.per_domain[domain][0],
            )
            return ranked[0].name
        leaders = {d: leader(d) for d in arena.DOMAINS}
        self.assertGreater(len(set(leaders.values())), 1)

    def test_examples_cover_all_scales(self):
        for scale in (1, 1_000, 1_000_000):
            self.assertTrue(self.season.examples[scale])


class TestArenaPage(unittest.TestCase):
    def setUp(self):
        self.html = arena.render(arena.simulate_season(seed=7))

    def test_self_contained(self):
        self.assertTrue(self.html.startswith("<!DOCTYPE html>"))
        for marker in ('<link rel="stylesheet"', 'src="http'):
            self.assertNotIn(marker, self.html)

    def test_ask_loop_structure(self):
        for needle in ('id="ask-form"', 'id="theater"', 'data-key="tapeout"',
                       "Restatement", "SIMULATED", "HUMAN CROWD"):
            self.assertIn(needle, self.html)

    def test_bridge_cta_links_to_map(self):
        self.assertIn('href="/map"', self.html)
        self.assertIn("hardest question", self.html)
        self.assertIn("Turn the agents on your own roadmap", self.html)

    def test_demo_payload_embedded(self):
        # Every demo question ships with agent forecasts and a consensus the
        # theater can animate — the magic moment is data, not lorem.
        for needle in ('"forecasts"', '"consensus"', '"assumptions"'):
            self.assertIn(needle, self.html)
        for q in arena._DEMO_QUESTIONS:
            self.assertIn(json.dumps(q["key"]), self.html)

    def test_crowd_row_is_last_in_standings(self):
        board = self.html.split('class="board-lite"', 1)[1].split("</table>", 1)[0]
        rows = board.split("<tr")[1:]
        self.assertIn("HUMAN CROWD", rows[-1])
        self.assertNotIn("HUMAN CROWD", "".join(rows[:-1]))

    def test_no_stray_format_specifiers(self):
        # The ask-loop JS is %-formatted at render time: doubled %% must have
        # collapsed to literal % in the output, none left behind.
        self.assertNotIn("%%", self.html)
        self.assertIn("+ '%'", self.html)

    def test_artifact_preview_variant(self):
        preview = arena.render_artifact_preview(arena.simulate_season(seed=7))
        self.assertFalse(preview.startswith("<!DOCTYPE"))
        self.assertIn('id="ask-form"', preview)

    def test_analytics_on_deployed_page_only(self):
        # Deployed page carries the PostHog funnel; the CSP-restricted artifact
        # preview must stay dependency-free.
        self.assertIn("posthog.init", self.html)
        for event in ("ask_submitted", "theater_completed", "route_question"):
            self.assertIn(event, self.html)
        # The preview references window.posthog defensively (guarded, no-ops
        # when absent) but must never LOAD it — no init, no external array.js.
        preview = arena.render_artifact_preview(arena.simulate_season(seed=7))
        self.assertNotIn("posthog.init", preview)
        self.assertNotIn("array.js", preview)


if __name__ == "__main__":
    unittest.main()
