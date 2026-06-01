"""Tests for the bulk-PGN dataset loader.

These run against the extracted TWIC file in data/ and skip automatically if it
is not present, so the suite stays portable.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hanat import Game, count_games, iter_pgns, load_games, load_pgns  # noqa: E402

_DATA = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "twic1646.pgn"
)
requires_data = unittest.skipUnless(os.path.exists(_DATA), "TWIC data file not present")


@requires_data
class TestDataset(unittest.TestCase):
    def test_count_matches_event_tags(self):
        self.assertEqual(count_games(_DATA), 5302)

    def test_load_pgns_limit(self):
        pgns = load_pgns(_DATA, limit=3)
        self.assertEqual(len(pgns), 3)
        self.assertTrue(all("[Event" in p for p in pgns))

    def test_iter_yields_raw_then_parses(self):
        first = next(iter_pgns(_DATA))
        game = Game.from_pgn(first)
        self.assertIn("White", game.headers)
        self.assertGreater(len(game.history), 0)

    def test_load_games_are_usable(self):
        games = load_games(_DATA, limit=2)
        self.assertEqual(len(games), 2)
        for g in games:
            self.assertIsInstance(g, Game)
            self.assertIn(g.result(), ("1-0", "0-1", "1/2-1/2", None))


if __name__ == "__main__":
    unittest.main(verbosity=2)
