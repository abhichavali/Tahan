"""Load PGN collections (e.g. the TWIC dataset) into the Game API.

TWIC ("The Week in Chess") ships each issue as a single ``.pgn`` file holding
thousands of games concatenated together. This module turns such a file into
something you can plug straight into :class:`hanat.game.Game`:

* :func:`iter_pgns` streams the file and yields one raw PGN string per game --
  memory-light, so it handles big files without loading them whole.
* :func:`iter_games` goes one step further and yields parsed
  :class:`~hanat.game.Game` objects, one at a time.
* :func:`load_pgns` / :func:`load_games` are the eager "give me the array"
  variants, with an optional ``limit``.

Not every PGN in the wild replays cleanly (variant games, the rare malformed
entry). By default the loaders skip games that fail to parse; pass
``skip_errors=False`` to have the first failure raise instead.
"""

from __future__ import annotations

import os
from typing import Iterator, List, Optional, Union

from .game import Game

PathLike = Union[str, os.PathLike]


def iter_pgns(path: PathLike, *, encoding: str = "utf-8-sig") -> Iterator[str]:
    """Yield each game in a PGN file as a raw PGN string.

    Reads line by line, so the whole file is never held in memory at once. A new
    game is recognised when a ``[Tag ...]`` line appears after some movetext.
    """
    with open(path, "r", encoding=encoding, errors="replace") as handle:
        current: List[str] = []
        seen_moves = False
        for line in handle:
            is_tag = line.lstrip().startswith("[")
            if is_tag and seen_moves and current:
                yield "".join(current)
                current = []
                seen_moves = False
            if line.strip() and not is_tag:
                seen_moves = True
            current.append(line)
        if current and any(l.strip() for l in current):
            yield "".join(current)


def iter_games(
    path: PathLike,
    *,
    skip_errors: bool = True,
    encoding: str = "utf-8-sig",
) -> Iterator[Game]:
    """Yield each game in a PGN file as a parsed :class:`~hanat.game.Game`.

    With ``skip_errors=True`` (the default), games that fail to parse are
    silently skipped so one bad entry never aborts a long run. Set it to
    ``False`` to surface the first :class:`ValueError`.
    """
    for pgn in iter_pgns(path, encoding=encoding):
        try:
            yield Game.from_pgn(pgn)
        except (ValueError, KeyError, IndexError):
            if not skip_errors:
                raise


def load_pgns(
    path: PathLike,
    *,
    limit: Optional[int] = None,
    encoding: str = "utf-8-sig",
) -> List[str]:
    """Return a list of raw PGN strings (optionally just the first ``limit``)."""
    out: List[str] = []
    for pgn in iter_pgns(path, encoding=encoding):
        out.append(pgn)
        if limit is not None and len(out) >= limit:
            break
    return out


def load_games(
    path: PathLike,
    *,
    limit: Optional[int] = None,
    skip_errors: bool = True,
    encoding: str = "utf-8-sig",
) -> List[Game]:
    """Return a list of parsed :class:`~hanat.game.Game` objects.

    ``limit`` caps how many *successfully parsed* games are returned. See
    :func:`iter_games` for ``skip_errors`` semantics.
    """
    out: List[Game] = []
    for game in iter_games(path, skip_errors=skip_errors, encoding=encoding):
        out.append(game)
        if limit is not None and len(out) >= limit:
            break
    return out


def count_games(path: PathLike, *, encoding: str = "utf-8-sig") -> int:
    """Count the games in a PGN file without parsing them."""
    return sum(1 for _ in iter_pgns(path, encoding=encoding))
