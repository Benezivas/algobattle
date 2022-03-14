"""Tests for all util functions."""
from pathlib import Path
from typing import cast
import unittest
import logging
import importlib

import algobattle
from algobattle.util import import_problem_from_path
from algobattle.docker import measure_runtime_overhead

logging.disable(logging.CRITICAL)


class Utiltests(unittest.TestCase):
    """Tests for the util functions."""

    @classmethod
    def setUpClass(cls) -> None:
        Problem = importlib.import_module('algobattle.problems.testsproblem')
        cls.problem = Problem.Problem()
        cls.config = Path(algobattle.__file__).resolve().parent / 'config' / 'config.ini'
        cls.tests_path = Path(cast(str, Problem.__file__)).parent

    def test_import_problem_from_path(self):
        self.assertIsNotNone(import_problem_from_path(self.tests_path))
        self.assertRaises(ValueError, lambda: import_problem_from_path(Path("foo")))

    def test_measure_runtime_overhead(self):
        self.assertGreater(measure_runtime_overhead(), 0)


if __name__ == '__main__':
    unittest.main()
