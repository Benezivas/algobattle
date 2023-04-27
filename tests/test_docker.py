"""Tests for all docker functions."""
from unittest import IsolatedAsyncioTestCase, main as run_tests
import random
from pathlib import Path

from algobattle.docker_util import (
    ExecutionTimeout,
    BuildError,
    ExecutionError,
    Generator,
    Image,
    RunParameters,
    Solver,
)
from . import testsproblem
from .testsproblem.problem import TestProblem as TestProblem


class ImageTests(IsolatedAsyncioTestCase):
    """Tests for the Image functions."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up the path to the docker containers."""
        cls.problem_path = Path(testsproblem.__file__).parent

    @classmethod
    def dockerfile(cls, name: str) -> Path:
        return cls.problem_path / name

    async def test_build_timeout(self):
        """Raises an error if building a container runs into a timeout."""
        with self.assertRaises(BuildError), await Image.build(self.problem_path / "build_timeout", timeout=0.5):
            pass

    async def test_build_failed(self):
        """Raises an error if building a docker container fails for any reason other than a timeout."""
        with self.assertRaises(BuildError), await Image.build(self.problem_path / "build_error"):
            pass

    async def test_build_successful(self):
        """Runs successfully if a docker container builds successfully."""
        with await Image.build(self.problem_path / "generator"):
            pass

    async def test_build_nonexistant_path(self):
        """Raises an error if the path to the container does not exist in the file system."""
        with self.assertRaises(RuntimeError):
            nonexistent_file = None
            while nonexistent_file is None or nonexistent_file.exists():
                nonexistent_file = Path(str(random.randint(0, 2**80)))
            with await Image.build(nonexistent_file):
                pass

    async def test_run_timeout(self):
        """`Image.run()` raises an error when the container times out."""
        with await Image.build(self.problem_path / "generator_timeout") as image, self.assertRaises(ExecutionTimeout):
            await image.run(timeout=1.0)

    async def test_run_error(self):
        """Raises an error if the container doesn't run successfully."""
        with (
            self.assertRaises(ExecutionError),
            await Image.build(self.problem_path / "generator_execution_error") as image,
        ):
            await image.run(timeout=10.0)


class ProgramTests(IsolatedAsyncioTestCase):
    """Tests for the Program functions."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up the config and problem objects."""
        cls.problem_path = Path(testsproblem.__file__).parent
        cls.params = RunParameters()
        cls.params_short = RunParameters(timeout=2)
        cls.instance = TestProblem(semantics=True)

    async def test_gen_timeout(self):
        """The generator times out."""
        with await Generator.build(self.problem_path / "generator_timeout", TestProblem, self.params_short) as gen:
            res = await gen.run(5)
            assert res.info.error is not None
            self.assertEqual(res.info.error.type, "ExecutionTimeout")

    async def test_gen_exec_err(self):
        """The generator doesn't execute properly."""
        with await Generator.build(self.problem_path / "generator_execution_error", TestProblem, self.params) as gen:
            res = await gen.run(5)
            assert res.info.error is not None
            self.assertEqual(res.info.error.type, "ExecutionError")

    async def test_gen_syn_err(self):
        """The generator outputs a syntactically incorrect solution."""
        with await Generator.build(self.problem_path / "generator_syntax_error", TestProblem, self.params) as gen:
            res = await gen.run(5)
            assert res.info.error is not None
            self.assertEqual(res.info.error.type, "EncodingError")

    async def test_gen_sem_err(self):
        """The generator outputs a semantically incorrect solution."""
        with await Generator.build(self.problem_path / "generator_semantics_error", TestProblem, self.params) as gen:
            res = await gen.run(5)
            assert res.info.error is not None
            self.assertEqual(res.info.error.type, "ValidationError")

    async def test_gen_succ(self):
        """The generator returns the fixed instance."""
        with await Generator.build(self.problem_path / "generator", TestProblem, self.params) as gen:
            res = await gen.run(5)
            correct = TestProblem(semantics=True)
            self.assertEqual(res.instance, correct)

    async def test_sol_timeout(self):
        """The solver times out."""
        with await Solver.build(self.problem_path / "solver_timeout", TestProblem, self.params_short) as sol:
            res = await sol.run(self.instance, 5)
            assert res.info.error is not None
            self.assertEqual(res.info.error.type, "ExecutionTimeout")

    async def test_sol_exec_err(self):
        """The solver doesn't execute properly."""
        with await Solver.build(self.problem_path / "solver_execution_error", TestProblem, self.params) as sol:
            res = await sol.run(self.instance, 5)
            assert res.info.error is not None
            self.assertEqual(res.info.error.type, "ExecutionError")

    async def test_sol_syn_err(self):
        """The solver outputs a syntactically incorrect solution."""
        with await Solver.build(self.problem_path / "solver_syntax_error", TestProblem, self.params) as sol:
            res = await sol.run(self.instance, 5)
            assert res.info.error is not None
            self.assertEqual(res.info.error.type, "EncodingError")

    async def test_sol_sem_err(self):
        """The solver outputs a semantically incorrect solution."""
        with await Solver.build(self.problem_path / "solver_semantics_error", TestProblem, self.params) as sol:
            res = await sol.run(self.instance, 5)
            assert res.info.error is not None
            self.assertEqual(res.info.error.type, "ValidationError")

    async def test_sol_succ(self):
        """The solver outputs a solution with a low quality."""
        with await Solver.build(self.problem_path / "solver", TestProblem, self.params) as sol:
            res = await sol.run(self.instance, 5)
            correct = TestProblem.Solution(semantics=True, quality=True)
            self.assertEqual(res.solution, correct)


if __name__ == "__main__":
    run_tests()
