"""Tests for all util functions."""
import unittest
import logging
import random
from pathlib import Path

from algobattle.match import MatchConfig
from algobattle.problem import Problem
from algobattle.battle import Battle, Iterated, Averaged
from . import testsproblem

logging.disable(logging.CRITICAL)


class Utiltests(unittest.TestCase):
    """Tests for the util functions."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up a problem, default config, fight handler and get a file name not existing on the file system."""
        cls.config = MatchConfig()
        cls.problem_path = Path(testsproblem.__file__).parent / "problem.py"
        cls.rand_file_name = str(random.randint(0, 2 ** 80))
        while Path(cls.rand_file_name).exists():
            cls.rand_file_name = str(random.randint(0, 2 ** 80))

    def test_import_problem_from_path_existing_path(self):
        """Importing works when importing a Problem from an existing path."""
        self.assertIsNotNone(Problem.import_from_path(self.problem_path))

    def test_import_problem_from_path_nonexistant_path(self):
        """An import fails if importing from a nonexistant path."""
        with self.assertRaises(ValueError):
            Problem.import_from_path(Path(self.rand_file_name))

    def test_default_battle_types(self):
        """Initializing an existing battle type works as expected."""
        self.assertEqual(Battle.all()["iterated"], Iterated)
        self.assertEqual(Battle.all()["averaged"], Averaged)


if __name__ == '__main__':
    unittest.main()
