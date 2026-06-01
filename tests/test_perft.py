"""Correctness tests for the rules engine.

`perft <https://www.chessprogramming.org/Perft>`_ counts the number of leaf
nodes in the legal-move tree to a given depth. The counts below are the
universally agreed reference values; matching them exercises castling, en
passant, promotion, check evasion and pin handling all at once. If move
generation has any bug, these numbers diverge.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hanat.board import Board  # noqa: E402


def perft(board: Board, depth: int) -> int:
    if depth == 0:
        return 1
    moves = board.legal_moves()
    if depth == 1:
        return len(moves)
    total = 0
    for move in moves:
        child = board.copy()
        child._apply(move)
        total += perft(child, depth - 1)
    return total


class PerftStartPosition(unittest.TestCase):
    def setUp(self):
        self.board = Board()

    def test_depth_1(self):
        self.assertEqual(perft(self.board, 1), 20)

    def test_depth_2(self):
        self.assertEqual(perft(self.board, 2), 400)

    def test_depth_3(self):
        self.assertEqual(perft(self.board, 3), 8902)

    def test_depth_4(self):
        self.assertEqual(perft(self.board, 4), 197281)


class PerftKiwipete(unittest.TestCase):
    """A famously tricky position rich in captures, pins and castling."""

    FEN = "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"

    def test_depth_1(self):
        self.assertEqual(perft(Board(self.FEN), 1), 48)

    def test_depth_2(self):
        self.assertEqual(perft(Board(self.FEN), 2), 2039)

    def test_depth_3(self):
        self.assertEqual(perft(Board(self.FEN), 3), 97862)


class PerftEnPassantAndPromotion(unittest.TestCase):
    """Position 3 from the chessprogramming wiki (en passant heavy)."""

    FEN = "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1"

    def test_depth_1(self):
        self.assertEqual(perft(Board(self.FEN), 1), 14)

    def test_depth_2(self):
        self.assertEqual(perft(Board(self.FEN), 2), 191)

    def test_depth_3(self):
        self.assertEqual(perft(Board(self.FEN), 3), 2812)

    def test_depth_4(self):
        self.assertEqual(perft(Board(self.FEN), 4), 43238)


if __name__ == "__main__":
    unittest.main(verbosity=2)
