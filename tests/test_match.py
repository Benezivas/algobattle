"""Tests for the Match class."""
from typing import cast
import unittest
import logging
import importlib

from configparser import ConfigParser
from pathlib import Path

import algobattle
from algobattle.battle_wrappers.iterated import Iterated
from algobattle.battle_wrappers.averaged import Averaged
from algobattle.docker_wrapper import Image
from algobattle.fight_handler import FightHandler
from algobattle.match import Match
from algobattle.team import Team

logging.disable(logging.CRITICAL)


class Matchtests(unittest.TestCase):
    """Tests for the match object."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up a match object."""
        Problem = importlib.import_module('algobattle.problems.testsproblem')
        cls.problem = Problem.Problem()
        cls.problem_path = Path(cast(str, Problem.__file__)).parent

        cls.generator = Image(cls.problem_path / "generator", "generator")
        cls.solver = Image(cls.problem_path / "solver", "solver")
        cls.team0 = Team('0', cls.generator, cls.solver)
        cls.team1 = Team('1', cls.generator, cls.solver)

        config_path = Path(Path(algobattle.__file__).parent, 'config', 'config.ini')
        cls.config = ConfigParser()
        cls.config.read(config_path)

        cls.fight_handler = FightHandler(cls.problem, cls.config)

        cls.wrapper_iter = Iterated(cls.config)
        cls.wrapper_avg = Averaged(cls.config)
        cls.match_iter = Match(cls.fight_handler, cls.wrapper_iter, [cls.team0, cls.team1])
        cls.match_avg = Match(cls.fight_handler, cls.wrapper_avg, [cls.team0, cls.team1])

    @classmethod
    def tearDownClass(cls) -> None:
        cls.generator.remove()
        cls.solver.remove()

    def test_all_battle_pairs_two_teams(self):
        """Two teams both generate and solve one time each."""
        self.assertEqual(self.match_iter.all_battle_pairs(), [('0', '1'), ('1', '0')])

    def test_all_battle_pairs_single_player(self):
        """A team playing against itself is the only battle pair in single player."""
        match = Match(self.fight_handler, self.wrapper_iter, [self.team0])
        self.assertEqual(match.all_battle_pairs(), [('0', '0')])

    def test_calculate_points_zero_rounds(self):
        """An empty dict is be returned if no rounds have been fought."""
        self.match_iter.rounds = 0
        self.assertEqual(self.match_iter.calculate_points(100), {})

    def test_calculate_points_iterated_no_successful_round(self):
        """Two teams should get an equal amount of points if nobody solved anything."""
        self.match_iter.rounds = 2
        self.match_iter.match_data = {'rounds': 2,
                                      'type': 'iterated',
                                      ('0', '1'): {0: {'solved': 0}, 1: {'solved': 0}},
                                      ('1', '0'): {0: {'solved': 0}, 1: {'solved': 0}}}
        self.assertEqual(self.match_iter.calculate_points(100), {'0': 50, '1': 50})

    def test_calculate_points_iterated_draw(self):
        """Two teams should get an equal amount of points if both solved a problem equally well."""
        self.match_iter.rounds = 2
        self.match_iter.match_data = {'rounds': 2,
                                      'type': 'iterated',
                                      ('0', '1'): {0: {'solved': 20}, 1: {'solved': 10}},
                                      ('1', '0'): {0: {'solved': 10}, 1: {'solved': 20}}}
        self.assertEqual(self.match_iter.calculate_points(100), {'0': 50, '1': 50})

    def test_calculate_points_iterated_domination(self):
        """One team should get all points if it solved anything and the other team nothing."""
        self.match_iter.rounds = 2
        self.match_iter.match_data = {'rounds': 2,
                                      'type': 'iterated',
                                      ('0', '1'): {0: {'solved': 10}, 1: {'solved': 10}},
                                      ('1', '0'): {0: {'solved': 0}, 1: {'solved': 0}}}
        self.assertEqual(self.match_iter.calculate_points(100), {'0': 0, '1': 100})

    def test_calculate_points_iterated_one_team_better(self):
        """One team should get more points than the other if it performed better."""
        self.match_iter.rounds = 2
        self.match_iter.match_data = {'rounds': 2,
                                      'type': 'iterated',
                                      ('0', '1'): {0: {'solved': 10}, 1: {'solved': 10}},
                                      ('1', '0'): {0: {'solved': 20}, 1: {'solved': 20}}}
        self.assertEqual(self.match_iter.calculate_points(100), {'0': 66.6, '1': 33.4})

    def test_calculate_points_averaged_no_successful_round(self):
        """Two teams should get an equal amount of points if nobody solved anything."""
        self.match_avg.rounds = 2
        self.match_avg.match_data = {'rounds': 2,
                                     'type': 'averaged',
                                     ('0', '1'): {0: {'approx_ratios': [0, 0, 0]},
                                                  1: {'approx_ratios': [0, 0, 0]}},
                                     ('1', '0'): {0: {'approx_ratios': [0, 0, 0]},
                                                  1: {'approx_ratios': [0, 0, 0]}}}
        self.assertEqual(self.match_avg.calculate_points(100), {'0': 50, '1': 50})

    def test_calculate_points_averaged_draw(self):
        """Two teams should get an equal amount of points if both solved a problem equally well."""
        self.match_avg.rounds = 2
        self.match_avg.match_data = {'type': 'averaged',
                                     ('0', '1'): {0: {'approx_ratios': [1.5, 1.5, 1.5]},
                                                  1: {'approx_ratios': [1.5, 1.5, 1.5]}},
                                     ('1', '0'): {0: {'approx_ratios': [1.5, 1.5, 1.5]},
                                                  1: {'approx_ratios': [1.5, 1.5, 1.5]}}}
        self.assertEqual(self.match_avg.calculate_points(100), {'0': 50, '1': 50})

    def test_calculate_points_averaged_domination(self):
        """One team should get all points if it solved anything and the other team nothing."""
        self.match_avg.rounds = 2
        self.match_avg.match_data = {'type': 'averaged',
                                     ('0', '1'): {0: {'approx_ratios': [0, 0, 0]},
                                                  1: {'approx_ratios': [0, 0, 0]}},
                                     ('1', '0'): {0: {'approx_ratios': [1.0, 1.0, 1.0]},
                                                  1: {'approx_ratios': [1.0, 1.0, 1.0]}}}
        self.assertEqual(self.match_avg.calculate_points(100), {'0': 100, '1': 0})

    def test_calculate_points_averaged_one_team_better(self):
        """One team should get more points than the other if it performed better."""
        self.match_avg.rounds = 2
        self.match_avg.match_data = {'type': 'averaged',
                                     ('0', '1'): {0: {'approx_ratios': [1.5, 1.5, 1.5]},
                                                  1: {'approx_ratios': [1.5, 1.5, 1.5]}},
                                     ('1', '0'): {0: {'approx_ratios': [1.0, 1.0, 1.0]},
                                                  1: {'approx_ratios': [1.0, 1.0, 1.0]}}}
        self.assertEqual(self.match_avg.calculate_points(100), {'0': 60, '1': 40})

    # TODO: Add tests for remaining functions


if __name__ == '__main__':
    unittest.main()
