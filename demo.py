#!/usr/bin/env python3
"""Demo showcasing plug-and-play policy and value heads with the new C++ MCTS engine."""

import math
import random
from hanat import Game, MCTSEngine


def random_policy_head(board):
    """Assigns random scores to legal moves and returns their softmax probabilities using pure Python."""
    legal = board.legal_moves()
    if not legal:
        return []

    # Assign a random float score to each legal move (drawn from normal distribution)
    raw_scores = [random.normalvariate(0.0, 1.0) for _ in range(len(legal))]

    # Apply softmax to normalize them into a valid probability distribution (with numerical stability)
    max_score = max(raw_scores)
    exp_scores = [math.exp(s - max_score) for s in raw_scores]
    sum_exp = sum(exp_scores)
    probabilities = [e / sum_exp for e in exp_scores]

    # Return as a list of floats (matching index-for-index with board.legal_moves())
    return probabilities


def random_value_head(board):
    """Evaluates the position by returning a random score between -1 and 1."""
    # Value is from the perspective of the active player to move
    return random.uniform(-1.0, 1.0)


def main():
    print("=== Hanat C++ PUCT MCTS Engine Demo ===")

    # 1. Instantiate the MCTS engine with our custom policy and value heads
    engine = MCTSEngine(
        policy_head=random_policy_head,
        value_head=random_value_head,
        num_simulations=100,  # Run 100 search iterations per move
        c_puct=1.414,
    )

    # 2. Start a chess game and plug in our engine
    game = Game(engine=engine)

    print("Initial Board Position:")
    print(game.board_str())
    print("-" * 40)

    # 3. Play a few moves using the MCTS engine
    for ply in range(1, 6):
        print(f"\n[Ply {ply}] Search in progress...")
        move = game.predict_next_move()

        if move is None:
            print("No legal moves available or game ended.")
            break

        # Render the selected move in SAN format
        san = game.board.san(move)
        game.push(move)

        print(f"MCTS Selected Move: {san} (UCI: {move.uci()})")
        print("Updated Board State:")
        print(game.board_str())
        print(f"FEN: {game.fen()}")
        print("-" * 40)


if __name__ == "__main__":
    main()
