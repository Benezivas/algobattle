"""Tests for all util functions."""
import unittest
import logging
import random
from pathlib import Path

from algobattle.battle_wrappers.iterated import Iterated
from algobattle.match import MatchConfig
import algobattle.util as util
from algobattle.fight_handler import FightHandler
from algobattle.battle_wrapper import BattleWrapper
from . import testsproblem

logging.disable(logging.CRITICAL)


class Utiltests(unittest.TestCase):
    """Tests for the util functions."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up a problem, default config, fight handler and get a file name not existing on the file system."""
        problem = testsproblem.Problem()
        cls.config = MatchConfig()
        cls.fight_handler = FightHandler(problem, **cls.config.docker_params)
        cls.problem_path = Path(testsproblem.__file__).parent
        cls.rand_file_name = str(random.randint(0, 2 ** 80))
        while Path(cls.rand_file_name).exists():
            cls.rand_file_name = str(random.randint(0, 2 ** 80))

    def test_import_problem_from_path_existing_path(self):
        """Importing works when importing a Problem from an existing path."""
        self.assertIsNotNone(util.import_problem_from_path(self.problem_path))

    def test_import_problem_from_path_nonexistant_path(self):
        """An import fails if importing from a nonexistant path."""
        self.assertRaises(ValueError, lambda: util.import_problem_from_path(Path(self.rand_file_name)))

    def test_initialize_wrapper_existing_path(self):
        """Initializing an existing wrapper works as expected."""
        self.assertEqual(BattleWrapper.get_wrapper("iterated"), Iterated)

    def test_initialize_wrapper_nonexistent_path(self):
        """Initializing a nonexistent wrapper raises an error."""
        with self.assertRaises(ValueError):
            BattleWrapper.get_wrapper(self.rand_file_name)


if __name__ == '__main__':
    unittest.main()
