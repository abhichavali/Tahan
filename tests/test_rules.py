"""Behavioural tests for the high-level Game API and special rules."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hanat import Game, Move  # noqa: E402


class TestBasics(unittest.TestCase):
    def test_initial_turn_and_moves(self):
        g = Game()
        self.assertEqual(g.turn, "white")
        self.assertEqual(len(g.legal_moves()), 20)

    def test_turn_alternates(self):
        g = Game()
        g.push("e4")
        self.assertEqual(g.turn, "black")
        g.push("e5")
        self.assertEqual(g.turn, "white")

    def test_accepts_uci_and_san(self):
        g = Game()
        g.push("e2e4")          # UCI
        g.push("Nf6")           # SAN
        self.assertEqual(g.history[0]["san"], "e4")
        self.assertEqual(g.history[1]["uci"], "g8f6")

    def test_illegal_move_rejected(self):
        g = Game()
        with self.assertRaises(ValueError):
            g.push("e5")        # pawn cannot jump three from e2


class TestSpecialRules(unittest.TestCase):
    def test_castling_kingside(self):
        g = Game("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
        g.push("O-O")
        self.assertEqual(g.board.piece_at(6), "K")
        self.assertEqual(g.board.piece_at(5), "R")

    def test_en_passant(self):
        g = Game()
        for mv in ["e4", "a6", "e5", "d5"]:
            g.push(mv)
        g.push("exd6")          # en passant capture
        self.assertIsNone(g.board.piece_at(35))  # captured pawn on d5 removed
        self.assertEqual(g.board.piece_at(43), "P")  # capturing pawn on d6

    def test_promotion(self):
        g = Game("8/P7/8/8/8/8/8/k6K w - - 0 1")
        g.push("a8=Q")
        self.assertEqual(g.board.piece_at(56), "Q")

    def test_promotion_uci(self):
        g = Game("8/P7/8/8/8/8/8/k6K w - - 0 1")
        g.push("a7a8q")
        self.assertEqual(g.board.piece_at(56), "Q")


class TestGameOver(unittest.TestCase):
    def test_fools_mate(self):
        g = Game()
        for mv in ["f3", "e5", "g4", "Qh4"]:
            g.push(mv)
        self.assertTrue(g.is_checkmate())
        self.assertEqual(g.result(), "0-1")
        self.assertTrue(g.is_game_over())

    def test_stalemate(self):
        g = Game("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")
        self.assertTrue(g.is_stalemate())
        self.assertEqual(g.result(), "1/2-1/2")

    def test_insufficient_material(self):
        g = Game("8/8/8/4k3/8/8/4K3/8 w - - 0 1")
        self.assertTrue(g.is_insufficient_material())
        self.assertEqual(g.result(), "1/2-1/2")

    def test_cannot_move_after_game_over(self):
        g = Game()
        for mv in ["f3", "e5", "g4", "Qh4"]:
            g.push(mv)
        with self.assertRaises(ValueError):
            g.push("a3")


class TestFen(unittest.TestCase):
    def test_roundtrip(self):
        fen = "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3"
        self.assertEqual(Game(fen).fen(), fen)


if __name__ == "__main__":
    unittest.main(verbosity=2)
