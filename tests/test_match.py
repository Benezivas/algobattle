"""Tests for the Match class."""
from __future__ import annotations
from configparser import ConfigParser
from pathlib import Path
from typing import Callable
import unittest
import logging

import algobattle
from algobattle.fight import Fight
from algobattle.match import Match
from algobattle.team import Matchup, Team
from algobattle.docker import DockerConfig
import algobattle.problems.testsproblem as Problem

logging.disable(logging.CRITICAL)


def _parse_docker_config(path: Path) -> DockerConfig:
    config = ConfigParser()
    config.read(path)

    kwargs = {
        "cpus": config["docker_config"].getint("cpus", None),
        "timeout_build": config["docker_config"].getfloat("timeout_build", None),
        "cache_containers": config["docker_config"].getboolean("cache_containers", True),
    }
    for role in ("generator", "solver"):
        kwargs[f"timeout_{role}"] = config["docker_config"].getfloat(f"timeout_{role}", None)
        kwargs[f"space_{role}"] = config["docker_config"].getint(f"space_{role}", None)

    return DockerConfig(**kwargs)


class Matchtests(unittest.TestCase):
    """Tests for the match object."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.problem = Problem.Problem()
        problem_file = Problem.__file__
        assert problem_file is not None
        cls.tests_path = Path(problem_file).parent

        config_directory = Path(algobattle.__file__).resolve().parent / 'config'
        cls.config = _parse_docker_config(config_directory / "config.ini")
        cls.config.cache_containers = False
        cls.config_short_build_timeout = _parse_docker_config(config_directory / 'config_short_build_timeout.ini')

        cls.team = ('0', cls.tests_path / 'generator', cls.tests_path / 'solver')

        cls.match = None

    def tearDown(self) -> None:
        if self.match is not None:
            self.match.cleanup()

    def assertBuild(self, build: Callable):
        try:
            build()
        except RuntimeError:
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
            self.match = Match(self.problem, self.config_short_build_timeout, [team])
        self.assertRaises(SystemExit, build_match)

    def test_build_error(self):
        # Build error
        team = ('0', self.tests_path / 'generator_build_error', self.tests_path / 'solver')

        def build_match():
            self.match = Match(self.problem, self.config_short_build_timeout, [team])
        self.assertRaises(SystemExit, build_match)


class FightTests(unittest.TestCase):
    """Tests for the Battlestyle object."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.problem = Problem.Problem()
        problem_file = Problem.__file__
        assert problem_file is not None
        cls.tests_path = Path(problem_file).parent

        config_directory = Path(algobattle.__file__).resolve().parent / 'config'
        cls.config = _parse_docker_config(config_directory / "config.ini")
        cls.config.cache_containers = False
        cls.config_short_build_timeout = _parse_docker_config(config_directory / 'config_short_build_timeout.ini')
        cls.config_short_timeout = _parse_docker_config(config_directory / 'config_short_run_timeout.ini')

        cls.fight_normal = Fight(cls.problem, cls.config)
        cls.fight_build_timeout = Fight(cls.problem, cls.config_short_build_timeout)
        cls.fight_run_timeout = Fight(cls.problem, cls.config_short_timeout)
        cls.team: Team | None = None

    def tearDown(self) -> None:
        if self.team is not None:
            self.team.cleanup()

    def test_one_fight_gen_timeout(self):
        self.team = Team('0', self.tests_path / 'generator_timeout', self.tests_path / 'solver', cache_image=False)
        matchup = Matchup(self.team, self.team)
        self.assertEqual(self.fight_run_timeout(matchup, 1), self.problem.approx_cap)

    def test_one_fight_gen_exec_error(self):
        self.team = Team('0', self.tests_path / 'generator_execution_error', self.tests_path / 'solver', cache_image=False)
        matchup = Matchup(self.team, self.team)
        self.assertEqual(self.fight_normal(matchup, 1), self.problem.approx_cap)

    def test_one_fight_gen_wrong_instance(self):
        self.team = Team('0', self.tests_path / 'generator_wrong_instance', self.tests_path / 'solver', cache_image=False)
        matchup = Matchup(self.team, self.team)
        self.assertEqual(self.fight_normal(matchup, 1), self.problem.approx_cap)

    def test_one_fight_gen_malformed_sol(self):
        self.team = Team('0', self.tests_path / 'generator_malformed_solution',
                         self.tests_path / 'solver', cache_image=False)
        matchup = Matchup(self.team, self.team)
        self.assertEqual(self.fight_normal(matchup, 1), self.problem.approx_cap)

    def test_one_fight_gen_wrong_cert(self):
        self.team = Team('0', self.tests_path / 'generator_wrong_certificate',
                         self.tests_path / 'solver', cache_image=False)
        matchup = Matchup(self.team, self.team)
        self.assertEqual(self.fight_normal(matchup, 1), self.problem.approx_cap)

    def test_one_fight_sol_timeout(self):
        self.team = Team('0', self.tests_path / 'generator', self.tests_path / 'solver_timeout', cache_image=False)
        matchup = Matchup(self.team, self.team)
        self.assertEqual(self.fight_run_timeout(matchup, 1), 0.0)

    def test_one_fight_sol_exec_error(self):
        self.team = Team('0', self.tests_path / 'generator',
                         self.tests_path / 'solver_execution_error', cache_image=False)
        matchup = Matchup(self.team, self.team)
        self.assertEqual(self.fight_run_timeout(matchup, 1), 0.0)

    def test_one_fight_sol_malformed(self):
        self.team = Team('0', self.tests_path / 'generator',
                         self.tests_path / 'solver_malformed_solution', cache_image=False)
        matchup = Matchup(self.team, self.team)
        self.assertEqual(self.fight_run_timeout(matchup, 1), 0.0)

    def test_one_fight_sol_wrong_cert(self):
        self.team = Team('0', self.tests_path / 'generator',
                         self.tests_path / 'solver_wrong_certificate', cache_image=False)
        matchup = Matchup(self.team, self.team)
        self.assertEqual(self.fight_run_timeout(matchup, 1), 0.0)

    def test_one_fight_successful(self):
        self.team = Team('0', self.tests_path / 'generator', self.tests_path / 'solver', cache_image=False)
        matchup = Matchup(self.team, self.team)
        self.assertEqual(self.fight_normal(matchup, 1), 1.0)


if __name__ == '__main__':
    unittest.main()
