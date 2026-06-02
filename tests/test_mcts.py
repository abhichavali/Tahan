import unittest
from hanat import Game, Move, Board, MCTSEngine

class TestMCTS(unittest.TestCase):
    def test_value_head_required(self):
        # Without value_head, a ValueError should be raised when predicting.
        engine = MCTSEngine(num_simulations=10)
        game = Game(engine=engine)
        with self.assertRaises(ValueError):
            game.predict_next_move()

    def test_mcts_with_value_head(self):
        # A mock value head that evaluates positions.
        # It should return a float (expected outcome from active player's POV).
        # Let's say it returns 0.5 (slight advantage) for any state.
        def mock_value_head(board):
            self.assertIsInstance(board, Board)
            return 0.5

        engine = MCTSEngine(value_head=mock_value_head, num_simulations=30)
        game = Game(engine=engine)
        move = game.predict_next_move()
        self.assertIsInstance(move, Move)
        self.assertIn(move, game.legal_moves())

    def test_mcts_with_policy_head_sequence(self):
        # A mock policy head that returns a list of probabilities corresponding to legal moves.
        def mock_policy_head(board):
            self.assertIsInstance(board, Board)
            legal = board.legal_moves()
            probs = [0.0] * len(legal)
            probs[0] = 1.0
            return probs

        def mock_value_head(board):
            return 0.1

        engine = MCTSEngine(policy_head=mock_policy_head, value_head=mock_value_head, num_simulations=20)
        game = Game(engine=engine)
        
        move = game.predict_next_move()
        self.assertEqual(move, game.legal_moves()[0])

    def test_mcts_with_policy_head_dict_uci(self):
        # A mock policy head that returns a dict mapping UCI strings to probabilities.
        def mock_policy_head(board):
            self.assertIsInstance(board, Board)
            legal = board.legal_moves()
            probs = {}
            for i, m in enumerate(legal):
                probs[m.uci()] = 1.0 if i == 0 else 0.0
            return probs

        def mock_value_head(board):
            return 0.0

        engine = MCTSEngine(policy_head=mock_policy_head, value_head=mock_value_head, num_simulations=20)
        game = Game(engine=engine)
        move = game.predict_next_move()
        self.assertEqual(move, game.legal_moves()[0])

    def test_mcts_with_policy_head_dict_tuple(self):
        # A mock policy head that returns a dict mapping (from, to, promo) tuples to probabilities.
        def mock_policy_head(board):
            self.assertIsInstance(board, Board)
            legal = board.legal_moves()
            probs = {}
            for i, m in enumerate(legal):
                key = (m.from_sq, m.to_sq, m.promotion)
                probs[key] = 1.0 if i == 0 else 0.0
            return probs

        def mock_value_head(board):
            return 0.0

        engine = MCTSEngine(policy_head=mock_policy_head, value_head=mock_value_head, num_simulations=20)
        game = Game(engine=engine)
        move = game.predict_next_move()
        self.assertEqual(move, game.legal_moves()[0])

    def test_set_heads_dynamically(self):
        engine = MCTSEngine(num_simulations=10)
        
        def mock_policy_head(board):
            legal = board.legal_moves()
            probs = [0.0] * len(legal)
            probs[-1] = 1.0  # favor the last move
            return probs
            
        def mock_value_head(board):
            return -0.2

        engine.set_policy_head(mock_policy_head)
        engine.set_value_head(mock_value_head)
        
        game = Game(engine=engine)
        move = game.predict_next_move()
        
        self.assertEqual(move, game.legal_moves()[-1])


if __name__ == "__main__":
    unittest.main()
