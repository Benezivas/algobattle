"""Tests for all docker functions."""
from __future__ import annotations
from typing import cast
import unittest
import logging
import importlib
import random

from configparser import ConfigParser
from pathlib import Path

import algobattle
import algobattle.util as util
from algobattle.fight_handler import FightHandler
from algobattle.docker import measure_runtime_overhead

logging.disable(logging.CRITICAL)


class DockerTests(unittest.TestCase):
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


if __name__ == '__main__':
    unittest.main()
