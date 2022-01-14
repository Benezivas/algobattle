"""Tests for all util functions."""
import unittest
import logging
import importlib
import os

import algobattle
from algobattle.match import Match
from algobattle.team import Team
from algobattle.util import import_problem_from_path, measure_runtime_overhead, calculate_points, run_subprocess

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

    def test_calculate_points_weird_type(self):
        match_data = {'rounds': 2, 'type': 'foo'}
        self.assertEqual(calculate_points(match_data, 100), {})

    def test_calculate_points_zero_rounds(self):
        match_data = {'rounds': 0, 'type': 'iterated'}
        self.assertEqual(calculate_points(match_data, 100), {})

    def test_calculate_points_iterated_draw(self):
        match_data = {'rounds': 2,
                      'type': 'iterated',
                      ('0', '1'): {0: {'solved': 20}, 1: {'solved': 10}},
                      ('1', '0'): {0: {'solved': 10}, 1: {'solved': 20}}}
        self.assertEqual(calculate_points(match_data, 100), {'0': 50, '1': 50})

    def test_calculate_points_iterated_domination(self):
        match_data = {'rounds': 2,
                      'type': 'iterated',
                      ('0', '1'): {0: {'solved': 10}, 1: {'solved': 10}},
                      ('1', '0'): {0: {'solved': 0}, 1: {'solved': 0}}}
        self.assertEqual(calculate_points(match_data, 100), {'0': 0, '1': 100})

    def test_calculate_points_averaged_draw(self):
        match_data = {'rounds': 2,
                      'type': 'averaged',
                      ('0', '1'): {0: {'approx_ratios': [1.5, 1.5, 1.5]},
                                   1: {'approx_ratios': [1.5, 1.5, 1.5]}},
                      ('1', '0'): {0: {'approx_ratios': [1.5, 1.5, 1.5]},
                                   1: {'approx_ratios': [1.5, 1.5, 1.5]}}}
        self.assertEqual(calculate_points(match_data, 100), {'0': 50, '1': 50})

    def test_calculate_points_averaged_domination(self):
        match_data = {'rounds': 2,
                      'type': 'averaged',
                      ('0', '1'): {0: {'approx_ratios': [1.5, 1.5, 1.5]},
                                   1: {'approx_ratios': [1.5, 1.5, 1.5]}},
                      ('1', '0'): {0: {'approx_ratios': [1.0, 1.0, 1.0]},
                                   1: {'approx_ratios': [1.0, 1.0, 1.0]}}}
        self.assertEqual(calculate_points(match_data, 100), {'0': 60, '1': 40})

    def test_run_subprocess(self):
        team = Team('0', self.tests_path + '/generator_timeout', self.tests_path + '/solver')
        match = Match(self.problem, self.config, [team])
        raw_output, _ = run_subprocess(match.generator_base_run_command(match.space_generator) + ['generator-0'], 0, 2)
        self.assertIsNone(raw_output)


if __name__ == '__main__':
    unittest.main()
