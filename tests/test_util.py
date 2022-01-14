"""Tests for all util functions."""
import unittest
import logging
import importlib
import os

import algobattle
from algobattle.match import Match
from algobattle.team import Team
from algobattle.util import import_problem_from_path, measure_runtime_overhead, run_subprocess

logging.disable(logging.CRITICAL)


class Utiltests(unittest.TestCase):
    """Tests for the util functions."""

    def setUp(self) -> None:
        Problem = importlib.import_module('algobattle.problems.testsproblem')
        self.problem = Problem.Problem()
        self.config = os.path.join(os.path.dirname(os.path.abspath(algobattle.__file__)), 'config', 'config.ini')
        self.tests_path = Problem.__file__[:-12]  # remove /__init__.py

    def test_import_problem_from_path(self):
        self.assertIsNotNone(import_problem_from_path(self.tests_path))
        self.assertIsNone(import_problem_from_path('foo'))

    def test_measure_runtime_overhead(self):
        self.assertGreater(measure_runtime_overhead(), 0)

    def test_run_subprocess(self):
        team = Team('0', self.tests_path + '/generator_timeout', self.tests_path + '/solver')
        match_run_timeout = Match(self.problem, self.config, [team])
        raw_output, _ = run_subprocess(match_run_timeout.base_run_command + ['generator-0'], 0, 2)
        self.assertIsNone(raw_output)


if __name__ == '__main__':
    unittest.main()
