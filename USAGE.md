# Hanat chess simulator — API guide

A dependency-free Python chess rules engine. It encodes the complete rules of
chess and exposes a small API so the rest of Hanat (the learning engine) can
generate games, query legal moves, and detect terminal positions without caring
how any of it works.

There is nothing to install — it is pure standard-library Python 3. Just import
the `hanat` package.

```python
from hanat import Game
```

### Optional: the fast C++ engine

The rules engine ships in two interchangeable forms: a pure-Python reference
(always used by default) and a native C++ port that is ~100x faster at move
generation. Building the native one is optional and changes nothing about the
API — the same `Game`/`Board` code transparently runs on whichever is present.

```bash
python3 setup.py build_ext --inplace   # compiles hanat/_chess.cpp in place
```

That needs only a C++17 compiler (no third-party Python packages). After it, the
fast path is picked up automatically. Check which backend is live:

```python
from hanat.board import BACKEND
print(BACKEND)            # 'cpp' if the extension is built, else 'python'
```

The speedup is dramatic for bulk work: loading TWIC PGNs goes from ~1 game/s
(Python) to ~390 games/s (C++).

## The 30-second tour

```python
from hanat import Game

game = Game()                  # standard starting position, white to move

game.push("e4")                # white plays (SAN accepted)
game.push("e7e5")              # black plays (UCI also accepted)
game.push("Nf3")

print(game.turn)               # 'black'
print(game.board_str())        # ASCII board
print(game.legal_moves_san())  # ['a6', 'a5', 'Nf6', 'Nc6', ...]

print(game.is_game_over())     # False
print(game.result())           # None  (game still going)
```

## Making moves

`game.push(move)` accepts three forms interchangeably:

| Form        | Example                       |
| ----------- | ----------------------------- |
| SAN string  | `"Nf3"`, `"exd5"`, `"O-O"`, `"e8=Q"` |
| UCI string  | `"g1f3"`, `"e7e8q"`           |
| `Move`      | `Move(12, 28)`                |

It raises `ValueError` if the move is illegal or the game is already over.
Convenience variants: `push_san("Nf3")` and `push_uci("g1f3")`.

```python
move = game.push("e4")         # returns the Move that was played
print(move.uci())              # 'e2e4'
```

## Asking what's legal

```python
game.legal_moves()        # list[Move]
game.legal_moves_san()    # list[str], e.g. ['e4', 'Nf3', ...]
game.legal_moves_uci()    # list[str], e.g. ['e2e4', 'g1f3', ...]
```

## Whose turn / game state

```python
game.turn                 # 'white' or 'black'
game.fen()                # current position as a FEN string
game.board_str()          # printable ASCII board
game.history              # [{'move': Move, 'san': 'e4', 'uci': 'e2e4'}, ...]
```

## Detecting the end of the game

```python
game.is_game_over()              # True for any terminal condition
game.result()                    # '1-0', '0-1', '1/2-1/2', or None

game.is_check()
game.is_checkmate()
game.is_stalemate()
game.is_insufficient_material()
game.is_fifty_move()             # 50 moves with no capture/pawn move
game.is_threefold_repetition()
```

A typical self-play / data-generation loop:

```python
from hanat import Game
import random

game = Game()
while not game.is_game_over():
    move = random.choice(game.legal_moves())   # replace with your policy
    game.push(move)

print(game.result(), "in", len(game.history), "plies")
```

## Starting from a custom position

```python
game = Game.from_fen("r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3")
```

## Loading a game from PGN

```python
game = Game.from_pgn('''
[Event "Casual"]
[White "Alice"]
[Black "Bob"]
[Result "1-0"]

1. e4 e5 2. Bc4 Nc6 3. Qh5 Nf6 4. Qxf7# 1-0
''')

game.headers["White"]     # 'Alice'
game.turn                 # 'black'  (it's the position after the last move)
game.is_checkmate()       # True
game.history              # full replayed move list
```

`from_pgn` replays the moves into a normal `Game`, so you get history,
repetition tracking and terminal detection for free. It tolerates real-world
PGN: move numbers, `{ ... }` / `; ...` comments, `( ... )` variations (skipped),
`$N` annotation glyphs, `!?` suffixes, `0-0` castling, and a `[FEN "..."]` tag
to start from a custom position. Tag pairs land in `game.headers`.

For multi-game PGN files, split first:

```python
from hanat.pgn import split_pgn_games, parse_pgn
games = [parse_pgn(chunk) for chunk in split_pgn_games(open("games.pgn").read())]
```

## Loading a dataset (TWIC and other bulk PGN files)

A TWIC issue is one big `.pgn` file with thousands of games concatenated. The
`hanat.dataset` helpers turn it into Games you can feed the rest of the API. The
extracted file lives in `data/` (e.g. `data/twic1646.pgn`).

```python
from hanat import iter_games, load_games, load_pgns, count_games

count_games("data/twic1646.pgn")          # 5302, without parsing

# Stream them one at a time (memory-light — nothing is held but the current game):
for game in iter_games("data/twic1646.pgn"):
    game.headers["White"], game.result()
    for ply in game.history:
        ...                                # ply['san'], ply['uci'], ply['move']

# Or get an array eagerly (optionally capped):
games = load_games("data/twic1646.pgn", limit=100)
pgns  = load_pgns("data/twic1646.pgn", limit=100)   # raw PGN strings
```

