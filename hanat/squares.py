"""Square coordinate helpers.

Squares are integers 0..63. Index 0 is a1, 7 is h1, 56 is a8, 63 is h8.
The mapping is ``index = rank * 8 + file`` where ``file`` 0 is the a-file and
``rank`` 0 is white's first rank (rank "1").
"""

FILE_NAMES = "abcdefgh"
RANK_NAMES = "12345678"


def square(file: int, rank: int) -> int:
    """Return the square index for a ``file`` (0-7) and ``rank`` (0-7)."""
    return rank * 8 + file


def file_of(sq: int) -> int:
    """File index (0-7) of a square."""
    return sq & 7


def rank_of(sq: int) -> int:
    """Rank index (0-7) of a square."""
    return sq >> 3


def square_name(sq: int) -> str:
    """Algebraic name of a square, e.g. ``square_name(28) == 'e4'``."""
    return FILE_NAMES[file_of(sq)] + RANK_NAMES[rank_of(sq)]


def parse_square(name: str) -> int:
    """Parse an algebraic square name (e.g. ``'e4'``) into an index."""
    name = name.strip().lower()
    if len(name) != 2 or name[0] not in FILE_NAMES or name[1] not in RANK_NAMES:
        raise ValueError(f"invalid square name: {name!r}")
    return square(FILE_NAMES.index(name[0]), RANK_NAMES.index(name[1]))


def on_board(file: int, rank: int) -> bool:
    """True if ``(file, rank)`` is within the 8x8 board."""
    return 0 <= file < 8 and 0 <= rank < 8
