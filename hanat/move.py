"""The :class:`Move` value type."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .squares import parse_square, square_name


@dataclass(frozen=True)
class Move:
    """A single move from one square to another.

    Attributes:
        from_sq: Origin square index (0-63).
        to_sq: Destination square index (0-63).
        promotion: For a promoting pawn move, the lowercase piece type to
            promote to (``'q'``, ``'r'``, ``'b'`` or ``'n'``); otherwise ``None``.
    """

    from_sq: int
    to_sq: int
    promotion: Optional[str] = None

    def uci(self) -> str:
        """Return the move in UCI long algebraic notation, e.g. ``'e2e4'``.

        Promotions are suffixed with the piece, e.g. ``'e7e8q'``.
        """
        s = square_name(self.from_sq) + square_name(self.to_sq)
        if self.promotion:
            s += self.promotion
        return s

    @classmethod
    def from_uci(cls, uci: str) -> "Move":
        """Parse a UCI move string (e.g. ``'e2e4'`` or ``'e7e8q'``)."""
        uci = uci.strip()
        if len(uci) not in (4, 5):
            raise ValueError(f"invalid UCI move: {uci!r}")
        from_sq = parse_square(uci[0:2])
        to_sq = parse_square(uci[2:4])
        promotion = uci[4].lower() if len(uci) == 5 else None
        if promotion is not None and promotion not in "qrbn":
            raise ValueError(f"invalid promotion piece: {promotion!r}")
        return cls(from_sq, to_sq, promotion)

    def __str__(self) -> str:
        return self.uci()
