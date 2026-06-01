"""Load games from PGN (Portable Game Notation).

:func:`parse_pgn` reads a single PGN game -- tag pairs plus movetext -- and
replays it into a :class:`~hanat.game.Game`, so you get full history, repetition
tracking and terminal detection for free. The parsed tag pairs are kept on
``game.headers``.

It tolerates the things real-world PGN throws at you: move numbers (``1.``,
``1...``), ``{ ... }`` and ``; ...`` comments, ``( ... )`` recursive variations
(skipped), ``$N`` numeric annotation glyphs, ``!?``-style suffixes, and a
``[FEN "..."]`` tag to start from a custom position.
"""

from __future__ import annotations

import re
from typing import List

_TAG_RE = re.compile(r'\[\s*(\w+)\s+"([^"]*)"\s*\]')
_BRACE_COMMENT_RE = re.compile(r"\{[^}]*\}")
_LINE_COMMENT_RE = re.compile(r";[^\n]*")
_NAG_RE = re.compile(r"\$\d+")
_MOVENUM_RE = re.compile(r"\d+\.(\.\.)?")
_RESULTS = {"1-0", "0-1", "1/2-1/2", "*"}


def _strip_variations(text: str) -> str:
    """Drop ``( ... )`` recursive-annotation variations, honouring nesting."""
    out: List[str] = []
    depth = 0
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif depth == 0:
            out.append(ch)
    return "".join(out)


def split_pgn_games(text: str) -> List[str]:
    """Split a multi-game PGN file into individual game strings.

    Games are delimited by a tag section starting with ``[Event ...]``. Returns
    one string per game (each still a full PGN, tags included).
    """
    chunks: List[str] = []
    current: List[str] = []
    seen_moves = False
    for line in text.splitlines():
        is_tag = line.lstrip().startswith("[")
        if is_tag and seen_moves and current:
            chunks.append("\n".join(current))
            current = []
            seen_moves = False
        if not is_tag and line.strip():
            seen_moves = True
        current.append(line)
    if current and any(l.strip() for l in current):
        chunks.append("\n".join(current))
    return chunks


def parse_pgn(pgn: str):
    """Parse one PGN game into a :class:`~hanat.game.Game`.

    Tag pairs are exposed on the returned game's ``headers`` dict. If the PGN
    carries a ``[FEN "..."]`` tag the game starts from that position. Raises
    :class:`ValueError` if a move in the movetext is illegal for the position it
    is reached in (which usually means the PGN is malformed).
    """
    from .game import Game  # local import avoids a circular dependency

    headers = dict(_TAG_RE.findall(pgn))

    movetext = _TAG_RE.sub(" ", pgn)
    movetext = _BRACE_COMMENT_RE.sub(" ", movetext)
    movetext = _LINE_COMMENT_RE.sub(" ", movetext)
    movetext = _strip_variations(movetext)
    movetext = _NAG_RE.sub(" ", movetext)
    movetext = _MOVENUM_RE.sub(" ", movetext)

    game = Game.from_fen(headers["FEN"]) if "FEN" in headers else Game()
    game.headers = headers

    for token in movetext.split():
        if token in _RESULTS:
            continue
        san = token.replace("0-0-0", "O-O-O").replace("0-0", "O-O")
        san = san.rstrip("!?").replace("e.p.", "").strip()
        if not san:
            continue
        game.push(san)

    return game
