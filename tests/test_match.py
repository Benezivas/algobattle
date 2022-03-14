"""Tests for the Match class."""
from configparser import ConfigParser
import unittest
import logging
import importlib
import os

import algobattle
from algobattle.battle_wrappers.iterated import Iterated
from algobattle.fight_handler import FightHandler
from algobattle.match import Match
from algobattle.team import Team
import algobattle.util as util

logging.disable(logging.CRITICAL)


class Matchtests(unittest.TestCase):
    """Tests for the match object."""

    def setUp(self) -> None:
        """Set up a match object."""
        Problem = importlib.import_module('algobattle.problems.testsproblem')
        self.problem = Problem.Problem()
        self.problem_path = Problem.__file__[:-12]  # remove /__init__.py

        util.build_docker_container(os.path.join(self.problem_path, 'generator'),
                                    docker_tag='gen',
                                    cache_docker_container=False)
        util.build_docker_container(os.path.join(self.problem_path, 'solver'),
                                    docker_tag='sol',
                                    cache_docker_container=False)
        self.team0 = Team('0', 'gen', 'sol')
        self.team1 = Team('1', 'gen', 'sol')

        config_path = os.path.join(os.path.dirname(os.path.abspath(algobattle.__file__)), 'config', 'config.ini')
        self.config = ConfigParser()
        self.config.read(config_path)

        self.fight_handler = FightHandler(self.problem, self.config)

        self.wrapper_iter = Iterated(self.config)
        self.match = Match(self.fight_handler, self.wrapper_iter, [self.team0, self.team1])

    def test_all_battle_pairs_two_teams(self):
        """Two teams both generate and solve one time each."""
        self.assertEqual(self.match.all_battle_pairs(), [('0', '1'), ('1', '0')])

    def test_all_battle_pairs_single_player(self):
        """A team playing against itself is the only battle pair in single player."""
        match = Match(self.fight_handler, self.wrapper_iter, [self.team0])
        self.assertEqual(match.all_battle_pairs(), [('0', '0')])

    # TODO: Add tests for remaining functions


if __name__ == '__main__':
    unittest.main()