Each yielded item is a normal `Game`: full move history, headers, FEN at every
ply, terminal detection — ready to plug into evaluation or training.

Real datasets contain the occasional game this engine can't replay (chess
variants, malformed entries). By default such games are skipped so one bad entry
never aborts a long run; pass `skip_errors=False` to surface the first failure:

```python
for game in iter_games("data/twic1646.pgn", skip_errors=False):
    ...
```

Loading replays through *unclaimed* threefold-repetition and fifty-move
positions (real games legitimately do), so it does not reject mid-game; only
genuine checkmate/stalemate ends a push. On a 500-game sample of TWIC every game
loaded successfully.

## Docker

A single `Dockerfile` builds a training/runtime image with everything wired up:
Python, a C++ toolchain (so the native chess engine is compiled during the
build), **Stockfish** (on `PATH` and `STOCKFISH_PATH`), and **PyTorch +
PyTorch Geometric**. Python deps are installed with **[uv](https://docs.astral.sh/uv)**
into a venv at `/opt/venv`. It has two targets, selected by build args.

```bash
# CPU image (portable — runs anywhere, including Apple Silicon)
docker compose build hanat
docker compose run --rm hanat            # runs train.py (the default CMD)

# NVIDIA GPU image (build/run on a Linux host with the NVIDIA Container Toolkit)
docker compose build hanat-gpu
docker compose run --rm hanat-gpu
```

The default command is `python train.py`, a small PyTorch Geometric scaffold
that streams the PGN dataset, turns positions into graphs, and trains a GCN to
predict game outcome. Pass it flags or drop into a shell instead:

```bash
docker compose run --rm hanat python train.py --data data/twic1646.pgn --epochs 5
docker compose run --rm hanat python3        # interactive REPL
```

Or with plain `docker build`:

```bash
docker build -t hanat:cpu .
docker build -t hanat:gpu \
  --build-arg BASE_IMAGE=nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04 \
  --build-arg CUDA_TAG=cu124 .
```

The build fails fast if the fast chess backend didn't compile or the ML stack
won't import — so a green build is a working environment. `./data` and
`./checkpoints` are mounted as volumes (datasets in, training outputs out).

Notes:
- `TORCH_VERSION` (default `2.5.0`) is a build arg; bump it as needed. PyG's
  compiled extensions are installed best-effort from its wheel index and are
  optional — `torch_geometric` runs without them.
- The GPU image is amd64/CUDA; build it on the GPU host, not on the Mac.

## Stockfish evaluation

Score any position with Stockfish. This is the one feature that needs an
external binary — install Stockfish (`brew install stockfish` /
`apt install stockfish`) and either put it on `PATH` or set `STOCKFISH_PATH`.

```python
from hanat import Game, evaluate

ev = evaluate(Game(), depth=15)     # accepts a Game, a Board, or a FEN string

ev.cp           # centipawns from WHITE's POV (+ = white better), or None if mate
ev.mate         # signed mate distance from White's POV (+N = white mates), else None
ev.best_move    # Move (Stockfish's choice)
ev.depth        # search depth reached
ev.pov_cp       # raw score relative to the side to move (Stockfish's convention)
ev.score()      # one comparable int (White POV; mates dominate) — handy as a label
```

Search limits (pass at most one; defaults to `depth=15`):

```python
evaluate(fen, depth=20)        # search to depth 20
evaluate(fen, movetime=1000)   # search for 1000 ms
evaluate(fen, nodes=1_000_000) # search 1M nodes
```

`evaluate()` spawns a Stockfish process per call. To score **many** positions
(e.g. the README's 3000-eval budget), reuse one process:

```python
from hanat import Engine

with Engine(options={"Threads": 4, "Hash": 256}) as sf:
    for fen in positions:
        ev = sf.evaluate(fen, depth=12)
        ...
```

## Going lower-level

`Game` wraps `Board`, the rules engine. Reach for `Board` directly when you want
raw position handling without history/repetition bookkeeping (e.g. inside a
search tree).

```python
from hanat.board import Board

board = Board()                       # start position
for move in board.legal_moves():
    child = board.copy()
    child.push(move)                  # apply on the copy
    ...                               # evaluate child.fen(), etc.

board.is_attacked(sq, "w")            # is square attacked by white?
board.san(move)                       # SAN for a move
board.parse_san("Nf3")                # SAN -> Move
board.king_square("b")                # locate the black king
```

Squares are integers `0..63` (`a1 = 0`, `h8 = 63`). Helpers live in
`hanat.squares`: `square_name(28) == 'e4'`, `parse_square('e4') == 28`.

## Correctness

Move generation is verified with [perft](https://www.chessprogramming.org/Perft)
against the standard reference node counts (start position, "Kiwipete", and
en-passant/promotion test positions). Run the suite with:

```bash
python3 -m unittest discover tests
```
