"""Thin Python adapter over the C++ rules engine (``hanat._chess``).

Presents exactly the same surface as the pure-Python
:class:`hanat._pyboard.Board`, so :class:`hanat.game.Game` and everything else
work against either backend unchanged. The C extension speaks in plain
``(from, to, promo)`` tuples; this wrapper converts to and from
:class:`hanat.move.Move`.

Importing this module raises :class:`ImportError` if the compiled extension is
not present, which is how :mod:`hanat.board` decides whether to use it.
"""

from __future__ import annotations

from typing import List, Optional

from . import _chess  # raises ImportError if the extension is not built
from ._pyboard import START_FEN
from .move import Move
from .squares import square


class CppBoard:
    """A chess position backed by the native engine. API-compatible with the
    pure-Python :class:`hanat._pyboard.Board`."""

    __slots__ = ("_b",)

    def __init__(self, fen: str = START_FEN):
        self._b = _chess.Board(fen)

    @classmethod
    def _wrap(cls, native: "_chess.Board") -> "CppBoard":
        obj = cls.__new__(cls)
        obj._b = native
        return obj

    @classmethod
    def empty(cls) -> "CppBoard":
        return cls("8/8/8/8/8/8/8/8 w - - 0 1")

    def copy(self) -> "CppBoard":
        return CppBoard._wrap(self._b.copy())

    # -- state ----------------------------------------------------------- #
    @property
    def turn(self) -> str:
        return self._b.turn

    @property
    def halfmove_clock(self) -> int:
        return self._b.halfmove_clock

    @property
    def fullmove_number(self) -> int:
        return self._b.fullmove_number

    @property
    def ep_square(self) -> Optional[int]:
        return self._b.ep_square

    def fen(self) -> str:
        return self._b.fen()

    def set_fen(self, fen: str) -> None:
        self._b.set_fen(fen)

    def piece_at(self, sq: int) -> Optional[str]:
        return self._b.piece_at(sq)

    def king_square(self, color: str) -> int:
        return self._b.king_square(color)

    def is_attacked(self, sq: int, by_color: str) -> bool:
        return self._b.is_attacked(sq, by_color)

    # -- queries --------------------------------------------------------- #
    def is_check(self) -> bool:
        return self._b.is_check()

    def is_checkmate(self) -> bool:
        return self._b.is_checkmate()

    def is_stalemate(self) -> bool:
        return self._b.is_stalemate()

    def is_insufficient_material(self) -> bool:
        return self._b.is_insufficient_material()

    # -- moves ----------------------------------------------------------- #
    def legal_moves(self) -> List[Move]:
        return [Move(f, t, p or None) for (f, t, p) in self._b.legal_moves()]

    def is_legal(self, move: Move) -> bool:
        return move in self.legal_moves()

    def _apply(self, move: Move) -> None:
        self._b.apply(move.from_sq, move.to_sq, move.promotion or "")

    def push(self, move: Move) -> None:
        self._b.push(move.from_sq, move.to_sq, move.promotion or "")

    def san(self, move: Move) -> str:
        return self._b.san(move.from_sq, move.to_sq, move.promotion or "")

    def parse_san(self, text: str) -> Move:
        f, t, p = self._b.parse_san(text)
        return Move(f, t, p or None)

    def perft(self, depth: int) -> int:
        """Count legal-move-tree leaves to ``depth`` entirely in C++ (fast)."""
        return self._b.perft(depth)

    # -- display --------------------------------------------------------- #
    def __str__(self) -> str:
        lines = []
        for rank in range(7, -1, -1):
            row = [self.piece_at(square(f, rank)) or "." for f in range(8)]
            lines.append(f"{rank + 1} " + " ".join(row))
        lines.append("  a b c d e f g h")
        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"Board({self.fen()!r})"
