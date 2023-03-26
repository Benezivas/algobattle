"""Tests for all docker functions."""
from __future__ import annotations
from typing import cast
from unittest import IsolatedAsyncioTestCase, main as run_tests
import logging
import random
from pathlib import Path

from algobattle.docker_util import (
    DockerError,
    EncodingError,
    ExecutionError,
    Generator,
    Image,
    RunParameters,
    SemanticsError,
    Solver,
    client,
    DockerImage,
    get_os_type,
)
from algobattle.util import TempDir
from . import testsproblem
from .testsproblem.problem import Tests as TestProblem

logging.disable(logging.CRITICAL)


class ImageTests(IsolatedAsyncioTestCase):
    """Tests for the Image functions."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up the path to the docker containers."""
        cls.problem_path = Path(testsproblem.__file__).parent

    @classmethod
    def dockerfile(cls, name: str) -> tuple[Path, str]:
        return cls.problem_path / name, name

    def test_build_timeout(self):
        """Raises an error if building a container runs into a timeout."""
        with self.assertRaises(DockerError), Image.build(*self.dockerfile("build_timeout"), timeout=0.5):
            pass

    def test_build_failed(self):
        """Raises an error if building a docker container fails for any reason other than a timeout."""
        with self.assertRaises(DockerError), Image.build(*self.dockerfile("build_error")):
            pass

    def test_build_successful(self):
        """Runs successfully if a docker container builds successfully."""
        with Image.build(*self.dockerfile("generator")):
            pass

    def test_build_nonexistant_path(self):
        """Raises an error if the path to the container does not exist in the file system."""
        with self.assertRaises(DockerError):
            nonexistent_file = None
            while nonexistent_file is None or nonexistent_file.exists():
                nonexistent_file = Path(str(random.randint(0, 2 ** 80)))
            with Image.build(nonexistent_file, "foo_bar"):
                pass

    async def test_run_timeout(self):
        """`Image.run()` normally terminates when the container times out."""
        with Image.build(*self.dockerfile("generator_timeout")) as image:
            await image.run(timeout=1.0)

    async def test_run_error(self):
        """Raises an error if the container doesn't run successfully."""
        with self.assertRaises(DockerError), Image.build(*self.dockerfile("generator_execution_error")) as image:
            await image.run(timeout=10.0)

    def test_archive(self):
        """Raises an error if the image can't be archived and restored properly."""
        with Image.build(*self.dockerfile("generator")) as image, TempDir() as folder:
            original_tag = cast(DockerImage, client().images.get(image.id)).tags[0]
            archived = image.archive(folder)
            assert (folder / "generator-archive.tar").is_file()
            restored = archived.restore()
            docker_image = cast(DockerImage, client().images.get(restored.id))
            assert docker_image.id == image.id
            assert docker_image.tags == [original_tag]


class ProgramTests(IsolatedAsyncioTestCase):
    """Tests for the Program functions."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up the config and problem objects."""
        cls.problem_path = Path(testsproblem.__file__).parent
        cls.params = RunParameters()
        cls.params_short = RunParameters(timeout=2)
        cls.instance = TestProblem(semantics=True)

    @classmethod
    def dockerfile(cls, name: str) -> tuple[Path, str]:
        if get_os_type() == "windows":
            return cls.problem_path / name / "Dockerfile_windows", name
        else:
            return cls.problem_path / name, name

    async def test_gen_timeout(self):
        """The generator doesnt output a solution."""
        with Generator.build(*self.dockerfile("generator_timeout"), TestProblem, self.params_short) as gen:
            with self.assertRaises(EncodingError):
                await gen.run(5)

    async def test_gen_exec_err(self):
        """The generator doesn't execute properly."""
        with Generator.build(*self.dockerfile("generator_execution_error"), TestProblem, self.params) as gen:
            with self.assertRaises(ExecutionError):
                await gen.run(5)

    async def test_gen_syn_err(self):
        """The generator outputs a syntactically incorrect solution."""
        with Generator.build(*self.dockerfile("generator_syntax_error"), TestProblem, self.params) as gen:
            with self.assertRaises(EncodingError):
                await gen.run(5)

    async def test_gen_sem_err(self):
        """The generator outputs a semantically incorrect solution."""
        with Generator.build(*self.dockerfile("generator_semantics_error"), TestProblem, self.params) as gen:
            with self.assertRaises(SemanticsError):
                await gen.run(5)

    async def test_gen_succ(self):
        """The generator returns the fixed instance."""
        with Generator.build(*self.dockerfile("generator"), TestProblem, self.params) as gen:
            res = await gen.run(5)
            correct = TestProblem(semantics=True)
            self.assertEqual(res.problem, correct)

    async def test_sol_timeout(self):
        """The solver times out."""
        with Solver.build(*self.dockerfile("solver_timeout"), TestProblem, self.params_short) as sol:
            with self.assertRaises(EncodingError):
                await sol.run(self.instance, 5)

    async def test_sol_exec_err(self):
        """The solver doesn't execute properly."""
        with Solver.build(*self.dockerfile("solver_execution_error"), TestProblem, self.params) as sol:
            with self.assertRaises(ExecutionError):
                await sol.run(self.instance, 5)

    async def test_sol_syn_err(self):
        """The solver outputs a syntactically incorrect solution."""
        with Solver.build(*self.dockerfile("solver_syntax_error"), TestProblem, self.params) as sol:
            with self.assertRaises(EncodingError):
                await sol.run(self.instance, 5)

    async def test_sol_sem_err(self):
        """The solver outputs a semantically incorrect solution."""
        with Solver.build(*self.dockerfile("solver_semantics_error"), TestProblem, self.params) as sol:
            with self.assertRaises(SemanticsError):
                await sol.run(self.instance, 5)

    async def test_sol_succ(self):
        """The solver outputs a solution with a low quality."""
        with Solver.build(*self.dockerfile("solver"), TestProblem, self.params) as sol:
            res = await sol.run(self.instance, 5)
            correct = TestProblem.Solution(semantics=True, quality=True)
            self.assertEqual(res.solution, correct)


if __name__ == "__main__":
    run_tests()
