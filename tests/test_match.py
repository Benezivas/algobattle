"""Tests for the Match class."""
from typing import Callable
import unittest
import logging
import importlib
import os
import subprocess

import algobattle
from algobattle.match import BuildError, Match, UnknownBattleType
from algobattle.team import Team

logging.disable(logging.CRITICAL)


class Matchtests(unittest.TestCase):
    """Tests for the match object."""

    @classmethod
    def setUpClass(cls) -> None:
        Problem = importlib.import_module('algobattle.problems.testsproblem')
        cls.problem = Problem.Problem()
        problem_file = Problem.__file__
        assert problem_file is not None
        cls.tests_path = problem_file[:-12]  # remove /__init__.py

        cls.config_directory = os.path.join(os.path.dirname(os.path.abspath(algobattle.__file__)), 'config')
        cls.config = os.path.join(cls.config_directory, 'config.ini')
        cls.config_short_build_timeout = os.path.join(cls.config_directory, 'config_short_build_timeout.ini')
        cls.config_short_timeout = os.path.join(cls.config_directory, 'config_short_run_timeout.ini')

        cls.team = Team('0', cls.tests_path + '/generator', cls.tests_path + '/solver')
    
    def tearDown(self) -> None:
        images = " ".join(f"generator-{name} solver-{name}" for name in ["0", "1"])
        subprocess.Popen(f"docker image rm -f {images}")

    def assertBuild(self, build: Callable):
        try:
            build()
        except BuildError:
            self.fail("Docker build did not finish successfully.")

    def test_build_normal(self):
        # A normal build
        self.assertBuild(lambda: Match(self.problem, self.config, [self.team]))

    def test_build_malformed_docker(self):
        # Malformed docker names
        match_malformed_docker_names = Match(self.problem, self.config, [self.team], cache_docker_containers=False)
        self.assertRaises(TypeError, lambda: match_malformed_docker_names._build((1, 0)))

    def test_build_timeout(self):
        # Build timeout
        team = Team('0', self.tests_path + '/generator_build_timeout', self.tests_path + '/solver')
        self.assertRaises(BuildError, lambda: Match(self.problem, self.config_short_build_timeout, [team], cache_docker_containers=False))

    def test_build_error(self):
        # Build error
        team = Team('0', self.tests_path + '/generator_build_error', self.tests_path + '/solver')
        self.assertRaises(BuildError, lambda: Match(self.problem, self.config_short_build_timeout, [team], cache_docker_containers=False))

    def test_all_battle_pairs(self):
        team0 = Team('0', self.tests_path + '/generator', self.tests_path + '/solver')
        team1 = Team('1', self.tests_path + '/generator', self.tests_path + '/solver')
        teams = [team0, team1]
        match = Match(self.problem, self.config, teams)
        self.assertEqual(match.all_battle_pairs(), [('0', '1'), ('1', '0')])

        match = Match(self.problem, self.config, [team0])
        self.assertEqual(match.all_battle_pairs(), [('0', '0')])

    def test_run(self):
        match = Match(self.problem, self.config, [self.team])
        self.assertRaises(UnknownBattleType, lambda: match.run(battle_type='foo'))

    def test_one_fight_gen_timeout(self):
        team = Team('0', self.tests_path + '/generator_timeout', self.tests_path + '/solver')
        match_run_timeout = Match(self.problem, self.config_short_timeout, [team], cache_docker_containers=False)
        match_run_timeout.generating_team = team
        match_run_timeout.solving_team = team
        self.assertEqual(match_run_timeout._one_fight(1), 1.0)

    def test_one_fight_gen_exec_error(self):
        team = Team('0', self.tests_path + '/generator_execution_error', self.tests_path + '/solver')
        match_broken_generator = Match(self.problem, self.config, [team], cache_docker_containers=False)
        match_broken_generator.generating_team = team
        match_broken_generator.solving_team = team
        self.assertEqual(match_broken_generator._one_fight(1), 1.0)

    def test_one_fight_gen_wrong_instance(self):
        team = Team('0', self.tests_path + '/generator_wrong_instance', self.tests_path + '/solver')
        match_wrong_generator_instance = Match(self.problem, self.config, [team], cache_docker_containers=False)
        match_wrong_generator_instance.generating_team = team
        match_wrong_generator_instance.solving_team = team
        self.assertEqual(match_wrong_generator_instance._one_fight(1), 1.0)

    def test_one_fight_gen_malformed_sol(self):
        team = Team('0', self.tests_path + '/generator_malformed_solution', self.tests_path + '/solver')
        match_malformed_generator_solution = Match(self.problem, self.config, [team], cache_docker_containers=False)
        match_malformed_generator_solution.generating_team = team
        match_malformed_generator_solution.solving_team = team
        self.assertEqual(match_malformed_generator_solution._one_fight(1), 1.0)

    def test_one_fight_gen_wrong_cert(self):
        team = Team('0', self.tests_path + '/generator_wrong_certificate', self.tests_path + '/solver')
        match_wrong_generator_certificate = Match(self.problem, self.config, [team], cache_docker_containers=False)
        match_wrong_generator_certificate.generating_team = team
        match_wrong_generator_certificate.solving_team = team
        self.assertEqual(match_wrong_generator_certificate._one_fight(1), 1.0)

    def test_one_fight_sol_timeout(self):
        team = Team('0', self.tests_path + '/generator', self.tests_path + '/solver_timeout')
        match_solver_timeout = Match(self.problem, self.config_short_timeout, [team], cache_docker_containers=False)
        match_solver_timeout.generating_team = team
        match_solver_timeout.solving_team = team
        self.assertEqual(match_solver_timeout._one_fight(1), 0.0)

    def test_one_fight_sol_exec_error(self):
        team = Team('0', self.tests_path + '/generator', self.tests_path + '/solver_execution_error')
        match_broken_solver = Match(self.problem, self.config, [team], cache_docker_containers=False)
        match_broken_solver.generating_team = team
        match_broken_solver.solving_team = team
        self.assertEqual(match_broken_solver._one_fight(1), 0.0)

    def test_one_fight_sol_malformed(self):
        team = Team('0', self.tests_path + '/generator', self.tests_path + '/solver_malformed_solution')
        match_malformed_solution = Match(self.problem, self.config, [team], cache_docker_containers=False)
        match_malformed_solution.generating_team = team
        match_malformed_solution.solving_team = team
        self.assertEqual(match_malformed_solution._one_fight(1), 0.0)

    def test_one_fight_sol_wrong_cert(self):
        team = Team('0', self.tests_path + '/generator', self.tests_path + '/solver_wrong_certificate')
        match_wrong_certificate = Match(self.problem, self.config, [team], cache_docker_containers=False)
        match_wrong_certificate.generating_team = team
        match_wrong_certificate.solving_team = team
        self.assertEqual(match_wrong_certificate._one_fight(1), 0.0)

    def test_one_fight_successful(self):
        successful_match = Match(self.problem, self.config, [self.team], cache_docker_containers=False)
        successful_match.generating_team = self.team
        successful_match.solving_team = self.team
        self.assertEqual(successful_match._one_fight(1), 1.0)


if __name__ == '__main__':
    unittest.main()
