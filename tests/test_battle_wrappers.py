"""Tests for all util functions."""
import unittest
import logging
import importlib
import os

import algobattle
from algobattle.battle_wrappers.averaged import Averaged
from algobattle.battle_wrappers.iterated import Iterated

logging.disable(logging.CRITICAL)


class Utiltests(unittest.TestCase):
    """Tests for the util functions."""

    def setUp(self) -> None:
        Problem = importlib.import_module('algobattle.problems.testsproblem')
        self.problem = Problem.Problem()
        self.config = os.path.join(os.path.dirname(os.path.abspath(algobattle.__file__)), 'config', 'config.ini')
        self.tests_path = Problem.__file__[:-12]  # remove /__init__.py
        self.averaged_wrapper = Averaged()
        self.iterated_wrapper = Iterated()

    def test_averaged_battle_wrapper(self):
        pass  # TODO: Implement tests for averaged battle wrapper

    def test_iterated_battle_wrapper(self):
        pass  # TODO: Implement tests for iterated battle wrapper

    def test_calculate_points_iterated_weird_type(self):
        match_data = {'rounds': 2, 'type': 'foo'}
        self.assertEqual(self.iterated_wrapper.calculate_points(match_data, 100), {})

    def test_calculate_points_iterated_zero_rounds(self):
        match_data = {'rounds': 0, 'type': 'iterated'}
        self.assertEqual(self.iterated_wrapper.calculate_points(match_data, 100), {})

    def test_calculate_points_iterated_no_successful_round(self):
        match_data = {'rounds': 2,
                      'type': 'iterated',
                      ('0', '1'): {0: {'solved': 0}, 1: {'solved': 0}},
                      ('1', '0'): {0: {'solved': 0}, 1: {'solved': 0}}}
        self.assertEqual(self.iterated_wrapper.calculate_points(match_data, 100), {'0': 50, '1': 50})

    def test_calculate_points_iterated_draw(self):
        match_data = {'rounds': 2,
                      'type': 'iterated',
                      ('0', '1'): {0: {'solved': 20}, 1: {'solved': 10}},
                      ('1', '0'): {0: {'solved': 10}, 1: {'solved': 20}}}
        self.assertEqual(self.iterated_wrapper.calculate_points(match_data, 100), {'0': 50, '1': 50})

    def test_calculate_points_iterated_domination(self):
        match_data = {'rounds': 2,
                      'type': 'iterated',
                      ('0', '1'): {0: {'solved': 10}, 1: {'solved': 10}},
                      ('1', '0'): {0: {'solved': 0}, 1: {'solved': 0}}}
        self.assertEqual(self.iterated_wrapper.calculate_points(match_data, 100), {'0': 0, '1': 100})
        

    def test_calculate_points_averaged_weird_type(self):
        match_data = {'rounds': 2, 'type': 'foo'}
        self.assertEqual(self.averaged_wrapper.calculate_points(match_data, 100), {})

    def test_calculate_points_averaged_zero_rounds(self):
        match_data = {'rounds': 0, 'type': 'iterated'}
        self.assertEqual(self.iterated_wrapper.calculate_points(match_data, 100), {})

    def test_calculate_points_averaged_draw(self):
        match_data = {'rounds': 2,
                      'type': 'averaged',
                      ('0', '1'): {0: {'approx_ratios': [1.5, 1.5, 1.5]},
                                   1: {'approx_ratios': [1.5, 1.5, 1.5]}},
                      ('1', '0'): {0: {'approx_ratios': [1.5, 1.5, 1.5]},
                                   1: {'approx_ratios': [1.5, 1.5, 1.5]}}}
        self.assertEqual(self.averaged_wrapper.calculate_points(match_data, 100), {'0': 50, '1': 50})

    def test_calculate_points_averaged_domination(self):
        match_data = {'rounds': 2,
                      'type': 'averaged',
                      ('0', '1'): {0: {'approx_ratios': [1.5, 1.5, 1.5]},
                                   1: {'approx_ratios': [1.5, 1.5, 1.5]}},
                      ('1', '0'): {0: {'approx_ratios': [1.0, 1.0, 1.0]},
                                   1: {'approx_ratios': [1.0, 1.0, 1.0]}}}
        self.assertEqual(self.averaged_wrapper.calculate_points(match_data, 100), {'0': 60, '1': 40})

    def test_calculate_points_averaged_no_successful_round(self):
        match_data = {'rounds': 2,
                      'type': 'averaged',
                      ('0', '1'): {0: {'approx_ratios': [0, 0, 0]},
                                   1: {'approx_ratios': [0, 0, 0]}},
                      ('1', '0'): {0: {'approx_ratios': [0, 0, 0]},
                                   1: {'approx_ratios': [0, 0, 0]}}}
        self.assertEqual(self.averaged_wrapper.calculate_points(match_data, 100), {'0': 50, '1': 50})
