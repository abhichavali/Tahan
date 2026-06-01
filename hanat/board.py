"""The chess rules engine -- backend selector.

There are two interchangeable implementations of the rules engine:

* :class:`hanat._pyboard.Board` -- a pure-Python reference (always available,
  zero dependencies, also the perft oracle).
* :class:`hanat._cboard.CppBoard` -- a native C++ engine (``hanat._chess``),
  roughly two orders of magnitude faster, used when it has been compiled.

``Board`` below is bound to the C++ engine if the extension is present and falls
back to the pure-Python one otherwise, so callers never have to care which is
in use. Build the fast path with ``python3 setup.py build_ext --inplace``.

The constants and the pure-Python class are re-exported so existing imports
(``from hanat.board import Board, WHITE, BLACK, START_FEN``) keep working, and so
tests/benchmarks can reach a specific backend via :data:`PyBoard` /
:data:`CppBoard`.
"""

from __future__ import annotations

from ._pyboard import BLACK, START_FEN, WHITE, piece_color
from ._pyboard import Board as PyBoard

CppBoard = None
try:
    from ._cboard import CppBoard as _CppBoard

    CppBoard = _CppBoard
    Board = _CppBoard
    BACKEND = "cpp"
except ImportError:
    Board = PyBoard
    BACKEND = "python"

__all__ = [
    "Board",
    "PyBoard",
    "CppBoard",
    "BACKEND",
    "WHITE",
    "BLACK",
    "START_FEN",
    "piece_color",
]
