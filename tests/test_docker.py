"""Tests for all docker functions."""
from __future__ import annotations
from typing import cast
import unittest
import logging
import random

from pathlib import Path

import algobattle
from algobattle.docker import DockerError, Image, measure_runtime_overhead

logging.disable(logging.CRITICAL)


class DockerTests(unittest.TestCase):
    """Tests for the util functions."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up the path to the docker containers."""
        cls.problem_path = Path(cast(str, algobattle.__file__)).parent / "problems" / "testsproblem"

    def test_build_docker_container_timeout(self):
        """Raises an error if building a container runs into a timeout."""
        with self.assertRaises(DockerError):
            image = Image(self.problem_path / "generator_build_timeout", "gen_built_to", timeout=0.5, cache=False)
            image.remove()

    def test_build_docker_container_failed_build(self):
        """Raises an error if building a docker container fails for any reason other than a timeout."""
        with self.assertRaises(DockerError):
            image = Image(self.problem_path / "generator_build_error", "gen_build_error", cache=False)
            image.remove()

    def test_build_docker_container_successful_build(self):
        """Runs successfully if a docker container builds successfully."""
        image = Image(self.problem_path / "generator", "gen_succ", cache=False)
        image.remove()

    def test_build_docker_container_nonexistant_path(self):
        """Raises an error if the path to the container does not exist in the file system."""
        with self.assertRaises(DockerError):
            nonexistent_file = None
            while nonexistent_file is None or nonexistent_file.exists():
                nonexistent_file = Path(str(random.randint(0, 2 ** 80)))
            image = Image(nonexistent_file, "foo_bar", cache=False)
            image.remove()

    def test_run_subprocess_timeout(self):
        """`Image.run()` raises an error when the container times out."""
        with self.assertRaises(DockerError):
            image = Image(self.problem_path / "generator_timeout", "gen_to", cache=False)
            try:
                image.run(timeout=2.0)
            finally:
                image.remove()
                raise

    def test_run_subprocess_execution_error(self):
        """run_subprocess returns None if an exception is thrown during execution of the subprocess."""
        with self.assertRaises(DockerError):
            image = Image(self.problem_path / "generator_execution_error", "gen_err", cache=False)
            try:
                image.run(timeout=10.0)
            finally:
                image.remove()
                raise

    def test_measure_runtime_overhead(self):
        """The overhead calculation returns some float greater than zero on normal execution."""
        self.assertGreater(measure_runtime_overhead(), 0)


if __name__ == '__main__':
    unittest.main()
