"""Cross-check the C++ backend against the pure-Python reference.

Drives a PyBoard and a CppBoard in lockstep through many random games, asserting
that legal moves, SAN, FEN and every terminal predicate agree at every ply. If
the C++ port ever diverges from the reference engine, this catches it. Skipped
when the native extension is not built.
"""

import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hanat.board import BACKEND, CppBoard, PyBoard  # noqa: E402

requires_cpp = unittest.skipUnless(BACKEND == "cpp", "C++ backend not built")


def _move_set(board):
    return sorted((m.from_sq, m.to_sq, m.promotion) for m in board.legal_moves())


@requires_cpp
class TestParity(unittest.TestCase):
    def test_random_games_agree(self):
        rng = random.Random(1234)
        for game_i in range(40):
            py = PyBoard()
            cpp = CppBoard()
            for _ in range(120):
                py_moves = _move_set(py)
                cpp_moves = _move_set(cpp)
                self.assertEqual(py_moves, cpp_moves,
                                 f"legal moves differ at {py.fen()}")
                self.assertEqual(py.fen(), cpp.fen())
                self.assertEqual(py.is_check(), cpp.is_check())
                self.assertEqual(py.is_checkmate(), cpp.is_checkmate())
                self.assertEqual(py.is_stalemate(), cpp.is_stalemate())
                self.assertEqual(py.is_insufficient_material(),
                                 cpp.is_insufficient_material())

                legal = py.legal_moves()
                if not legal:
                    break
                # SAN must agree for every legal move in this position.
                for m in legal:
                    self.assertEqual(py.san(m), cpp.san(m),
                                     f"SAN differs for {m.uci()} at {py.fen()}")
                move = rng.choice(legal)
                # parse_san round-trips identically on both engines.
                self.assertEqual(py.parse_san(py.san(move)),
                                 cpp.parse_san(cpp.san(move)))
                py._apply(move)
                cpp._apply(move)


if __name__ == "__main__":
    unittest.main(verbosity=2)
