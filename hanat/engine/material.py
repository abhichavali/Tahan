from __future__ import annotations
from typing import TYPE_CHECKING, Optional

from .base import BaseEngine

if TYPE_CHECKING:
    from ..game import Game
    from ..move import Move

# Standard piece values
_VALUES = {
    "P": 100,
    "N": 320,
    "B": 330,
    "R": 500,
    "Q": 900,
    "K": 20000,
    "p": 100,
    "n": 320,
    "b": 330,
    "r": 500,
    "q": 900,
    "k": 20000,
}


def _evaluate_material(board) -> int:
    """Evaluate material from White's point of view."""
    score = 0
    for sq in range(64):
        piece = board.squares[sq]
        if piece is None:
            continue
        val = _VALUES.get(piece, 0)
        if piece.isupper():
            score += val
        else:
            score -= val
    return score


class MaterialEngine(BaseEngine):
    """A simple 1-ply search engine that maximizes material balance."""

    def predict_next_move(self, game: Game) -> Optional[Move]:
        legal = game.legal_moves()
        if not legal:
            return None

        best_move = legal[0]
        is_white = game.board.turn == "w"
        sign = 1 if is_white else -1
        best_score = -float("inf")

        for move in legal:
            child = game.board.copy()
            child._apply(move)

            if child.is_checkmate():
                score = 100000  # Mate is the best possible outcome
            elif child.is_stalemate() or child.is_insufficient_material():
                score = 0  # Draw
            else:
                score = _evaluate_material(child) * sign

            if score > best_score:
                best_score = score
                best_move = move

        return best_move
