import unittest
from hanat import Game, BaseEngine, Move, RandomEngine


class CustomAlwaysFirstEngine(BaseEngine):
    def predict_next_move(self, game: Game) -> Move:
        legal = game.legal_moves()
        if not legal:
            return None
        return legal[0]


class TestAIEngine(unittest.TestCase):
    def test_default_engine_is_random(self):
        game = Game()
        self.assertIsInstance(game.engine, RandomEngine)
        move = game.predict_next_move()
        self.assertIsInstance(move, Move)
        self.assertIn(move, game.legal_moves())

    def test_custom_engine(self):
        engine = CustomAlwaysFirstEngine()
        game = Game(engine=engine)
        self.assertEqual(game.engine, engine)

        move = game.predict_next_move()
        self.assertEqual(move, game.legal_moves()[0])

    def test_change_engine_at_runtime(self):
        game = Game()
        engine = CustomAlwaysFirstEngine()
        game.engine = engine

        move = game.predict_next_move()
        self.assertEqual(move, game.legal_moves()[0])


if __name__ == "__main__":
    unittest.main()
