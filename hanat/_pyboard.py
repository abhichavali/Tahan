"""The chess rules engine.

:class:`Board` holds a single position and knows everything about the rules of
chess: legal move generation (including castling, en passant and promotion),
check / checkmate / stalemate detection, FEN parsing and serialisation, and
conversion to/from SAN (standard algebraic notation).

Most users should prefer the higher level :class:`hanat.game.Game` wrapper,
which adds turn tracking, move history and draw-by-repetition handling.
"""

from __future__ import annotations

from typing import List, Optional

from .move import Move
from .squares import file_of, on_board, parse_square, rank_of, square, square_name

WHITE = "w"
BLACK = "b"

# Direction vectors as (file_delta, rank_delta).
_KNIGHT = [(1, 2), (2, 1), (2, -1), (1, -2), (-1, -2), (-2, -1), (-2, 1), (-1, 2)]
_KING = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
_BISHOP = [(1, 1), (1, -1), (-1, 1), (-1, -1)]
_ROOK = [(1, 0), (-1, 0), (0, 1), (0, -1)]
_QUEEN = _BISHOP + _ROOK

START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


def piece_color(piece: str) -> str:
    """Return :data:`WHITE` or :data:`BLACK` for a piece character."""
    return WHITE if piece.isupper() else BLACK


def _opposite(color: str) -> str:
    return BLACK if color == WHITE else WHITE


