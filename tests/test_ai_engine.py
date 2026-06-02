import unittest
from hanat import Game, BaseEngine, Move


class CustomAlwaysFirstEngine(BaseEngine):
    def predict_next_move(self, game: Game) -> Move:
        legal = game.legal_moves()
        if not legal:
            return None
        return legal[0]


class TestAIEngine(unittest.TestCase):
    def test_default_engine_is_none(self):
        game = Game()
        self.assertIsNone(game.engine)
        with self.assertRaises(ValueError):
            game.predict_next_move()

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
