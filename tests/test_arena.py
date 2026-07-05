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

    def test_leaderboard_structure(self):
        for needle in ("standings-body", "standings-data", "HUMAN CROWD",
                       "SIMULATED SEASON", 'data-scope="All"', "Calibration"):
            self.assertIn(needle, self.html)
        for domain in arena.DOMAINS:
            escaped = domain.replace("&", "&amp;")
            self.assertIn(f'data-scope="{escaped}"', self.html)

    def test_scale_ladder_present(self):
        for n in ("N = 1<", "N = 1,000<", "N = 1,000,000<"):
            self.assertIn(n, self.html)

    def test_artifact_preview_variant(self):
        preview = arena.render_artifact_preview(arena.simulate_season(seed=7))
        self.assertFalse(preview.startswith("<!DOCTYPE"))
        self.assertIn("standings-data", preview)


if __name__ == "__main__":
    unittest.main()