class Board:
    """A mutable chess position.

    The board is an array of 64 squares (see :mod:`hanat.squares`). Each square
    holds either ``None`` or a single-character piece: uppercase for white
    (``PNBRQK``) and lowercase for black (``pnbrqk``).
    """

    __slots__ = (
        "squares",
        "turn",
        "castling",
        "ep_square",
        "halfmove_clock",
        "fullmove_number",
    )

    def __init__(self, fen: str = START_FEN):
        self.squares: List[Optional[str]] = [None] * 64
        self.turn: str = WHITE
        self.castling: set = set()
        self.ep_square: Optional[int] = None
        self.halfmove_clock: int = 0
        self.fullmove_number: int = 1
        self.set_fen(fen)

    # ------------------------------------------------------------------ #
    # Construction / copying
    # ------------------------------------------------------------------ #
    @classmethod
    def empty(cls) -> "Board":
        """Return a board with no pieces and white to move."""
        b = cls.__new__(cls)
        b.squares = [None] * 64
        b.turn = WHITE
        b.castling = set()
        b.ep_square = None
        b.halfmove_clock = 0
        b.fullmove_number = 1
        return b

    def copy(self) -> "Board":
        """Return an independent copy of this board."""
        b = Board.__new__(Board)
        b.squares = self.squares[:]
        b.turn = self.turn
        b.castling = set(self.castling)
        b.ep_square = self.ep_square
        b.halfmove_clock = self.halfmove_clock
        b.fullmove_number = self.fullmove_number
        return b

    # ------------------------------------------------------------------ #
    # FEN
    # ------------------------------------------------------------------ #
    def set_fen(self, fen: str) -> None:
        """Load a position from a FEN string."""
        parts = fen.split()
        if len(parts) < 4:
            raise ValueError(f"invalid FEN: {fen!r}")
        placement = parts[0]
        self.squares = [None] * 64
        rank = 7
        file = 0
        for ch in placement:
            if ch == "/":
                rank -= 1
                file = 0
            elif ch.isdigit():
                file += int(ch)
            else:
                if ch.lower() not in "pnbrqk":
                    raise ValueError(f"invalid piece in FEN: {ch!r}")
                self.squares[square(file, rank)] = ch
                file += 1

        self.turn = WHITE if parts[1] == "w" else BLACK
        self.castling = set(c for c in parts[2] if c in "KQkq")
        self.ep_square = None if parts[3] == "-" else parse_square(parts[3])
        self.halfmove_clock = int(parts[4]) if len(parts) > 4 else 0
        self.fullmove_number = int(parts[5]) if len(parts) > 5 else 1

    def fen(self) -> str:
        """Serialise the current position as a FEN string."""
        rows = []
        for rank in range(7, -1, -1):
            row = ""
            empty = 0
            for file in range(8):
                piece = self.squares[square(file, rank)]
                if piece is None:
                    empty += 1
                else:
                    if empty:
                        row += str(empty)
                        empty = 0
                    row += piece
            if empty:
                row += str(empty)
            rows.append(row)
        placement = "/".join(rows)
        turn = "w" if self.turn == WHITE else "b"
        castling = "".join(c for c in "KQkq" if c in self.castling) or "-"
        ep = square_name(self.ep_square) if self.ep_square is not None else "-"
        return f"{placement} {turn} {castling} {ep} {self.halfmove_clock} {self.fullmove_number}"

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #
    def piece_at(self, sq: int) -> Optional[str]:
        """Return the piece character at ``sq`` or ``None``."""
        return self.squares[sq]

    def king_square(self, color: str) -> int:
        """Return the square of ``color``'s king (-1 if absent)."""
        king = "K" if color == WHITE else "k"
        for sq in range(64):
            if self.squares[sq] == king:
                return sq
        return -1

    def is_attacked(self, sq: int, by_color: str) -> bool:
        """True if ``sq`` is attacked by any piece of ``by_color``."""
        f, r = file_of(sq), rank_of(sq)
        sq_pieces = self.squares

        # Pawn attacks. A white pawn attacks diagonally "up" the board, so a
        # square is attacked by a white pawn sitting one rank below it.
        if by_color == WHITE:
            for df in (-1, 1):
                nf, nr = f + df, r - 1
                if on_board(nf, nr) and sq_pieces[square(nf, nr)] == "P":
                    return True
        else:
            for df in (-1, 1):
                nf, nr = f + df, r + 1
                if on_board(nf, nr) and sq_pieces[square(nf, nr)] == "p":
                    return True

        # Knight attacks.
        knight = "N" if by_color == WHITE else "n"
        for df, dr in _KNIGHT:
            nf, nr = f + df, r + dr
            if on_board(nf, nr) and sq_pieces[square(nf, nr)] == knight:
                return True

        # King attacks.
        king = "K" if by_color == WHITE else "k"
        for df, dr in _KING:
            nf, nr = f + df, r + dr
            if on_board(nf, nr) and sq_pieces[square(nf, nr)] == king:
                return True

        # Sliding attacks: bishops/queens on diagonals, rooks/queens on lines.
        bishop = "B" if by_color == WHITE else "b"
        rook = "R" if by_color == WHITE else "r"
        queen = "Q" if by_color == WHITE else "q"

        for df, dr in _BISHOP:
            nf, nr = f + df, r + dr
            while on_board(nf, nr):
                piece = sq_pieces[square(nf, nr)]
                if piece is not None:
                    if piece == bishop or piece == queen:
                        return True
                    break
                nf += df
                nr += dr

        for df, dr in _ROOK:
            nf, nr = f + df, r + dr
            while on_board(nf, nr):
                piece = sq_pieces[square(nf, nr)]
                if piece is not None:
                    if piece == rook or piece == queen:
                        return True
                    break
                nf += df
                nr += dr

        return False

    def is_check(self) -> bool:
        """True if the side to move is in check."""
        return self.is_attacked(self.king_square(self.turn), _opposite(self.turn))

    # ------------------------------------------------------------------ #
    # Pseudo-legal move generation
    # ------------------------------------------------------------------ #
    def _pseudo_legal_moves(self) -> List[Move]:
        moves: List[Move] = []
        color = self.turn
        for sq in range(64):
            piece = self.squares[sq]
            if piece is None or piece_color(piece) != color:
                continue
            kind = piece.lower()
            if kind == "p":
                self._gen_pawn(sq, color, moves)
            elif kind == "n":
                self._gen_step(sq, color, _KNIGHT, moves)
            elif kind == "k":
                self._gen_step(sq, color, _KING, moves)
                self._gen_castling(sq, color, moves)
            elif kind == "b":
                self._gen_slide(sq, color, _BISHOP, moves)
            elif kind == "r":
                self._gen_slide(sq, color, _ROOK, moves)
            elif kind == "q":
                self._gen_slide(sq, color, _QUEEN, moves)
        return moves

    def _gen_step(self, sq, color, directions, moves) -> None:
        f, r = file_of(sq), rank_of(sq)
        for df, dr in directions:
            nf, nr = f + df, r + dr
            if not on_board(nf, nr):
                continue
            target = square(nf, nr)
            occupant = self.squares[target]
            if occupant is None or piece_color(occupant) != color:
                moves.append(Move(sq, target))

    def _gen_slide(self, sq, color, directions, moves) -> None:
        f, r = file_of(sq), rank_of(sq)
        for df, dr in directions:
            nf, nr = f + df, r + dr
            while on_board(nf, nr):
                target = square(nf, nr)
                occupant = self.squares[target]
                if occupant is None:
                    moves.append(Move(sq, target))
                else:
                    if piece_color(occupant) != color:
                        moves.append(Move(sq, target))
                    break
                nf += df
                nr += dr

    def _gen_pawn(self, sq, color, moves) -> None:
        f, r = file_of(sq), rank_of(sq)
        forward = 1 if color == WHITE else -1
        start_rank = 1 if color == WHITE else 6
        promo_rank = 7 if color == WHITE else 0

        # Single push.
        one = square(f, r + forward)
        if self.squares[one] is None:
            self._add_pawn_move(sq, one, r + forward, promo_rank, moves)
            # Double push.
            if r == start_rank:
                two = square(f, r + 2 * forward)
                if self.squares[two] is None:
                    moves.append(Move(sq, two))

        # Captures (including en passant).
        for df in (-1, 1):
            nf, nr = f + df, r + forward
            if not on_board(nf, nr):
                continue
            target = square(nf, nr)
            occupant = self.squares[target]
            if occupant is not None and piece_color(occupant) != color:
                self._add_pawn_move(sq, target, nr, promo_rank, moves)
            elif target == self.ep_square:
                moves.append(Move(sq, target))

    @staticmethod
    def _add_pawn_move(from_sq, to_sq, to_rank, promo_rank, moves) -> None:
        if to_rank == promo_rank:
            for promo in ("q", "r", "b", "n"):
                moves.append(Move(from_sq, to_sq, promo))
        else:
            moves.append(Move(from_sq, to_sq))

    def _gen_castling(self, sq, color, moves) -> None:
        if self.is_attacked(sq, _opposite(color)):
            return  # cannot castle out of check
        enemy = _opposite(color)
        if color == WHITE:
            if "K" in self.castling and self.squares[5] is None and self.squares[6] is None:
                if not self.is_attacked(5, enemy) and not self.is_attacked(6, enemy):
                    if self.squares[7] == "R":
                        moves.append(Move(4, 6))
            if (
                "Q" in self.castling
                and self.squares[3] is None
                and self.squares[2] is None
                and self.squares[1] is None
            ):
                if not self.is_attacked(3, enemy) and not self.is_attacked(2, enemy):
                    if self.squares[0] == "R":
                        moves.append(Move(4, 2))
        else:
            if "k" in self.castling and self.squares[61] is None and self.squares[62] is None:
                if not self.is_attacked(61, enemy) and not self.is_attacked(62, enemy):
                    if self.squares[63] == "r":
                        moves.append(Move(60, 62))
            if (
                "q" in self.castling
                and self.squares[59] is None
                and self.squares[58] is None
                and self.squares[57] is None
            ):
                if not self.is_attacked(59, enemy) and not self.is_attacked(58, enemy):
                    if self.squares[56] == "r":
                        moves.append(Move(60, 58))

    # ------------------------------------------------------------------ #
    # Legal move generation
    # ------------------------------------------------------------------ #
    def legal_moves(self) -> List[Move]:
        """Return every legal move for the side to move."""
        color = self.turn
        enemy = _opposite(color)
        legal = []
        for move in self._pseudo_legal_moves():
            trial = self.copy()
            trial._apply(move)
            if not trial.is_attacked(trial.king_square(color), enemy):
                legal.append(move)
        return legal

    def is_legal(self, move: Move) -> bool:
        """True if ``move`` is legal in the current position."""
        return move in self.legal_moves()

    # ------------------------------------------------------------------ #
    # Making moves
    # ------------------------------------------------------------------ #
    def _apply(self, move: Move) -> None:
        """Apply a move in place. Assumes the move is pseudo-legal."""
        piece = self.squares[move.from_sq]
        color = piece_color(piece)
        kind = piece.lower()
        captured = self.squares[move.to_sq]
        prev_ep = self.ep_square

        self.squares[move.to_sq] = piece
        self.squares[move.from_sq] = None

        is_capture = captured is not None

        # En passant capture: remove the pawn that was passed.
        if kind == "p" and move.to_sq == prev_ep:
            cap_sq = move.to_sq - 8 if color == WHITE else move.to_sq + 8
            self.squares[cap_sq] = None
            is_capture = True

        # Promotion.
        if move.promotion is not None:
            promoted = move.promotion.upper() if color == WHITE else move.promotion
            self.squares[move.to_sq] = promoted

        # Castling: relocate the rook.
        if kind == "k" and abs(file_of(move.to_sq) - file_of(move.from_sq)) == 2:
            if move.to_sq == 6:      # white king side
                self.squares[5], self.squares[7] = self.squares[7], None
            elif move.to_sq == 2:    # white queen side
                self.squares[3], self.squares[0] = self.squares[0], None
            elif move.to_sq == 62:   # black king side
                self.squares[61], self.squares[63] = self.squares[63], None
            elif move.to_sq == 58:   # black queen side
                self.squares[59], self.squares[56] = self.squares[56], None

        # Update castling rights.
        if kind == "k":
            if color == WHITE:
                self.castling.discard("K")
                self.castling.discard("Q")
            else:
                self.castling.discard("k")
                self.castling.discard("q")
        self._touch_rook_square(move.from_sq)
        self._touch_rook_square(move.to_sq)  # rook captured on its home square

        # En passant target for the next move.
        if kind == "p" and abs(move.to_sq - move.from_sq) == 16:
            self.ep_square = (move.from_sq + move.to_sq) // 2
        else:
            self.ep_square = None

        # Half-move clock (for the 50-move rule).
        if kind == "p" or is_capture:
            self.halfmove_clock = 0
        else:
            self.halfmove_clock += 1

        if color == BLACK:
            self.fullmove_number += 1
        self.turn = _opposite(color)

    def _touch_rook_square(self, sq: int) -> None:
        if sq == 0:
            self.castling.discard("Q")
        elif sq == 7:
            self.castling.discard("K")
        elif sq == 56:
            self.castling.discard("q")
        elif sq == 63:
            self.castling.discard("k")

    def push(self, move: Move) -> None:
        """Apply a legal ``move`` to the board.

        Raises :class:`ValueError` if the move is not legal.
        """
        if move not in self.legal_moves():
            raise ValueError(f"illegal move: {move.uci()} in {self.fen()}")
        self._apply(move)

    # ------------------------------------------------------------------ #
    # Game-over detection
    # ------------------------------------------------------------------ #
    def is_checkmate(self) -> bool:
        """True if the side to move is checkmated."""
        return self.is_check() and not self.legal_moves()

    def is_stalemate(self) -> bool:
        """True if the side to move has no legal move and is not in check."""
        return not self.is_check() and not self.legal_moves()

    def is_insufficient_material(self) -> bool:
        """True for dead positions that cannot be won by either side."""
        bishops_light = bishops_dark = knights = 0
        for sq in range(64):
            piece = self.squares[sq]
            if piece is None:
                continue
            kind = piece.lower()
            if kind in ("p", "r", "q"):
                return False
            if kind == "n":
                knights += 1
            elif kind == "b":
                if (file_of(sq) + rank_of(sq)) % 2 == 0:
                    bishops_dark += 1
                else:
                    bishops_light += 1
        minors = knights + bishops_light + bishops_dark
        if minors <= 1:
            return True  # K vs K, K+minor vs K
        if knights == 0 and (bishops_light == 0 or bishops_dark == 0):
            return True  # any number of same-coloured bishops only
        return False

    # ------------------------------------------------------------------ #
    # SAN (standard algebraic notation)
    # ------------------------------------------------------------------ #
    def san(self, move: Move) -> str:
        """Return the SAN string for a legal ``move`` in this position."""
        piece = self.squares[move.from_sq]
        kind = piece.lower()

        # Castling.
        if kind == "k" and abs(file_of(move.to_sq) - file_of(move.from_sq)) == 2:
            text = "O-O" if file_of(move.to_sq) == 6 else "O-O-O"
            return text + self._check_suffix(move)

        is_capture = self.squares[move.to_sq] is not None or (
            kind == "p" and move.to_sq == self.ep_square
        )

        if kind == "p":
            text = ""
            if is_capture:
                text += square_name(move.from_sq)[0] + "x"
            text += square_name(move.to_sq)
            if move.promotion:
                text += "=" + move.promotion.upper()
        else:
            text = piece.upper()
            text += self._disambiguation(move)
            if is_capture:
                text += "x"
            text += square_name(move.to_sq)

        return text + self._check_suffix(move)

    def _disambiguation(self, move: Move) -> str:
        piece = self.squares[move.from_sq]
        kind = piece.lower()
        rivals = []
        for other in self.legal_moves():
            if other.to_sq != move.to_sq or other.from_sq == move.from_sq:
                continue
            op = self.squares[other.from_sq]
            if op is not None and op.lower() == kind and op == piece:
                rivals.append(other.from_sq)
        if not rivals:
            return ""
        same_file = any(file_of(s) == file_of(move.from_sq) for s in rivals)
        same_rank = any(rank_of(s) == rank_of(move.from_sq) for s in rivals)
        name = square_name(move.from_sq)
        if not same_file:
            return name[0]
        if not same_rank:
            return name[1]
        return name

    def _check_suffix(self, move: Move) -> str:
        trial = self.copy()
        trial._apply(move)
        if trial.is_check():
            return "#" if not trial.legal_moves() else "+"
        return ""

    def parse_san(self, text: str) -> Move:
        """Parse a SAN string into a legal :class:`Move` for this position."""
        cleaned = text.strip().rstrip("+#").replace("!", "").replace("?", "")
        for move in self.legal_moves():
            san = self.san(move).rstrip("+#")
            if san == cleaned:
                return move
        raise ValueError(f"illegal or ambiguous SAN: {text!r} in {self.fen()}")

    # ------------------------------------------------------------------ #
    # Display
    # ------------------------------------------------------------------ #
    def __str__(self) -> str:
        lines = []
        for rank in range(7, -1, -1):
            row = [self.squares[square(f, rank)] or "." for f in range(8)]
            lines.append(f"{rank + 1} " + " ".join(row))
        lines.append("  a b c d e f g h")
        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"Board({self.fen()!r})"
