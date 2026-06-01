from __future__ import annotations
import random
from typing import TYPE_CHECKING, Optional

from .base import BaseEngine

if TYPE_CHECKING:
    from ..game import Game
    from ..move import Move


class RandomEngine(BaseEngine):
    """A baseline engine that returns a random legal move."""

    def predict_next_move(self, game: Game) -> Optional[Move]:
        legal = game.legal_moves()
        if not legal:
            return None
        return random.choice(legal)
