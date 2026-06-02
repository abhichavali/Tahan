from __future__ import annotations
from typing import TYPE_CHECKING, Optional, Callable, Dict, Union, List, Tuple
from .base import BaseEngine
from ..board import Board, CppBoard
from ..move import Move

if TYPE_CHECKING:
    from ..game import Game

class MCTSEngine(BaseEngine):
    """An engine that uses the Monte Carlo Tree Search (MCTS) algorithm in C++."""

    def __init__(
        self,
        policy_head: Optional[Callable[[Board], Union[Dict[str, float], List[float]]]] = None,
        value_head: Optional[Callable[[Board], float]] = None,
        num_simulations: int = 100,
        c_puct: float = 1.414,
    ):
        self.policy_head = policy_head
        self.value_head = value_head
        self.num_simulations = num_simulations
        self.c_puct = c_puct

    def set_policy_head(self, policy_head: Optional[Callable]) -> None:
        """Set the policy head method."""
        self.policy_head = policy_head

    def set_value_head(self, value_head: Optional[Callable]) -> None:
        """Set the value head method."""
        self.value_head = value_head

    def predict_next_move(self, game: Game) -> Optional[Move]:
        if self.value_head is None:
            raise ValueError("value_head must be set before predicting the next move.")

        board = game.board
        
        # If backend is pure Python, we temporarily convert/load the FEN into CppBoard 
        # because the native C++ MCTS runs on the optimized C++ board structure.
        if not isinstance(board, CppBoard) and CppBoard is not None:
            cpp_board = CppBoard(board.fen())
        else:
            cpp_board = board

        if cpp_board is None:
            raise RuntimeError("Native C++ extension is required for MCTS.")

        # Run MCTS search using the C++ backend
        # Returns: (best_move_tuple, visit_counts)
        res = cpp_board.mcts_search(
            policy_head=self.policy_head,
            value_head=self.value_head,
            num_simulations=self.num_simulations,
            c_puct=self.c_puct,
        )
        
        if res is None:
            return None
        
        best_move_tup, _ = res
        if best_move_tup is None:
            return None
            
        f, t, p = best_move_tup
        return Move(f, t, p or None)
