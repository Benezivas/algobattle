"""Tests for the Match class."""
from __future__ import annotations
from configparser import ConfigParser
from pathlib import Path
from typing import Callable, cast
import unittest
import logging

import algobattle
from algobattle.battle_wrappers.iterated import Iterated
from algobattle.match import BuildError, Match, RunParameters
from algobattle.team import Matchup, Team
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

        config_directory = Path(algobattle.__file__).resolve().parent / 'config'
        cls.config = ConfigParser()
        cls.config.read(config_directory / "config.ini")
        cls.config_short_build_timeout = ConfigParser()
        cls.config_short_build_timeout.read(config_directory / 'config_short_build_timeout.ini')
        cls.config_short_timeout = ConfigParser()
        cls.config_short_timeout.read(config_directory / 'config_short_run_timeout.ini')

        cls.team = ('0', cls.tests_path / 'generator', cls.tests_path / 'solver')
        cls.wrapper_normal = Iterated(cls.problem, RunParameters(cls.config["run_parameters"]))
        cls.wrapper_build_timeout = Iterated(cls.problem, RunParameters(cls.config_short_build_timeout["run_parameters"]))
        cls.wrapper_run_timeout = Iterated(cls.problem, RunParameters(cls.config_short_timeout["run_parameters"]))

        cls.match = None

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
        self.assertRaises(ValueError, lambda: cast(Match, self.match).run(battle_type='foo'))


class WrapperTests(unittest.TestCase):
    """Tests for the BattleWrapper object."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.problem = Problem.Problem()
        problem_file = Problem.__file__
        assert problem_file is not None
        cls.tests_path = Path(problem_file).parent

        config_directory = Path(algobattle.__file__).resolve().parent / 'config'
        cls.config = ConfigParser()
        cls.config.read(config_directory / "config.ini")
        cls.config_short_build_timeout = ConfigParser()
        cls.config_short_build_timeout.read(config_directory / 'config_short_build_timeout.ini')
        cls.config_short_timeout = ConfigParser()
        cls.config_short_timeout.read(config_directory / 'config_short_run_timeout.ini')

        cls.wrapper_normal = Iterated(cls.problem, RunParameters(cls.config["run_parameters"]))
        cls.wrapper_build_timeout = Iterated(cls.problem, RunParameters(cls.config_short_build_timeout["run_parameters"]))
        cls.wrapper_run_timeout = Iterated(cls.problem, RunParameters(cls.config_short_timeout["run_parameters"]))
        cls.team: Team | None = None

    def tearDown(self) -> None:
        if self.team is not None:
            self.team.cleanup()

    def test_one_fight_gen_timeout(self):
        self.team = Team('0', self.tests_path / 'generator_timeout', self.tests_path / 'solver', cache_container=False)
        matchup = Matchup(self.team, self.team)
        self.assertEqual(self.wrapper_run_timeout._one_fight(matchup, 1), self.problem.approx_cap)

    def test_one_fight_gen_exec_error(self):
        self.team = Team('0', self.tests_path / 'generator_execution_error', self.tests_path / 'solver', cache_container=False)
        matchup = Matchup(self.team, self.team)
        self.assertEqual(self.wrapper_normal._one_fight(matchup, 1), self.problem.approx_cap)

    def test_one_fight_gen_wrong_instance(self):
        self.team = Team('0', self.tests_path / 'generator_wrong_instance', self.tests_path / 'solver', cache_container=False)
        matchup = Matchup(self.team, self.team)
        self.assertEqual(self.wrapper_normal._one_fight(matchup, 1), self.problem.approx_cap)

    def test_one_fight_gen_malformed_sol(self):
        self.team = Team('0', self.tests_path / 'generator_malformed_solution',
                         self.tests_path / 'solver', cache_container=False)
        matchup = Matchup(self.team, self.team)
        self.assertEqual(self.wrapper_normal._one_fight(matchup, 1), self.problem.approx_cap)

    def test_one_fight_gen_wrong_cert(self):
        self.team = Team('0', self.tests_path / 'generator_wrong_certificate',
                         self.tests_path / 'solver', cache_container=False)
        matchup = Matchup(self.team, self.team)
        self.assertEqual(self.wrapper_normal._one_fight(matchup, 1), self.problem.approx_cap)

    def test_one_fight_sol_timeout(self):
        self.team = Team('0', self.tests_path / 'generator', self.tests_path / 'solver_timeout', cache_container=False)
        matchup = Matchup(self.team, self.team)
        self.assertEqual(self.wrapper_run_timeout._one_fight(matchup, 1), 0.0)

    def test_one_fight_sol_exec_error(self):
        self.team = Team('0', self.tests_path / 'generator',
                         self.tests_path / 'solver_execution_error', cache_container=False)
        matchup = Matchup(self.team, self.team)
        self.assertEqual(self.wrapper_run_timeout._one_fight(matchup, 1), 0.0)

    def test_one_fight_sol_malformed(self):
        self.team = Team('0', self.tests_path / 'generator',
                         self.tests_path / 'solver_malformed_solution', cache_container=False)
        matchup = Matchup(self.team, self.team)
        self.assertEqual(self.wrapper_run_timeout._one_fight(matchup, 1), 0.0)

    def test_one_fight_sol_wrong_cert(self):
        self.team = Team('0', self.tests_path / 'generator',
                         self.tests_path / 'solver_wrong_certificate', cache_container=False)
        matchup = Matchup(self.team, self.team)
        self.assertEqual(self.wrapper_run_timeout._one_fight(matchup, 1), 0.0)

    def test_one_fight_successful(self):
        self.team = Team('0', self.tests_path / 'generator', self.tests_path / 'solver', cache_container=False)
        matchup = Matchup(self.team, self.team)
        self.assertEqual(self.wrapper_normal._one_fight(matchup, 1), 1.0)


if __name__ == '__main__':
    unittest.main()
