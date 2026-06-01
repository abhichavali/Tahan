from __future__ import annotations
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..game import Game
    from ..move import Move


class BaseEngine:
    """Base interface for a chess policy/search engine."""

    def predict_next_move(self, game: Game) -> Optional[Move]:
        """Predict and return the next best move for the active side.

        Args:
            game: A Game instance.

        Returns:
            A Move object if a legal move is available, else None.
        """
        raise NotImplementedError
