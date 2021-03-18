""" Tests for the Match class.
"""
import unittest
import logging
import importlib
import configparser
import pkgutil
import os

import algobattle
from algobattle.match import Match
from algobattle.team import Team

logging.disable(logging.CRITICAL)

class Matchtests(unittest.TestCase):
    def setUp(self) -> None:
        Problem = importlib.import_module('algobattle.problems.testsproblem')
        self.problem = Problem.Problem()
        self.tests_path = Problem.__file__[:-12] #remove /__init__.py

        self.config_directory = os.path.join(os.path.dirname(os.path.abspath(algobattle.__file__)), 'config')
        self.config = os.path.join(self.config_directory, 'config.ini')

        self.team = Team(0, self.tests_path + '/generator', self.tests_path + '/solver')

        self.match = Match(self.problem, self.config, [self.team])

    def test_build(self):
        self.assertTrue(self.match.build_successful)

        match_malformed_docker_names = Match(self.problem, self.config, self.team, testing=True)
        self.assertFalse(match_malformed_docker_names._build((1,0)))

        config_short_build_timeout = os.path.join(self.config_directory, 'config_short_build_timeout.ini')
        team = Team(0, self.tests_path + '/generator_build_timeout', self.tests_path + '/solver')
        match_build_timeout = Match(self.problem, config_short_build_timeout, [team], testing=True)
        self.assertFalse(match_build_timeout.build_successful)

        team = Team(0, self.tests_path + '/generator_build_error', self.tests_path + '/solver')
        match_build_fail = Match(self.problem, config_short_build_timeout, [team], testing=True)
        self.assertFalse(match_build_fail.build_successful)

        match = Match(self.problem, self.config, 'foo')
        self.assertFalse(match.build_successful)

        team = Team('a', self.tests_path + '/generator', self.tests_path + '/solver')
        match = Match(self.problem, self.config, [team])
        self.assertFalse(match.build_successful)

        team = Team(0.1, self.tests_path + '/generator', self.tests_path + '/solver')
        match = Match(self.problem, self.config, [team])
        self.assertFalse(match.build_successful)

        team = Team(0.1, self.tests_path + '/generator', self.tests_path + '/solver')
        match = Match(self.problem, self.config, [team])
        self.assertFalse(match.build_successful)

    def test_all_battle_pairs(self):
        team0 = Team(0, self.tests_path + '/generator', self.tests_path + '/solver')
        team1 = Team(1, self.tests_path + '/generator', self.tests_path + '/solver')
        teams = [team0, team1]
        match = Match(self.problem, self.config, teams)
        self.assertEqual(match.all_battle_pairs(), [(0,1), (1,0)])
        
        match = Match(self.problem, self.config, [team0])
        self.assertEqual(match.all_battle_pairs(), [(0,0)])

    def test_run(self):
        self.assertEqual(self.match.run(battle_type='foo'), ([]))

    def test_averaged_battle_wrapper(self):
        pass

    def test_iterated_battle_wrapper(self):
        pass

    def test_one_fight(self):
        config_short_timeout = os.path.join(self.config_directory, 'config_short_run_timeout.ini')
        team = Team(0, self.tests_path + '/generator_timeout', self.tests_path + '/solver')
        match_run_timeout = Match(self.problem, config_short_timeout, [team])
        match_run_timeout.generating_team = 0
        match_run_timeout.solving_team = 0
        self.assertEqual(match_run_timeout._one_fight(1), 1.0)

        team = Team(0, self.tests_path + '/generator_execution_error', self.tests_path + '/solver')
        match_broken_generator = Match(self.problem, self.config, [team], testing=True)
        match_broken_generator.generating_team = 0
        match_broken_generator.solving_team = 0
        self.assertEqual(match_broken_generator._one_fight(1), 1.0)

        team = Team(0, self.tests_path + '/generator_wrong_instance', self.tests_path + '/solver')
        match_wrong_generator_instance = Match(self.problem, self.config, [team])
        match_wrong_generator_instance.generating_team = 0
        match_wrong_generator_instance.solving_team = 0
        self.assertEqual(match_wrong_generator_instance._one_fight(1), 1.0)

        team = Team(0, self.tests_path + '/generator_malformed_solution', self.tests_path + '/solver')
        match_malformed_generator_solution = Match(self.problem, self.config, [team])
        match_malformed_generator_solution.generating_team = 0
        match_malformed_generator_solution.solving_team = 0
        self.assertEqual(match_malformed_generator_solution._one_fight(1), 1.0)

        team = Team(0, self.tests_path + '/generator_wrong_certificate', self.tests_path + '/solver')
        match_wrong_generator_certificate = Match(self.problem, self.config, [team])
        match_wrong_generator_certificate.generating_team = 0
        match_wrong_generator_certificate.solving_team = 0
        self.assertEqual(match_wrong_generator_certificate._one_fight(1), 1.0)

        team = Team(0, self.tests_path + '/generator', self.tests_path + '/solver_timeout')
        match_solver_timeout = Match(self.problem, config_short_timeout, [team])
        match_solver_timeout.generating_team = 0
        match_solver_timeout.solving_team = 0
        self.assertEqual(match_solver_timeout._one_fight(1), 0.0)

        team = Team(0, self.tests_path + '/generator', self.tests_path + '/solver_execution_error')
        match_broken_solver = Match(self.problem, self.config, [team], testing=True)
        match_broken_solver.generating_team = 0
        match_broken_solver.solving_team = 0
        self.assertEqual(match_broken_solver._one_fight(1), 0.0)

        team = Team(0, self.tests_path + '/generator', self.tests_path + '/solver_malformed_solution')
        match_malformed_solution = Match(self.problem, self.config, [team])
        match_malformed_solution.generating_team = 0
        match_malformed_solution.solving_team = 0
        self.assertEqual(match_malformed_solution._one_fight(1), 0.0)

        team = Team(0, self.tests_path + '/generator', self.tests_path + '/solver_wrong_certificate')
        match_wrong_certificate = Match(self.problem, self.config, [team])
        match_wrong_certificate.generating_team = 0
        match_wrong_certificate.solving_team = 0
        self.assertEqual(match_wrong_certificate._one_fight(1), 0.0)

        successful_match = Match(self.problem, self.config, [self.team])
        successful_match.generating_team = 0
        successful_match.solving_team = 0
        self.assertEqual(successful_match._one_fight(1), 1.0)

    def test_run_subprocess(self):
        team = Team(0, self.tests_path + '/generator_timeout', self.tests_path + '/solver')
        match_run_timeout = Match(self.problem, self.config, [team])
        raw_output, elapsed_time = match_run_timeout._run_subprocess(match_run_timeout.base_build_command + ['generator0'], 0, 2)
        self.assertGreater(elapsed_time, 1.99)
        self.assertEqual(raw_output, None)

if __name__ == '__main__':
    unittest.main()