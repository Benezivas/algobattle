""" Tests for the Match class.
"""
import unittest
import logging
import importlib
import configparser
import pkgutil

from algobattle.match import Match

logging.disable(logging.CRITICAL)

class Matchtests(unittest.TestCase):
    def setUp(self) -> None:
        Problem = importlib.import_module('algobattle.problems.testsproblem')
        self.problem = Problem.Problem()
        self.tests_path = Problem.__file__[:-12] #remove /__init__.py

        self.config = configparser.ConfigParser()
        config_data = pkgutil.get_data('algobattle', 'config/config.ini').decode()
        self.config.read_string(config_data)

        self.match = Match(self.problem, self.config, 
          self.tests_path + '/generator', self.tests_path + '/generator',
          self.tests_path + '/solver', self.tests_path + '/solver', 0, 1)

    def test_build(self):
        self.assertTrue(self.match.build_successful)

        match_malformed_docker_names = Match(self.problem, self.config, 
          self.tests_path + '/generator', self.tests_path + '/generator',
          self.tests_path + '/solver', self.tests_path + '/solver', 0, 1, testing=True)
        self.assertFalse(match_malformed_docker_names._build('foo', 'foo', 'bar', 'bar', 0, 1))

        config_short_build_timeout = configparser.ConfigParser()
        config_data = pkgutil.get_data('algobattle', 'config/config_short_build_timeout.ini').decode()
        config_short_build_timeout.read_string(config_data)
        match_build_timeout = Match(self.problem, config_short_build_timeout, 
          self.tests_path + '/generator_build_timeout', self.tests_path + '/generator',
          self.tests_path + '/solver', self.tests_path + '/solver', 0, 1, testing=True)
        self.assertFalse(match_build_timeout.build_successful)

        match_build_fail = Match(self.problem, config_short_build_timeout, 
          self.tests_path + '/generator_build_error', self.tests_path + '/generator',
          self.tests_path + '/solver', self.tests_path + '/solver', 0, 1, testing=True)
        self.assertFalse(match_build_fail.build_successful)

        match = Match(self.problem, self.config, 
          self.tests_path + '/generator', self.tests_path + '/generator',
          self.tests_path + '/solver', self.tests_path + '/solver', 0, 'foo')
        self.assertFalse(match.build_successful)

        match = Match(self.problem, self.config, 
          self.tests_path + '/generator', self.tests_path + '/generator',
          self.tests_path + '/solver', self.tests_path + '/solver', 'foo', 1)
        self.assertFalse(match.build_successful)

        match = Match(self.problem, self.config, 
          self.tests_path + '/generator', self.tests_path + '/generator',
          self.tests_path + '/solver', self.tests_path + '/solver', 0.1, 1)
        self.assertFalse(match.build_successful)

        match = Match(self.problem, self.config, 
          self.tests_path + '/generator', self.tests_path + '/generator',
          self.tests_path + '/solver', self.tests_path + '/solver', 1, 0.1)
        self.assertFalse(match.build_successful)


    def test_run(self):
        self.assertEqual(self.match.run(battle_type='foo'), ([],[],[],[]))

    def test_averaged_battle_wrapper(self):
        pass

    def test_iterated_battle_wrapper(self):
        pass

    def test_one_fight(self):
        with self.assertRaises(Exception):
            self.match._one_fight(-1, 0, 1)

        config_short_timeout = configparser.ConfigParser()
        config_data = pkgutil.get_data('algobattle', 'config/config_short_run_timeout.ini').decode()
        config_short_timeout.read_string(config_data)
        match_run_timeout = Match(self.problem, config_short_timeout, 
          self.tests_path + '/generator_timeout', self.tests_path + '/generator',
          self.tests_path + '/solver', self.tests_path + '/solver', 0, 1)
        self.assertEqual(match_run_timeout._one_fight(1), 1.0)

        match_broken_generator = Match(self.problem, self.config, 
          self.tests_path + '/generator_execution_error', self.tests_path + '/generator',
          self.tests_path + '/solver', self.tests_path + '/solver', 0, 1, testing=True)
        self.assertEqual(match_broken_generator._one_fight(1), 1.0)

        match_wrong_generator_instance = Match(self.problem, self.config, 
          self.tests_path + '/generator_wrong_instance', self.tests_path + '/generator',
          self.tests_path + '/solver', self.tests_path + '/solver', 0, 1)
        self.assertEqual(match_wrong_generator_instance._one_fight(1), 1.0)

        match_malformed_generator_solution = Match(self.problem, self.config, 
          self.tests_path + '/generator_malformed_solution', self.tests_path + '/generator',
          self.tests_path + '/solver', self.tests_path + '/solver', 0, 1)
        self.assertEqual(match_malformed_generator_solution._one_fight(1), 1.0)

        match_wrong_generator_certificate = Match(self.problem, self.config, 
          self.tests_path + '/generator_wrong_certificate', self.tests_path + '/generator',
          self.tests_path + '/solver', self.tests_path + '/solver', 0, 1)
        self.assertEqual(match_wrong_generator_certificate._one_fight(1), 1.0)

        match_solver_timeout = Match(self.problem, config_short_timeout, 
          self.tests_path + '/generator', self.tests_path + '/generator',
          self.tests_path + '/solver', self.tests_path + '/solver_timeout', 0, 1)
        self.assertEqual(match_solver_timeout._one_fight(1), 0.0)

        match_broken_solver = Match(self.problem, self.config, 
          self.tests_path + '/generator', self.tests_path + '/generator',
          self.tests_path + '/solver', self.tests_path + '/solver_execution_error', 0, 1, testing=True)
        self.assertEqual(match_broken_solver._one_fight(1), 0.0)

        match_malformed_solution = Match(self.problem, self.config, 
          self.tests_path + '/generator', self.tests_path + '/generator',
          self.tests_path + '/solver', self.tests_path + '/solver_malformed_solution', 0, 1)
        self.assertEqual(match_malformed_solution._one_fight(1), 0.0)

        match_wrong_certificate = Match(self.problem, self.config, 
          self.tests_path + '/generator', self.tests_path + '/generator',
          self.tests_path + '/solver', self.tests_path + '/solver_wrong_certificate', 0, 1)
        self.assertEqual(match_wrong_certificate._one_fight(1), 0.0)

        self.config = configparser.ConfigParser()
        config_data = pkgutil.get_data('algobattle', 'config/config.ini').decode()
        self.config.read_string(config_data)
        successful_match = Match(self.problem, self.config, 
          self.tests_path + '/generator', self.tests_path + '/generator',
          self.tests_path + '/solver', self.tests_path + '/solver', 0, 1)
        self.assertEqual(successful_match._one_fight(1), 1.0)

    def test_run_subprocess(self):
        match_run_timeout = Match(self.problem, self.config, 
          self.tests_path + '/generator_timeout', self.tests_path + '/generator',
          self.tests_path + '/solver', self.tests_path + '/solver', 0, 1)
        raw_output, elapsed_time = match_run_timeout._run_subprocess(match_run_timeout.base_build_command + ['generator0'], 0, 2)
        self.assertGreater(elapsed_time, 1.99)
        self.assertEqual(raw_output, None)

if __name__ == '__main__':
    unittest.main()