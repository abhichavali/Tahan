"""Hanat chess game simulator.

A dependency-free chess rules engine and a simple game API.

Quick start::

    from hanat import Game

    game = Game()
    game.push("e4")
    game.push("e5")
    print(game.board_str())
    print(game.legal_moves_san())

See :class:`hanat.game.Game` for the high-level API and
:class:`hanat.board.Board` for direct, lower-level access to the rules engine.
"""

from .board import BLACK, WHITE, Board
from .dataset import (
    count_games,
    iter_games,
    iter_pgns,
    load_games,
    load_pgns,
)
from .engine import (
    Engine,
    Evaluation,
    evaluate,
    find_stockfish,
    BaseEngine,
    RandomEngine,
    MaterialEngine,
    MCTSEngine,
)
from .game import DRAW, BLACK_WINS, WHITE_WINS, Game
from .move import Move
from .pgn import parse_pgn
from .squares import parse_square, square_name

__all__ = [
    "Game",
    "Board",
    "Move",
    "WHITE",
    "BLACK",
    "WHITE_WINS",
    "BLACK_WINS",
    "DRAW",
    "square_name",
    "parse_square",
    "Engine",
    "Evaluation",
    "evaluate",
    "find_stockfish",
    "BaseEngine",
    "RandomEngine",
    "MaterialEngine",
    "MCTSEngine",
    "parse_pgn",
    "iter_pgns",
    "iter_games",
    "load_pgns",
    "load_games",
    "count_games",
]

__version__ = "0.1.0"
