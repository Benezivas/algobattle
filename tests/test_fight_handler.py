"""Tests for the Fight Handler class."""
from configparser import ConfigParser
import unittest
import logging
import importlib
import os

import algobattle
import algobattle.util as util
from algobattle.fight_handler import FightHandler
from algobattle.team import Team

logging.disable(logging.CRITICAL)


class FightHandlertests(unittest.TestCase):
    """Tests for the match object."""

    def setUp(self) -> None:
        Problem = importlib.import_module('algobattle.problems.testsproblem')
        self.problem = Problem.Problem()
        self.problem_path = Problem.__file__[:-12]  # remove /__init__.py

        util.build_docker_container(os.path.join(self.problem_path, 'generator'),
                                    docker_tag='gen_succ',
                                    cache_docker_container=False)
        util.build_docker_container(os.path.join(self.problem_path, 'solver'),
                                    docker_tag='sol_succ',
                                    cache_docker_container=False)

        self.config_base_path = os.path.join(os.path.dirname(os.path.abspath(algobattle.__file__)), 'config')
        self.config = ConfigParser()
        self.config.read(os.path.join(self.config_base_path, 'config.ini'))

        self.config_short_run_timeout = ConfigParser()
        self.config_short_run_timeout.read(os.path.join(self.config_base_path, 'config_short_run_timeout.ini'))

        self.fight_handler = FightHandler(self.problem, self.config)
        self.fight_handler_short_to = FightHandler(self.problem, self.config_short_run_timeout)

    def test_one_fight_gen_timeout(self):
        """An approximation of 1.0 is returned if the generator times out."""
        util.build_docker_container(os.path.join(self.problem_path, 'generator_timeout'),
                                    docker_tag='gen_to',
                                    cache_docker_container=False)
        team = Team('0', 'gen_to', 'sol_succ')
        self.fight_handler_short_to.set_roles(generating=team, solving=team)
        self.assertEqual(self.fight_handler_short_to.fight(1), 1.0)

    def test_one_fight_gen_exec_error(self):
        """An approximation of 1.0 is returned if the generator fails on execution."""
        util.build_docker_container(os.path.join(self.problem_path, 'generator_execution_error'),
                                    docker_tag='gen_exerr',
                                    cache_docker_container=False)
        team = Team('0', 'gen_exerr', 'sol_succ')
        self.fight_handler.set_roles(generating=team, solving=team)
        self.assertEqual(self.fight_handler.fight(1), 1.0)

    def test_one_fight_gen_wrong_instance(self):
        """An approximation of 1.0 is returned if the generator returns a bad instance."""
        util.build_docker_container(os.path.join(self.problem_path, 'generator_wrong_instance'),
                                    docker_tag='gen_bad_inst',
                                    cache_docker_container=False)
        team = Team('0', 'gen_bad_inst', 'sol_succ')
        self.fight_handler.set_roles(generating=team, solving=team)
        self.assertEqual(self.fight_handler.fight(1), 1.0)

    def test_one_fight_gen_malformed_sol(self):
        """An approximation of 1.0 is returned if the generator returns a malformed certificate."""
        util.build_docker_container(os.path.join(self.problem_path, 'generator_malformed_solution'),
                                    docker_tag='gen_mal_cert',
                                    cache_docker_container=False)
        team = Team('0', 'gen_mal_cert', 'sol_succ')
        self.fight_handler.set_roles(generating=team, solving=team)
        self.assertEqual(self.fight_handler.fight(1), 1.0)

    def test_one_fight_gen_wrong_cert(self):
        """An approximation of 1.0 is returned if the generator returns a bad certificate."""
        util.build_docker_container(os.path.join(self.problem_path, 'generator_wrong_certificate'),
                                    docker_tag='gen_bad_cert',
                                    cache_docker_container=False)
        team = Team('0', 'gen_bad_cert', 'sol_succ')
        self.fight_handler.set_roles(generating=team, solving=team)
        self.assertEqual(self.fight_handler.fight(1), 1.0)

    def test_one_fight_sol_timeout(self):
        """An approximation ratio of 0.0 is returned if the solver times out."""
        util.build_docker_container(os.path.join(self.problem_path, 'solver_timeout'),
                                    docker_tag='sol_to',
                                    cache_docker_container=False)
        team = Team('0', 'gen_succ', 'sol_to')
        self.fight_handler_short_to.set_roles(generating=team, solving=team)
        self.assertEqual(self.fight_handler_short_to.fight(1), 0.0)

    def test_one_fight_sol_exec_error(self):
        """An approximation ratio of 0.0 is returned if the solver fails on execution."""
        util.build_docker_container(os.path.join(self.problem_path, 'solver_execution_error'),
                                    docker_tag='sol_exerr',
                                    cache_docker_container=False)
        team = Team('0', 'gen_succ', 'sol_exerr')
        self.fight_handler.set_roles(generating=team, solving=team)
        self.assertEqual(self.fight_handler.fight(1), 0.0)

    def test_one_fight_sol_malformed(self):
        """An approximation ratio of 0.0 is returned if the solver returns a malformed certificate."""
        util.build_docker_container(os.path.join(self.problem_path, 'solver_malformed_solution'),
                                    docker_tag='sol_mal_cert',
                                    cache_docker_container=False)
        team = Team('0', 'gen_succ', 'sol_mal_cert')
        self.fight_handler.set_roles(generating=team, solving=team)
        self.assertEqual(self.fight_handler.fight(1), 0.0)

    def test_one_fight_sol_wrong_cert(self):
        """An approximation ratio of 0.0 is returned if the solver returns a bad certificate."""
        util.build_docker_container(os.path.join(self.problem_path, 'solver_wrong_certificate'),
                                    docker_tag='sol_bad_cert',
                                    cache_docker_container=False)
        team = Team('0', 'gen_succ', 'sol_bad_cert')
        self.fight_handler.set_roles(generating=team, solving=team)
        self.assertEqual(self.fight_handler.fight(1), 0.0)

    def test_one_fight_successful(self):
        """An approximation ratio of 1.0 is returned if a solver correctly and optimally solves an instance."""
        team = Team('0', 'gen_succ', 'sol_succ')
        self.fight_handler.set_roles(generating=team, solving=team)
        self.assertEqual(self.fight_handler.fight(1), 1.0)

    # TODO: Test approximation ratios != 1.0
    # TODO: Split up further into _run_generator and _run_solver?


if __name__ == '__main__':
    unittest.main()
