import unittest
import unittest.mock
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

    @unittest.mock.patch("shutil.which")
    @unittest.mock.patch("subprocess.run")
    def test_find_elo_mock(self, mock_run, mock_which):
        # 1. Mock shutil.which to find the binaries
        mock_which.return_value = "/usr/local/bin/mock-binary"

        # 2. Mock subprocess.run outputs
        mock_ordo_stdout = """
Pl  Name          Rating  Elos   +/-  Points  Games   Score    Draw
 1  Stockfish          0     0     0    20.0     40   50.0%    0.0%
 2  HanatEngine      145   145    25    20.0     40   50.0%    0.0%
"""
        mock_cute_res = unittest.mock.Mock()
        mock_cute_res.returncode = 0
        mock_cute_res.stdout = "cutechess match finished"
        
        mock_ordo_res = unittest.mock.Mock()
        mock_ordo_res.returncode = 0
        mock_ordo_res.stdout = mock_ordo_stdout

        mock_run.side_effect = [mock_cute_res, mock_ordo_res]

        # 3. Create engine and call find_elo
        def mock_value_head(board):
            return 0.0
        engine = MCTSEngine(value_head=mock_value_head, num_simulations=10)

        elo = engine.find_elo(num_games=4, stockfish_path="/mock/stockfish")

        # 4. Verify ELO rating is parsed correctly
        self.assertEqual(elo, 145.0)

        # 5. Check mock_run was called with correct parameters
        self.assertEqual(mock_run.call_count, 2)
        first_call_args = mock_run.call_args_list[0][0][0]
        self.assertEqual(first_call_args[0], "cutechess-cli")
        self.assertIn("option.Skill Level=0", first_call_args)


if __name__ == "__main__":
    unittest.main()
