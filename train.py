#!/usr/bin/env python3
"""Train a tiny GNN to predict game outcome from a chess position.

This is a runnable scaffold, not a tuned model — it wires the Hanat data API to
PyTorch Geometric end to end so `docker compose run` does something real:

  1. stream Games from a PGN dataset (hanat.iter_games),
  2. turn sampled positions into graphs (64 nodes = squares, piece one-hots as
     node features, king-move adjacency as edges),
  3. label each graph with the game's final result (+1 white win, -1 black win,
     0 draw), from the side-to-move's POV,
  4. train a 2-layer GCN + global mean pool to regress that label.

Swap the model / features / labels for your own; the plumbing stays the same.

    python train.py --data data/twic1646.pgn --max-games 3000 --epochs 5
"""
from __future__ import annotations

import argparse
import random
from pathlib import Path

import torch
import torch.nn.functional as F
from torch_geometric.data import Data
from torch_geometric.loader import DataLoader
from torch_geometric.nn import GCNConv, global_mean_pool

from hanat import iter_games
from hanat.game import BLACK_WINS, DRAW, WHITE_WINS

# 12 piece planes (PNBRQK / pnbrqk) + 1 "empty" plane = 13 features per square.
_PIECES = "PNBRQKpnbrqk"
_PIECE_INDEX = {p: i for i, p in enumerate(_PIECES)}
NUM_NODE_FEATURES = len(_PIECES) + 1


def _king_adjacency() -> torch.Tensor:
    """edge_index (2, E) connecting each square to its up-to-8 neighbours."""
    src, dst = [], []
    for sq in range(64):
        f, r = sq % 8, sq // 8
        for df in (-1, 0, 1):
            for dr in (-1, 0, 1):
                if df == 0 and dr == 0:
                    continue
                nf, nr = f + df, r + dr
                if 0 <= nf < 8 and 0 <= nr < 8:
                    src.append(sq)
                    dst.append(nr * 8 + nf)
    return torch.tensor([src, dst], dtype=torch.long)


_EDGE_INDEX = _king_adjacency()


def _fen_to_features(fen: str) -> torch.Tensor:
    """Board part of a FEN -> (64, 13) one-hot node feature matrix (a1=0)."""
    x = torch.zeros((64, NUM_NODE_FEATURES), dtype=torch.float)
    rows = fen.split(" ", 1)[0].split("/")  # rank 8 first
    for rank_from_top, row in enumerate(rows):
        rank = 7 - rank_from_top
        file = 0
        for ch in row:
            if ch.isdigit():
                for _ in range(int(ch)):
                    x[rank * 8 + file, NUM_NODE_FEATURES - 1] = 1.0  # empty
                    file += 1
            else:
                x[rank * 8 + file, _PIECE_INDEX[ch]] = 1.0
                file += 1
    return x


_LABEL = {WHITE_WINS: 1.0, BLACK_WINS: -1.0, DRAW: 0.0}


def build_dataset(
    path: str,
    max_games: int,
    positions_per_game: int,
    seed: int = 0,
) -> list[Data]:
    """Sample positions from games and turn them into labelled graphs."""
    rng = random.Random(seed)
    graphs: list[Data] = []
    for gi, game in enumerate(iter_games(path)):
        if gi >= max_games:
            break
        result = game.result()
        if result not in _LABEL:
            continue  # unfinished / unknown result — skip
        history = game.history
        if not history:
            continue
        # Replay to collect the FEN before each ply (side-to-move POV label).
        replay = type(game)()
        fens, to_move_white = [], []
        for ply in history:
            fens.append(replay.fen())
            to_move_white.append(replay.turn == "white")
            replay.push(ply["move"])
        idxs = range(len(fens))
        if len(fens) > positions_per_game:
            idxs = rng.sample(range(len(fens)), positions_per_game)
        for i in idxs:
            y = _LABEL[result]
            if not to_move_white[i]:
                y = -y  # flip to the side-to-move's perspective
            graphs.append(
                Data(
                    x=_fen_to_features(fens[i]),
                    edge_index=_EDGE_INDEX,
                    y=torch.tensor([y], dtype=torch.float),
                )
            )
    return graphs


class OutcomeGCN(torch.nn.Module):
    def __init__(self, hidden: int = 64):
        super().__init__()
        self.conv1 = GCNConv(NUM_NODE_FEATURES, hidden)
        self.conv2 = GCNConv(hidden, hidden)
        self.head = torch.nn.Linear(hidden, 1)

    def forward(self, data: Data) -> torch.Tensor:
        x = F.relu(self.conv1(data.x, data.edge_index))
        x = F.relu(self.conv2(x, data.edge_index))
        x = global_mean_pool(x, data.batch)
        return torch.tanh(self.head(x)).squeeze(-1)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", default="data/twic1646.pgn", help="PGN dataset path")
    p.add_argument("--max-games", type=int, default=2000)
    p.add_argument("--positions-per-game", type=int, default=8)
    p.add_argument("--epochs", type=int, default=5)
    p.add_argument("--batch-size", type=int, default=256)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    p.add_argument("--out", default="checkpoints/outcome_gcn.pt")
    args = p.parse_args()

    if not Path(args.data).exists():
        raise SystemExit(
            f"dataset not found: {args.data}\n"
            "Point --data at a PGN file (the repo's data/ dir is a mounted volume)."
        )

    print(f"loading up to {args.max_games} games from {args.data} ...")
    graphs = build_dataset(args.data, args.max_games, args.positions_per_game)
    if not graphs:
        raise SystemExit("no training positions were produced — check the dataset.")
    print(f"built {len(graphs)} position graphs")

    loader = DataLoader(graphs, batch_size=args.batch_size, shuffle=True)
    device = torch.device(args.device)
    model = OutcomeGCN().to(device)
    opt = torch.optim.Adam(model.parameters(), lr=args.lr)

    model.train()
    for epoch in range(1, args.epochs + 1):
        total = 0.0
        for batch in loader:
            batch = batch.to(device)
            opt.zero_grad()
            pred = model(batch)
            loss = F.mse_loss(pred, batch.y)
            loss.backward()
            opt.step()
            total += loss.item() * batch.num_graphs
        print(f"epoch {epoch:>2}/{args.epochs}  mse={total / len(graphs):.4f}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), out)
    print(f"saved model to {out}")


if __name__ == "__main__":
    main()
