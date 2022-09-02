"""Tests for all util functions."""
from typing import cast
import unittest
import logging
import importlib
import random

from configparser import ConfigParser
from pathlib import Path

import algobattle
from algobattle.battle_wrappers.iterated import Iterated
import algobattle.util as util
from algobattle.fight_handler import FightHandler
from algobattle.docker import measure_runtime_overhead

logging.disable(logging.CRITICAL)


class Utiltests(unittest.TestCase):
    """Tests for the util functions."""

    def setUp(self) -> None:
        """Set up a problem, default config, fight handler and get a file name not existing on the file system."""
        Problem = importlib.import_module('algobattle.problems.testsproblem')
        self.problem = Problem.Problem()
        config_path = Path(Path(algobattle.__file__).parent, 'config', 'config.ini')
        self.config = ConfigParser()
        self.config.read(config_path)
        self.fight_handler = FightHandler(self.problem, self.config)
        self.problem_path = Path(cast(str, Problem.__file__)).parent
        self.rand_file_name = str(random.randint(0, 2 ** 80))
        while Path(self.rand_file_name).exists():
            self.rand_file_name = str(random.randint(0, 2 ** 80))

    def test_import_problem_from_path_existing_path(self):
        """Importing works when importing a Problem from an existing path."""
        self.assertIsNotNone(util.import_problem_from_path(self.problem_path))

    def test_import_problem_from_path_nonexistant_path(self):
        """An import fails if importing from a nonexistant path."""
        self.assertIsNone(util.import_problem_from_path(Path(self.rand_file_name)))

    def test_initialize_wrapper_existing_path(self):
        """Initializing an existing wrapper works as expected."""
        self.assertEqual(type(util.initialize_wrapper('iterated', self.config)), type(Iterated(self.config)))

    def test_initialize_wrapper_nonexistent_path(self):
        """Initializing a nonexistent wrapper returns None."""
        self.assertEqual(util.initialize_wrapper(self.rand_file_name, self.config), None)

    def test_measure_runtime_overhead(self):
        """The overhead calculation returns some float greater than zero on normal execution."""
        self.assertGreater(measure_runtime_overhead(), 0)

    def test_update_nested_dict(self):
        """A nested dict should be updated with information from another nested dict as expected."""
        dict_to_be_expanded = {0: 1, 1: {0: 0, 1: 0}, 2: 2}
        dict_expanding = {1: {1: 1}, 2: 1}
        self.assertEqual(util.update_nested_dict(dict_to_be_expanded, dict_expanding),
                         {0: 1, 1: {0: 0, 1: 1}, 2: 1})


if __name__ == '__main__':
    unittest.main()
