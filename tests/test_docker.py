"""Tests for all docker functions."""
from __future__ import annotations
from typing import cast
import unittest
import logging
import random
from pathlib import Path

from algobattle.docker_util import DockerError, Image, client, DockerImage
from . import testsproblem

logging.disable(logging.CRITICAL)


class DockerTests(unittest.TestCase):
    """Tests for the util functions."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up the path to the docker containers."""
        cls.problem_path = Path(testsproblem.__file__).parent

    def test_build_timeout(self):
        """Raises an error if building a container runs into a timeout."""
        with self.assertRaises(DockerError), Image.build(self.problem_path / "generator_build_timeout", "gen_built_to", timeout=0.5):
            pass

    def test_build_failed(self):
        """Raises an error if building a docker container fails for any reason other than a timeout."""
        with self.assertRaises(DockerError), Image.build(self.problem_path / "generator_build_error", "gen_build_error"):
            pass

    def test_build_successful(self):
        """Runs successfully if a docker container builds successfully."""
        with Image.build(self.problem_path / "generator", "gen_succ"):
            pass

    def test_build_nonexistant_path(self):
        """Raises an error if the path to the container does not exist in the file system."""
        with self.assertRaises(DockerError):
            nonexistent_file = None
            while nonexistent_file is None or nonexistent_file.exists():
                nonexistent_file = Path(str(random.randint(0, 2 ** 80)))
            with Image.build(nonexistent_file, "foo_bar"):
                pass

    def test_run_timeout(self):
        """`Image.run()` normally terminates when the container times out."""
        with Image.build(self.problem_path / "generator_timeout", "gen_to") as image:
            image.run(timeout=1.0)

    def test_run_error(self):
        """Raises an error if the container doesn't run successfully."""
        with self.assertRaises(DockerError), Image.build(self.problem_path / "generator_execution_error", "gen_err") as image:
            image.run(timeout=10.0)

    def test_archive(self):
        """Raises an error if the image can't be archived and restored properly."""
        with Image.build(self.problem_path / "generator", "gen_arch") as image:
            original_tag = cast(DockerImage, client().images.get(image.id)).tags[0]
            archived = image.archive()
            assert (self.problem_path / "generator" / "gen_arch-archive.tar").is_file()
            restored = archived.restore()
            docker_image = cast(DockerImage, client().images.get(restored.id))
            assert docker_image.id == image.id
            assert docker_image.tags == [original_tag]

if __name__ == '__main__':
    unittest.main()
