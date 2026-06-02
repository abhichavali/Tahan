"""High-level game API.

:class:`Game` is the simple, friendly entry point most callers want. It wraps a
:class:`hanat.board.Board`, tracks whose turn it is, records move history, and
handles draw conditions (threefold repetition, the fifty-move rule and
insufficient material).
"""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from .engine.base import BaseEngine

from .board import BLACK, WHITE, Board, START_FEN
from .move import Move

WHITE_WINS = "1-0"
BLACK_WINS = "0-1"
DRAW = "1/2-1/2"


class Game:
    """A complete chess game.

    Example:
        >>> game = Game()
        >>> game.turn
        'white'
        >>> game.push("e4")          # white moves (SAN or UCI both accepted)
        >>> game.push("e5")          # black moves
        >>> game.is_game_over()
        False
    """

    def __init__(self, fen: str = START_FEN, engine: Optional[BaseEngine] = None):
        self.board = Board(fen)
        self.history: List[dict] = []
        self.headers: dict = {}
        self._positions: Counter = Counter()
        self._record_position()
        self.engine = engine

    @classmethod
    def from_fen(cls, fen: str) -> "Game":
        """Create a game from an arbitrary starting position."""
        return cls(fen)

    @classmethod
    def from_pgn(cls, pgn: str) -> "Game":
        """Create a game by replaying a PGN string.

        Tag pairs are exposed on the returned game's ``headers`` dict. See
        :func:`hanat.pgn.parse_pgn` for the accepted syntax.
        """
        from .pgn import parse_pgn
        return parse_pgn(pgn)

    # ------------------------------------------------------------------ #
    # Turn / state
    # ------------------------------------------------------------------ #
    @property
    def turn(self) -> str:
        """Whose turn it is: ``'white'`` or ``'black'``."""
        return "white" if self.board.turn == WHITE else "black"

    def fen(self) -> str:
        """Current position as a FEN string."""
        return self.board.fen()

    def board_str(self) -> str:
        """An ASCII rendering of the board (rank 8 at the top)."""
        return str(self.board)

    # ------------------------------------------------------------------ #
    # Moves
    # ------------------------------------------------------------------ #
    def legal_moves(self) -> List[Move]:
        """List of legal :class:`Move` objects for the side to move."""
        return self.board.legal_moves()

    def legal_moves_san(self) -> List[str]:
        """Legal moves rendered as SAN strings, e.g. ``['e4', 'Nf3', ...]``."""
        return [self.board.san(m) for m in self.board.legal_moves()]

    def legal_moves_uci(self) -> List[str]:
        """Legal moves rendered as UCI strings, e.g. ``['e2e4', 'g1f3', ...]``."""
        return [m.uci() for m in self.board.legal_moves()]

    def push(self, move) -> Move:
        """Make a move.

        ``move`` may be a :class:`Move`, a SAN string (``"Nf3"``, ``"e8=Q"``,
        ``"O-O"``) or a UCI string (``"g1f3"``, ``"e7e8q"``). Returns the
        :class:`Move` that was played.

        Raises :class:`ValueError` if the move is illegal or the game has
        genuinely ended (checkmate or stalemate). Claimable draws -- threefold
        repetition and the fifty-move rule -- do *not* block further moves,
        since real games legitimately play on through unclaimed repetitions;
        use :meth:`is_game_over` / :meth:`result` to detect those.
        """
        if self.board.is_checkmate() or self.board.is_stalemate():
            raise ValueError("the game is already over")
        resolved = self._resolve(move)
        san = self.board.san(resolved)
        self.board.push(resolved)
        self.history.append({"move": resolved, "san": san, "uci": resolved.uci()})
        self._record_position()
        return resolved

    def push_uci(self, uci: str) -> Move:
        """Convenience wrapper for :meth:`push` with a UCI string."""
        return self.push(Move.from_uci(uci))

    def push_san(self, san: str) -> Move:
        """Convenience wrapper for :meth:`push` with a SAN string."""
        return self.push(self.board.parse_san(san))

    def _resolve(self, move) -> Move:
        if isinstance(move, Move):
            return move
        if not isinstance(move, str):
            raise TypeError(f"move must be a Move or str, got {type(move).__name__}")
        text = move.strip()
        # Try UCI first (it has a rigid shape), then fall back to SAN.
        if len(text) in (4, 5) and text[0:2].lower()[0] in "abcdefgh":
            try:
                candidate = Move.from_uci(text)
                if candidate in self.board.legal_moves():
                    return candidate
            except ValueError:
                pass
        return self.board.parse_san(text)

    # ------------------------------------------------------------------ #
    # Game-over conditions
    # ------------------------------------------------------------------ #
    def is_check(self) -> bool:
        """True if the side to move is in check."""
        return self.board.is_check()

    def is_checkmate(self) -> bool:
        return self.board.is_checkmate()

    def is_stalemate(self) -> bool:
        return self.board.is_stalemate()

    def is_insufficient_material(self) -> bool:
        return self.board.is_insufficient_material()

    def is_fifty_move(self) -> bool:
        """True once 50 full moves have passed without a capture or pawn move."""
        return self.board.halfmove_clock >= 100

    def is_threefold_repetition(self) -> bool:
        """True if the current position has occurred at least three times."""
        return self._positions[self._position_key()] >= 3

    def is_game_over(self) -> bool:
        """True if the game has ended for any reason."""
        return self.result() is not None

    def result(self) -> Optional[str]:
        """Return the game result, or ``None`` if the game is ongoing.

        One of ``'1-0'`` (white wins), ``'0-1'`` (black wins) or ``'1/2-1/2'``
        (draw).
        """
        if self.board.is_checkmate():
            return BLACK_WINS if self.board.turn == WHITE else WHITE_WINS
        if (
            self.board.is_stalemate()
            or self.is_insufficient_material()
            or self.is_fifty_move()
            or self.is_threefold_repetition()
        ):
            return DRAW
        return None

    # ------------------------------------------------------------------ #
    # Repetition bookkeeping
    # ------------------------------------------------------------------ #
    def _position_key(self) -> str:
        # Repetition ignores move clocks: piece placement, side, castling, ep.
        return " ".join(self.board.fen().split()[:4])

    def _record_position(self) -> None:
        self._positions[self._position_key()] += 1

    def __str__(self) -> str:
        return self.board_str()

    def predict_next_move(self) -> Optional[Move]:
        """Predict the next best move for the active side."""
        if self.engine is None:
            raise ValueError("No engine has been set for this game.")
        return self.engine.predict_next_move(self)
