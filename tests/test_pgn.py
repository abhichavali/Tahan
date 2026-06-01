"""Tests for PGN loading."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hanat import Game  # noqa: E402


SCHOLARS_MATE = """[Event "Casual"]
[Site "?"]
[White "Alice"]
[Black "Bob"]
[Result "1-0"]

1. e4 e5 2. Bc4 Nc6 3. Qh5 Nf6 4. Qxf7# 1-0
"""


class TestPgn(unittest.TestCase):
    def test_headers_parsed(self):
        g = Game.from_pgn(SCHOLARS_MATE)
        self.assertEqual(g.headers["White"], "Alice")
        self.assertEqual(g.headers["Result"], "1-0")

    def test_moves_replayed(self):
        g = Game.from_pgn(SCHOLARS_MATE)
        self.assertEqual(len(g.history), 7)
        self.assertEqual(g.history[0]["san"], "e4")
        self.assertTrue(g.is_checkmate())
        self.assertEqual(g.result(), "1-0")

    def test_comments_nags_and_variations_ignored(self):
        pgn = (
            "1. e4 {best by test} e5 "
            "2. Nf3 (2. f4 exf4) Nc6 $1 "
            "3. Bb5 a6 *"
        )
        g = Game.from_pgn(pgn)
        self.assertEqual([h["san"] for h in g.history],
                         ["e4", "e5", "Nf3", "Nc6", "Bb5", "a6"])

    def test_castling_with_zeros(self):
        pgn = "1. e4 e5 2. Nf3 Nf6 3. Bc4 Bc5 4. 0-0 0-0 *"
        g = Game.from_pgn(pgn)
        self.assertEqual(g.history[6]["san"], "O-O")
        self.assertEqual(g.history[7]["san"], "O-O")

    def test_custom_fen_setup(self):
        pgn = (
            '[SetUp "1"]\n'
            '[FEN "8/P7/8/8/8/8/8/k6K w - - 0 1"]\n\n'
            "1. a8=Q+ *"
        )
        g = Game.from_pgn(pgn)
        self.assertEqual(g.board.piece_at(56), "Q")

    def test_illegal_move_raises(self):
        with self.assertRaises(ValueError):
            Game.from_pgn("1. e4 e5 2. Qh6 *")  # queen can't teleport


if __name__ == "__main__":
    unittest.main(verbosity=2)
