"""Tests for all util functions."""
import unittest
import logging
import importlib
import os

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
        cls.config = os.path.join(os.path.dirname(os.path.abspath(algobattle.__file__)), 'config', 'config.ini')
        problem_file = Problem.__file__
        assert problem_file is not None
        cls.tests_path = problem_file[:-12]  # remove /__init__.py

    def test_import_problem_from_path(self):
        self.assertIsNotNone(import_problem_from_path(self.tests_path))
        self.assertIsNone(import_problem_from_path('foo'))

    def test_measure_runtime_overhead(self):
        self.assertGreater(measure_runtime_overhead(), 0)


if __name__ == '__main__':
    unittest.main()
