"""Stockfish evaluation via the UCI protocol.

This is the only part of Hanat that reaches outside the standard library, and it
does so at *runtime* rather than as a hard dependency: it shells out to a
Stockfish binary if one is available. The rest of the package stays pure-stdlib.

Two entry points:

* :class:`Engine` keeps a single Stockfish process alive so you can evaluate
  many positions cheaply. Prefer this when scoring lots of positions (e.g. the
  3000-eval budget in the README) -- spawning a process per call is slow.
* :func:`evaluate` is a one-shot convenience that spins a process up, scores one
  position and tears it down again.

Scores are normalised to **White's point of view**: a positive centipawn value
means White is better, regardless of whose turn it is. (Stockfish itself reports
relative to the side to move; that raw value is kept on
:attr:`Evaluation.pov_cp`.)
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import Optional, Union

from .board import WHITE, Board
from .game import Game
from .move import Move

PositionLike = Union[Board, Game, str]

_CANDIDATE_NAMES = ("stockfish", "stockfish.exe")
_SCORE_RE = re.compile(r"score (cp|mate) (-?\d+)")
_DEPTH_RE = re.compile(r"\bdepth (\d+)")


@dataclass
class Evaluation:
    """The result of a Stockfish search on one position.

    Attributes:
        cp: Centipawn score from **White's** point of view (``+`` = White is
            better). ``None`` when the position is a forced mate.
        mate: Signed distance to mate from White's point of view (``+N`` means
            White mates in ``N``, ``-N`` means Black mates in ``N``). ``None``
            when the evaluation is a normal centipawn score.
        best_move: Stockfish's preferred :class:`~hanat.move.Move`, or ``None``
            in a terminal position.
        depth: The search depth actually reached.
        pov_cp: The raw centipawn score *relative to the side to move*, exactly
            as Stockfish reported it (``None`` for a mate score). Handy if you
            want the side-to-move convention instead of White's.
    """

    cp: Optional[int]
    mate: Optional[int]
    best_move: Optional[Move]
    depth: int
    pov_cp: Optional[int]

    def score(self, mate_value: int = 1_000_000) -> int:
        """Collapse the evaluation to a single comparable integer (White POV).

        Centipawn scores are returned as-is; mates are mapped to large signed
        values so that "White mates" always outranks any centipawn advantage and
        a faster mate outranks a slower one. Useful as a training label.
        """
        if self.mate is not None:
            sign = 1 if self.mate > 0 else -1
            return sign * (mate_value - abs(self.mate))
        return self.cp if self.cp is not None else 0

    @property
    def is_mate(self) -> bool:
        """True if this evaluation is a forced mate rather than a cp score."""
        return self.mate is not None


def _as_board(position: PositionLike) -> Board:
    if isinstance(position, Board):
        return position
    if isinstance(position, Game):
        return position.board
    if isinstance(position, str):
        return Board(position)
    raise TypeError(
        f"position must be a Board, Game or FEN string, got {type(position).__name__}"
    )


def find_stockfish(path: Optional[str] = None) -> str:
    """Locate a Stockfish executable.

    Resolution order: the explicit ``path`` argument, the ``STOCKFISH_PATH``
    environment variable, then ``stockfish`` on ``PATH``. Raises
    :class:`FileNotFoundError` with install hints if none are found.
    """
    candidates = [path, os.environ.get("STOCKFISH_PATH"), *_CANDIDATE_NAMES]
    for cand in candidates:
        if not cand:
            continue
        resolved = shutil.which(cand)
        if resolved:
            return resolved
        if os.path.isfile(cand) and os.access(cand, os.X_OK):
            return cand
    raise FileNotFoundError(
        "Stockfish executable not found. Install it (e.g. `brew install stockfish` "
        "or `apt install stockfish`), or pass path=... / set STOCKFISH_PATH."
    )


class Engine:
    """A persistent Stockfish process spoken to over UCI.

    Use as a context manager so the process is always cleaned up::

        with Engine() as sf:
            ev = sf.evaluate(game, depth=15)
            print(ev.cp, ev.best_move)

    Args:
        path: Explicit path to the Stockfish binary (see :func:`find_stockfish`).
        options: UCI options to set, e.g. ``{"Threads": 4, "Hash": 256}``.
    """

    def __init__(self, path: Optional[str] = None, *, options: Optional[dict] = None):
        self.path = find_stockfish(path)
        self._proc = subprocess.Popen(
            [self.path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        self._send("uci")
        self._wait_for("uciok")
        for name, value in (options or {}).items():
            self._send(f"setoption name {name} value {value}")
        self._send("isready")
        self._wait_for("readyok")

    # -- process plumbing ------------------------------------------------ #
    def _send(self, command: str) -> None:
        assert self._proc.stdin is not None
        self._proc.stdin.write(command + "\n")
        self._proc.stdin.flush()

    def _wait_for(self, token: str) -> None:
        assert self._proc.stdout is not None
        for line in self._proc.stdout:
            if line.strip().startswith(token):
                return
        raise RuntimeError(f"Stockfish closed before sending {token!r}")

    # -- evaluation ------------------------------------------------------ #
    def evaluate(
        self,
        position: PositionLike,
        *,
        depth: Optional[int] = None,
        movetime: Optional[int] = None,
        nodes: Optional[int] = None,
    ) -> Evaluation:
        """Run Stockfish on ``position`` and return an :class:`Evaluation`.

        ``position`` may be a :class:`~hanat.board.Board`, a
        :class:`~hanat.game.Game` (its current position is used) or a FEN string.

        Provide at most one search limit; they are tried in this order and
        default to ``depth=15``:

        * ``movetime`` -- search for this many milliseconds.
        * ``nodes`` -- search this many nodes.
        * ``depth`` -- search to this ply depth.
        """
        board = _as_board(position)
        if movetime is not None:
            limit = f"movetime {movetime}"
        elif nodes is not None:
            limit = f"nodes {nodes}"
        else:
            limit = f"depth {depth if depth is not None else 15}"

        self._send(f"position fen {board.fen()}")
        self._send(f"go {limit}")

        last_cp: Optional[int] = None
        last_mate: Optional[int] = None
        best_move: Optional[Move] = None
        depth_reached = 0

        assert self._proc.stdout is not None
        for line in self._proc.stdout:
            line = line.strip()
            if line.startswith("info"):
                score = _SCORE_RE.search(line)
                if score is None:
                    continue  # e.g. "info string ..." with no score
                dm = _DEPTH_RE.search(line)
                if dm:
                    depth_reached = int(dm.group(1))
                kind, value = score.group(1), int(score.group(2))
                if kind == "cp":
                    last_cp, last_mate = value, None
                else:
                    last_mate, last_cp = value, None
            elif line.startswith("bestmove"):
                token = line.split()[1]
                if token != "(none)":
                    best_move = Move.from_uci(token)
                break

        sign = 1 if board.turn == WHITE else -1
        return Evaluation(
            cp=last_cp * sign if last_cp is not None else None,
            mate=last_mate * sign if last_mate is not None else None,
            best_move=best_move,
            depth=depth_reached,
            pov_cp=last_cp,
        )

    # -- lifecycle ------------------------------------------------------- #
    def close(self) -> None:
        """Terminate the Stockfish process."""
        if self._proc.poll() is None:
            try:
                self._send("quit")
                self._proc.wait(timeout=5)
            except (BrokenPipeError, subprocess.TimeoutExpired, ValueError):
                self._proc.kill()
                self._proc.wait()

    def __enter__(self) -> "Engine":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass


def evaluate(
    position: PositionLike,
    *,
    depth: int = 15,
    movetime: Optional[int] = None,
    nodes: Optional[int] = None,
    path: Optional[str] = None,
    options: Optional[dict] = None,
) -> Evaluation:
    """One-shot Stockfish evaluation of a single position.

    Spins up a Stockfish process, scores ``position`` and shuts it down. For
    scoring many positions, create one :class:`Engine` and reuse it instead.

    See :meth:`Engine.evaluate` for the meaning of the search-limit arguments.
    """
    with Engine(path=path, options=options) as engine:
        return engine.evaluate(position, depth=depth, movetime=movetime, nodes=nodes)
