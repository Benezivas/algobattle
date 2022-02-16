"""Tests for all util functions."""
import subprocess
import unittest
import logging
import importlib
import os

import algobattle
from algobattle.battle_wrappers.averaged import Averaged
from algobattle.battle_wrappers.iterated import Iterated
from algobattle.match import Match
from algobattle.team import Team

logging.disable(logging.CRITICAL)


class BattleWrapperTests(unittest.TestCase):
    """Tests for the battle wrapper functions."""

    @classmethod
    def setUpClass(cls) -> None:
        Problem = importlib.import_module('algobattle.problems.testsproblem')
        assert Problem is not None
        cls.problem = Problem.Problem()
        base_path = os.path.dirname(os.path.abspath(algobattle.__file__))
        generator_path = os.path.join(base_path, "problems", "testsproblem", "generator")
        solver_path = os.path.join(base_path, "problems", "testsproblem", "solver")
        cls.config = os.path.join(base_path, 'config', 'config.ini')
        cls.match = Match(cls.problem, cls.config, [Team("0", generator_path, solver_path), Team("1", generator_path, solver_path)])

    def test_averaged_battle_wrapper(self):
        pass  # TODO: Implement tests for averaged battle wrapper

    def test_iterated_battle_wrapper(self):
        pass  # TODO: Implement tests for iterated battle wrapper

    def test_calculate_points_iterated_zero_rounds(self):
        battle = Iterated(self.match, self.problem, rounds=0)
        self.assertEqual(battle.calculate_points(100), {})

    def test_calculate_points_iterated_no_successful_round(self):
        battle = Iterated(self.match, self.problem, rounds=2)
        battle.pairs[("0", "1")][0].solved = 0
        battle.pairs[("0", "1")][1].solved = 0
        battle.pairs[("1", "0")][0].solved = 0
        battle.pairs[("1", "0")][1].solved = 0
        self.assertEqual(battle.calculate_points(100), {'0': 50, '1': 50})

    def test_calculate_points_iterated_draw(self):
        battle = Iterated(self.match, self.problem, rounds=2)
        battle.pairs[("0", "1")][0].solved = 20
        battle.pairs[("0", "1")][1].solved = 10
        battle.pairs[("1", "0")][0].solved = 10
        battle.pairs[("1", "0")][1].solved = 20
        self.assertEqual(battle.calculate_points(100), {'0': 50, '1': 50})

    def test_calculate_points_iterated_domination(self):
        battle = Iterated(self.match, self.problem, rounds=2)
        battle.pairs[("0", "1")][0].solved = 10
        battle.pairs[("0", "1")][1].solved = 10
        battle.pairs[("1", "0")][0].solved = 0
        battle.pairs[("1", "0")][1].solved = 0
        self.assertEqual(battle.calculate_points(100), {'0': 0, '1': 100})

    def test_calculate_points_averaged_zero_rounds(self):
        battle = Averaged(self.match, self.problem, rounds=0)
        self.assertEqual(battle.calculate_points(100), {})

    def test_calculate_points_averaged_draw(self):
        battle = Averaged(self.match, self.problem, rounds=2)
        battle.pairs[("0", "1")][0].approx_ratios = [1.5, 1.5, 1.5]
        battle.pairs[("0", "1")][1].approx_ratios = [1.5, 1.5, 1.5]
        battle.pairs[("1", "0")][0].approx_ratios = [1.5, 1.5, 1.5]
        battle.pairs[("1", "0")][1].approx_ratios = [1.5, 1.5, 1.5]
        self.assertEqual(battle.calculate_points(100), {'0': 50, '1': 50})

    def test_calculate_points_averaged_domination(self):
        battle = Averaged(self.match, self.problem, rounds=2)
        battle.pairs[("0", "1")][0].approx_ratios = [1.5, 1.5, 1.5]
        battle.pairs[("0", "1")][1].approx_ratios = [1.5, 1.5, 1.5]
        battle.pairs[("1", "0")][0].approx_ratios = [1.0, 1.0, 1.0]
        battle.pairs[("1", "0")][1].approx_ratios = [1.0, 1.0, 1.0]
        self.assertEqual(battle.calculate_points(100), {'0': 60, '1': 40})

    def test_calculate_points_averaged_no_successful_round(self):
        battle = Averaged(self.match, self.problem, rounds=2)
        battle.pairs[("0", "1")][0].approx_ratios = [0, 0, 0]
        battle.pairs[("0", "1")][1].approx_ratios = [0, 0, 0]
        battle.pairs[("1", "0")][0].approx_ratios = [0, 0, 0]
        battle.pairs[("1", "0")][1].approx_ratios = [0, 0, 0]
        self.assertEqual(battle.calculate_points(100), {'0': 50, '1': 50})

if __name__ == '__main__':
    unittest.main()
