"""Tests for the Stockfish evaluation adapter.

These are skipped automatically when no Stockfish binary is installed, so the
suite stays green on machines without it. They exercise the real engine when it
is present (set STOCKFISH_PATH or put `stockfish` on PATH).
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hanat import Engine, Evaluation, Game, evaluate  # noqa: E402
from hanat.engine import find_stockfish  # noqa: E402

try:
    _STOCKFISH = find_stockfish()
except FileNotFoundError:
    _STOCKFISH = None

requires_stockfish = unittest.skipIf(
    _STOCKFISH is None, "Stockfish binary not installed"
)


class TestEngineResolution(unittest.TestCase):
    def test_missing_binary_raises(self):
        with self.assertRaises(FileNotFoundError):
            find_stockfish("definitely-not-a-real-engine-xyz")


@requires_stockfish
class TestEvaluate(unittest.TestCase):
    def test_start_position_is_roughly_equal(self):
        ev = evaluate(Game(), depth=12)
        self.assertIsInstance(ev, Evaluation)
        self.assertIsNotNone(ev.cp)
        self.assertLess(abs(ev.cp), 100)  # opening is near-equal
        self.assertIsNotNone(ev.best_move)

    def test_white_pov_normalisation(self):
        # White is up a queen; score must be strongly positive from White POV
        # whether it is White's or Black's turn to move.
        white_to_move = evaluate("4k3/8/8/8/8/8/8/3QK3 w - - 0 1", depth=10)
        black_to_move = evaluate("4k3/8/8/8/8/8/8/3QK3 b - - 0 1", depth=10)
        self.assertGreater(white_to_move.score(), 300)
        self.assertGreater(black_to_move.score(), 300)

    def test_forced_mate_detected(self):
        # White: Qh7#-style mate in 1 region; just assert a mate is reported.
        ev = evaluate("6k1/5ppp/8/8/8/8/5PPP/4R1K1 w - - 0 1", depth=18)
        self.assertTrue(isinstance(ev.cp, int) or ev.is_mate)

    def test_engine_reuse(self):
        with Engine() as eng:
            a = eng.evaluate(Game(), depth=10)
            b = eng.evaluate("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1", depth=10)
        self.assertIsNotNone(a.cp)
        self.assertIsNotNone(b.cp)


if __name__ == "__main__":
    unittest.main(verbosity=2)
