"""Tests for all util functions."""
from typing import cast
import unittest
import logging
import importlib
import random

from configparser import ConfigParser
from pathlib import Path

import algobattle
from algobattle.battle_wrappers.iterated import Iterated
import algobattle.util as util
from algobattle.fight_handler import FightHandler
from algobattle.docker import measure_runtime_overhead

logging.disable(logging.CRITICAL)


class Utiltests(unittest.TestCase):
    """Tests for the util functions."""

    def setUp(self) -> None:
        """Set up a problem, default config, fight handler and get a file name not existing on the file system."""
        Problem = importlib.import_module('algobattle.problems.testsproblem')
        self.problem = Problem.Problem()
        config_path = Path(Path(algobattle.__file__).parent, 'config', 'config.ini')
        self.config = ConfigParser()
        self.config.read(config_path)
        self.fight_handler = FightHandler(self.problem, self.config)
        self.problem_path = Path(cast(str, Problem.__file__)).parent
        self.rand_file_name = str(random.randint(0, 2 ** 80))
        while Path(self.rand_file_name).exists():
            self.rand_file_name = str(random.randint(0, 2 ** 80))

    def test_import_problem_from_path_existing_path(self):
        """Importing works when importing a Problem from an existing path."""
        self.assertIsNotNone(util.import_problem_from_path(self.problem_path))

    def test_import_problem_from_path_nonexistant_path(self):
        """An import fails if importing from a nonexistant path."""
        self.assertIsNone(util.import_problem_from_path(Path(self.rand_file_name)))

    def test_initialize_wrapper_existing_path(self):
        """Initializing an existing wrapper works as expected."""
        self.assertEqual(type(util.initialize_wrapper('iterated', self.config)), type(Iterated(self.config)))

    def test_initialize_wrapper_nonexistent_path(self):
        """Initializing a nonexistent wrapper returns None."""
        self.assertEqual(util.initialize_wrapper(self.rand_file_name, self.config), None)

    def test_measure_runtime_overhead(self):
        """The overhead calculation returns some float greater than zero on normal execution."""
        self.assertGreater(measure_runtime_overhead(), 0)

    def test_build_docker_container_timeout(self):
        """False is returned if building a container runs into a timeout."""
        self.assertFalse(util.build_docker_container(Path(self.problem_path, 'generator_build_timeout'),
                                                     docker_tag='gen_bld_to',
                                                     timeout_build=0.5,
                                                     cache_docker_container=False))

    def test_build_docker_container_failed_build(self):
        """False is returned if building a docker container fails for any reason other than a timeout."""
        self.assertFalse(util.build_docker_container(Path(self.problem_path, 'generator_build_error'),
                                                     docker_tag='gen_bld_err',
                                                     cache_docker_container=False))

    def test_build_docker_container_successful_build(self):
        """True is returned if a docker container builds successfully."""
        self.assertTrue(util.build_docker_container(Path(self.problem_path, 'generator'),
                                                    docker_tag='gen_succ',
                                                    cache_docker_container=False))

    def test_build_docker_container_nonexistant_path(self):
        """False is returned if the path to the container does not exist in the file system."""
        self.assertFalse(util.build_docker_container(Path(self.problem_path, 'foobar'),
                                                     docker_tag='foo_bar',
                                                     cache_docker_container=False))

    def test_run_subprocess_timeout(self):
        """run_subprocess returns None on a subprocess timeout."""
        docker_tag = 'gen_to'
        util.build_docker_container(Path(self.problem_path, 'generator_timeout'),
                                    docker_tag,
                                    cache_docker_container=False)
        run_command = self.fight_handler.base_run_command(self.fight_handler.space_generator) + [docker_tag]
        raw_output, _ = util.run_subprocess(run_command, input=None, timeout=2.0)
        self.assertIsNone(raw_output)

    def test_run_subprocess_execution_error(self):
        """run_subprocess returns None if an exception is thrown during execution of the subprocess."""
        docker_tag = 'gen_err'
        util.build_docker_container(Path(self.problem_path, 'generator_execution_error'),
                                    docker_tag,
                                    cache_docker_container=False)
        run_command = self.fight_handler.base_run_command(self.fight_handler.space_generator) + [docker_tag]
        raw_output, _ = util.run_subprocess(run_command, input=None, timeout=10.0)
        self.assertIsNone(raw_output)

    def test_update_nested_dict(self):
        """A nested dict should be updated with information from another nested dict as expected."""
        dict_to_be_expanded = {0: 1, 1: {0: 0, 1: 0}, 2: 2}
        dict_expanding = {1: {1: 1}, 2: 1}
        self.assertEqual(util.update_nested_dict(dict_to_be_expanded, dict_expanding),
                         {0: 1, 1: {0: 0, 1: 1}, 2: 1})


if __name__ == '__main__':
    unittest.main()
