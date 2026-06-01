#!/usr/bin/env python3
"""UCI interface for the Hanat chess engine using the Game API."""

import sys
import argparse
from hanat import Game, RandomEngine, MaterialEngine


def main():
    parser = argparse.ArgumentParser(description="Hanat UCI Engine")
    parser.add_argument(
        "--engine",
        type=str,
        default="random",
        choices=["random", "material"],
        help="The engine policy to use ('random' or 'material')",
    )
    args, unknown = parser.parse_known_args()

    if args.engine == "material":
        engine = MaterialEngine()
    else:
        engine = RandomEngine()

    game = Game(engine=engine)

    sys.stdout.write("id name Hanat\n")
    sys.stdout.write("id author Antigravity & User\n")
    sys.stdout.write("uciok\n")
    sys.stdout.flush()

    while True:
        line = sys.stdin.readline()
        if not line:
            break
        line = line.strip()
        if not line:
            continue

        parts = line.split()
        cmd = parts[0]

        if cmd == "isready":
            sys.stdout.write("readyok\n")
            sys.stdout.flush()
        elif cmd == "ucinewgame":
            game = Game(engine=engine)
        elif cmd == "position":
            if len(parts) > 1:
                if parts[1] == "startpos":
                    game = Game(engine=engine)
                    moves_idx = 2
                elif parts[1] == "fen":
                    fen_parts = []
                    idx = 2
                    while idx < len(parts) and parts[idx] != "moves":
                        fen_parts.append(parts[idx])
                        idx += 1
                    game = Game.from_fen(" ".join(fen_parts))
                    game.engine = engine
                    moves_idx = idx
                else:
                    moves_idx = 1

                if moves_idx < len(parts) and parts[moves_idx] == "moves":
                    for move_str in parts[moves_idx + 1:]:
                        game.push(move_str)
        elif cmd == "go":
            best_move = game.predict_next_move()
            if best_move is None:
                sys.stdout.write("bestmove (none)\n")
            else:
                sys.stdout.write(f"bestmove {best_move.uci()}\n")
            sys.stdout.flush()
        elif cmd == "quit":
            break


if __name__ == "__main__":
    main()
