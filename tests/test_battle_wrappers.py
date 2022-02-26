"""Tests for all util functions."""
from pathlib import Path
import unittest
import logging

import algobattle
from algobattle.battle_wrappers.averaged import Averaged
from algobattle.battle_wrappers.iterated import Iterated
from algobattle.matchups import BattleMatchups
from algobattle.team import Team

logging.disable(logging.CRITICAL)


class BattleWrapperTests(unittest.TestCase):
    """Tests for the battle wrapper functions."""

    @classmethod
    def setUpClass(cls) -> None:
        base_path = Path(algobattle.__file__).resolve().parent
        generator_path = base_path / "problems" / "testsproblem" / "generator"
        solver_path = base_path / "problems" / "testsproblem" / "solver"
        cls.teams = [Team("0", generator_path, solver_path), Team("1", generator_path, solver_path)]
        cls.matchups = BattleMatchups(cls.teams)

    def test_averaged_battle_wrapper(self):
        pass  # TODO: Implement tests for averaged battle wrapper

    def test_iterated_battle_wrapper(self):
        pass  # TODO: Implement tests for iterated battle wrapper

    def test_calculate_points_iterated_zero_rounds(self):
        self.assertEqual(Iterated.MatchResult(self.matchups, rounds=0).calculate_points(100), {})

    def test_calculate_points_iterated_no_successful_round(self):
        results = Iterated.MatchResult(self.matchups)
        for m in self.matchups:
            results[m] = [Iterated.Result(solved=0), Iterated.Result(solved=0)]
        self.assertEqual(results.calculate_points(100), {self.teams[0]: 50, self.teams[1]: 50})

    def test_calculate_points_iterated_draw(self):
        results = Iterated.MatchResult(self.matchups)
        results[self.matchups[0]] = [Iterated.Result(solved=20), Iterated.Result(solved=10)]
        results[self.matchups[1]] = [Iterated.Result(solved=10), Iterated.Result(solved=20)]
        self.assertEqual(results.calculate_points(100), {self.teams[0]: 50, self.teams[1]: 50})

    def test_calculate_points_iterated_domination(self):
        results = Iterated.MatchResult(self.matchups)
        results[self.matchups[0]] = [Iterated.Result(solved=10), Iterated.Result(solved=10)]
        results[self.matchups[1]] = [Iterated.Result(solved=0), Iterated.Result(solved=0)]
        self.assertEqual(results.calculate_points(100), {self.teams[0]: 0, self.teams[1]: 100})

    def test_calculate_points_averaged_zero_rounds(self):
        self.assertEqual(Averaged.MatchResult(self.matchups, rounds=0).calculate_points(100), {})

    def test_calculate_points_averaged_draw(self):
        results = Averaged.MatchResult(self.matchups)
        results[self.matchups[0]] = [Averaged.Result([1.5, 1.5, 1.5]), Averaged.Result([1.5, 1.5, 1.5])]
        results[self.matchups[1]] = [Averaged.Result([1.5, 1.5, 1.5]), Averaged.Result([1.5, 1.5, 1.5])]
        self.assertEqual(results.calculate_points(100), {self.teams[0]: 50, self.teams[1]: 50})

    def test_calculate_points_averaged_domination(self):
        results = Averaged.MatchResult(self.matchups)
        results[self.matchups[0]] = [Averaged.Result([1.5, 1.5, 1.5]), Averaged.Result([1.5, 1.5, 1.5])]
        results[self.matchups[1]] = [Averaged.Result([1.0, 1.0, 1.0]), Averaged.Result([1.0, 1.0, 1.0])]
        self.assertEqual(results.calculate_points(100), {self.teams[0]: 60, self.teams[1]: 40})

    def test_calculate_points_averaged_no_successful_round(self):
        results = Averaged.MatchResult(self.matchups)
        results[self.matchups[0]] = [Averaged.Result([0, 0, 0]), Averaged.Result([0, 0, 0])]
        results[self.matchups[1]] = [Averaged.Result([0, 0, 0]), Averaged.Result([0, 0, 0])]
        self.assertEqual(results.calculate_points(100), {self.teams[0]: 50, self.teams[1]: 50})

if __name__ == '__main__':
    unittest.main()
