"""Tests for the Match class."""
from __future__ import annotations
from pathlib import Path
from typing import Callable, cast
import unittest
import logging

import algobattle
from algobattle.battle_wrappers.iterated import Iterated
from algobattle.match import BuildError, Match, UnknownBattleType
from algobattle.matchups import Matchup
import algobattle.problems.testsproblem as Problem

logging.disable(logging.CRITICAL)


class Matchtests(unittest.TestCase):
    """Tests for the match object."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.problem = Problem.Problem()
        problem_file = Problem.__file__
        assert problem_file is not None
        cls.tests_path = Path(problem_file).parent

        cls.config_directory = Path(algobattle.__file__).resolve().parent / 'config'
        cls.config = cls.config_directory / 'config.ini'
        cls.config_short_build_timeout = cls.config_directory / 'config_short_build_timeout.ini'
        cls.config_short_timeout = cls.config_directory / 'config_short_run_timeout.ini'

        cls.team = ('0', cls.tests_path / 'generator', cls.tests_path / 'solver')
        cls.match: Match | None = None
        cls.wrapper = Iterated(cls.problem)
    
    def tearDown(self) -> None:
        if self.match is not None:
            self.match.cleanup()

    def assertBuild(self, build: Callable):
        try:
            build()
        except BuildError:
            self.fail("Docker build did not finish successfully.")

    def test_build_normal(self):
        # A normal build
        def build_match():
            self.match = Match(self.problem, self.config, [self.team])
        self.assertBuild(build_match)

    def test_build_timeout(self):
        # Build timeout
        team = ('0', self.tests_path / 'generator_build_timeout', self.tests_path / 'solver')
        def build_match():
            self.match = Match(self.problem, self.config_short_build_timeout, [team], cache_docker_containers=False)
        self.assertRaises(BuildError, build_match)

    def test_build_error(self):
        # Build error
        team = ('0', self.tests_path / 'generator_build_error', self.tests_path / 'solver')
        def build_match():
            self.match = Match(self.problem, self.config_short_build_timeout, [team], cache_docker_containers=False)
        self.assertRaises(BuildError, build_match)

    def test_run(self):
        self.match = Match(self.problem, self.config, [self.team])
        self.assertRaises(UnknownBattleType, lambda: cast(Match, self.match).run(battle_type='foo'))

    def test_one_fight_gen_timeout(self):
        team = ('0', self.tests_path / 'generator_timeout', self.tests_path / 'solver')
        self.match = Match(self.problem, self.config_short_timeout, [team], cache_docker_containers=False)
        matchup = Matchup(self.match.teams[0], self.match.teams[0])
        self.assertEqual(self.wrapper._one_fight(matchup, 1), 1.0)

    def test_one_fight_gen_exec_error(self):
        team = ('0', self.tests_path / 'generator_execution_error', self.tests_path / 'solver')
        self.match = Match(self.problem, self.config, [team], cache_docker_containers=False)
        matchup = Matchup(self.match.teams[0], self.match.teams[0])
        self.assertEqual(self.wrapper._one_fight(matchup, 1), 1.0)

    def test_one_fight_gen_wrong_instance(self):
        team = ('0', self.tests_path / 'generator_wrong_instance', self.tests_path / 'solver')
        self.match = Match(self.problem, self.config, [team], cache_docker_containers=False)
        matchup = Matchup(self.match.teams[0], self.match.teams[0])
        self.assertEqual(self.wrapper._one_fight(matchup, 1), 1.0)

    def test_one_fight_gen_malformed_sol(self):
        team = ('0', self.tests_path / 'generator_malformed_solution', self.tests_path / 'solver')
        self.match = Match(self.problem, self.config, [team], cache_docker_containers=False)
        matchup = Matchup(self.match.teams[0], self.match.teams[0])
        self.assertEqual(self.wrapper._one_fight(matchup, 1), 1.0)

    def test_one_fight_gen_wrong_cert(self):
        team = ('0', self.tests_path / 'generator_wrong_certificate', self.tests_path / 'solver')
        self.match = Match(self.problem, self.config, [team], cache_docker_containers=False)
        matchup = Matchup(self.match.teams[0], self.match.teams[0])
        self.assertEqual(self.wrapper._one_fight(matchup, 1), 1.0)

    def test_one_fight_sol_timeout(self):
        team = ('0', self.tests_path / 'generator', self.tests_path / 'solver_timeout')
        self.match = Match(self.problem, self.config_short_timeout, [team], cache_docker_containers=False)
        matchup = Matchup(self.match.teams[0], self.match.teams[0])
        self.assertEqual(self.wrapper._one_fight(matchup, 1), 0.0)

    def test_one_fight_sol_exec_error(self):
        team = ('0', self.tests_path / 'generator', self.tests_path / 'solver_execution_error')
        self.match = Match(self.problem, self.config, [team], cache_docker_containers=False)
        matchup = Matchup(self.match.teams[0], self.match.teams[0])
        self.assertEqual(self.wrapper._one_fight(matchup, 1), 0.0)

    def test_one_fight_sol_malformed(self):
        team = ('0', self.tests_path / 'generator', self.tests_path / 'solver_malformed_solution')
        self.match = Match(self.problem, self.config, [team], cache_docker_containers=False)
        matchup = Matchup(self.match.teams[0], self.match.teams[0])
        self.assertEqual(self.wrapper._one_fight(matchup, 1), 0.0)

    def test_one_fight_sol_wrong_cert(self):
        team = ('0', self.tests_path / 'generator', self.tests_path / 'solver_wrong_certificate')
        self.match = Match(self.problem, self.config, [team], cache_docker_containers=False)
        matchup = Matchup(self.match.teams[0], self.match.teams[0])
        self.assertEqual(self.wrapper._one_fight(matchup, 1), 0.0)

    def test_one_fight_successful(self):
        self.match = Match(self.problem, self.config, [self.team], cache_docker_containers=False)
        matchup = Matchup(self.match.teams[0], self.match.teams[0])
        self.assertEqual(self.wrapper._one_fight(matchup, 1), 1.0)


if __name__ == '__main__':
    unittest.main()
