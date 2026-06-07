from __future__ import annotations
import os
import sys
import socket
import threading
import subprocess
import tempfile
import shutil
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..game import Game
    from ..move import Move


class EngineUCIServer:
    """A local TCP socket server that wraps a Python chess engine in a UCI loop."""

    def __init__(self, engine: BaseEngine):
        self.engine = engine
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind(("127.0.0.1", 0))
        self.port = self.sock.getsockname()[1]
        self.sock.listen(1)
        self.thread = threading.Thread(target=self._listen, daemon=True)
        self.thread.start()

    def _listen(self):
        from ..game import Game
        try:
            conn, addr = self.sock.accept()
            game = Game(engine=self.engine)
            rfile = conn.makefile("r", encoding="utf-8")
            wfile = conn.makefile("w", encoding="utf-8")
            while True:
                line = rfile.readline()
                if not line:
                    break
                line = line.strip()
                if not line:
                    continue
                parts = line.split()
                cmd = parts[0]
                if cmd == "uci":
                    wfile.write("id name HanatEngine\nid author Antigravity\nuciok\n")
                    wfile.flush()
                elif cmd == "isready":
                    wfile.write("readyok\n")
                    wfile.flush()
                elif cmd == "ucinewgame":
                    game = Game(engine=self.engine)
                elif cmd == "position":
                    if len(parts) > 1:
                        if parts[1] == "startpos":
                            game = Game(engine=self.engine)
                            moves_idx = 2
                        elif parts[1] == "fen":
                            fen_parts = []
                            idx = 2
                            while idx < len(parts) and parts[idx] != "moves":
                                fen_parts.append(parts[idx])
                                idx += 1
                            game = Game.from_fen(" ".join(fen_parts))
                            game.engine = self.engine
                            moves_idx = idx
                        else:
                            moves_idx = 1
                        if moves_idx < len(parts) and parts[moves_idx] == "moves":
                            for move_str in parts[moves_idx + 1:]:
                                game.push(move_str)
                elif cmd == "go":
                    best_move = game.predict_next_move()
                    if best_move is None:
                        wfile.write("bestmove (none)\n")
                    else:
                        wfile.write(f"bestmove {best_move.uci()}\n")
                    wfile.flush()
                elif cmd == "quit":
                    break
            conn.close()
        except Exception:
            pass
        finally:
            self.sock.close()


class BaseEngine:
    """Base interface for a chess policy/search engine."""

    def predict_next_move(self, game: Game) -> Optional[Move]:
        """Predict and return the next best move for the active side.

        Args:
            game: A Game instance.

        Returns:
            A Move object if a legal move is available, else None.
        """
        raise NotImplementedError

    def find_elo(
        self,
        benchmark_level: int = 0,
        num_games: int = 50,
        concurrency: int = 2,
        tc: str = "40/10",
        stockfish_path: Optional[str] = None
    ) -> float:
        """Automates running matches against Stockfish and calculating ELO using Ordo.

        Args:
            benchmark_level: Stockfish Skill Level (0-20, default 0).
            num_games: Total number of games to play.
            concurrency: Number of concurrent games to run.
            tc: Time control (default "40/10").
            stockfish_path: Optional path to Stockfish binary.

        Returns:
            The calculated ELO rating relative to Stockfish (set at 0).
        """
        # 1. Find Stockfish binary
        if stockfish_path is None:
            from .stockfish import find_stockfish
            try:
                stockfish_path = find_stockfish()
            except FileNotFoundError:
                raise FileNotFoundError("Stockfish binary not found. Please install Stockfish or pass stockfish_path.")

        # 2. Check cutechess-cli and ordo binaries
        if not shutil.which("cutechess-cli"):
            raise FileNotFoundError("cutechess-cli binary not found in PATH.")
        if not shutil.which("ordo"):
            raise FileNotFoundError("ordo binary not found in PATH.")

        # 3. Start the UCI server for this engine
        server = EngineUCIServer(self)

        # 4. Create the client forwarder script
        client_code = """import socket, sys, threading
def forward_stdin(s):
    try:
        for line in sys.stdin:
            s.sendall(line.encode('utf-8'))
    except Exception: pass
port = int(sys.argv[1])
s = socket.create_connection(("127.0.0.1", port))
t = threading.Thread(target=forward_stdin, args=(s,), daemon=True)
t.start()
try:
    while True:
        data = s.recv(4096)
        if not data: break
        sys.stdout.write(data.decode('utf-8'))
        sys.stdout.flush()
except Exception: pass
"""
        # Create temp files
        temp_dir = tempfile.mkdtemp()
        client_path = os.path.join(temp_dir, "temp_client.py")
        pgn_path = os.path.join(temp_dir, "results.pgn")

        try:
            with open(client_path, "w", encoding="utf-8") as f:
                f.write(client_code)

            # Compute rounds (each round is 2 games in a 2-engine match)
            rounds = max(1, num_games // 2)

            # 5. Run cutechess-cli
            cmd_cutechess = [
                "cutechess-cli",
                "-engine", "name=HanatEngine", "cmd=python3", f"arg={client_path}", f"arg={server.port}",
                "-engine", "name=Stockfish", f"cmd={stockfish_path}", f"option.Skill Level={benchmark_level}",
                "-each", "proto=uci", f"tc={tc}",
                "-rounds", str(rounds),
                "-games", "2",  # 2 games per round so colors alternate -> rounds*2 == num_games
                "-concurrency", str(concurrency),
                "-pgnout", pgn_path
            ]
            
            result_cute = subprocess.run(cmd_cutechess, capture_output=True, text=True)
            if result_cute.returncode != 0:
                print("cutechess-cli stdout:", result_cute.stdout)
                print("cutechess-cli stderr:", result_cute.stderr)
                raise RuntimeError(f"cutechess-cli failed with exit code {result_cute.returncode}")

            # 6. Run Ordo
            cmd_ordo = [
                "ordo",
                "-p", pgn_path,
                "-a", "0",
                "-A", "Stockfish",
                "-G",  # force a rating even when the result graph is poorly connected
                       # (e.g. a weak engine that wins or loses every game)
            ]
            result_ordo = subprocess.run(cmd_ordo, capture_output=True, text=True)
            if result_ordo.returncode != 0:
                print("ordo stdout:", result_ordo.stdout)
                print("ordo stderr:", result_ordo.stderr)
                raise RuntimeError(f"ordo failed with exit code {result_ordo.returncode}")

            # 7. Parse Ordo ratings output
            stdout = result_ordo.stdout
            for line in stdout.splitlines():
                if "HanatEngine" in line:
                    tokens = line.split()
                    try:
                        idx = tokens.index("HanatEngine")
                        rating = float(tokens[idx + 1])
                        return rating
                    except (ValueError, IndexError):
                        pass
            
            raise RuntimeError(f"Could not find HanatEngine rating in Ordo output:\n{stdout}")

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
