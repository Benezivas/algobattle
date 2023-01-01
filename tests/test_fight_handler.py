"""Tests for the Fight Handler class."""
from __future__ import annotations
import unittest
import logging

from pathlib import Path
from uuid import uuid4

from algobattle.fight_handler import FightHandler
from algobattle.match import MatchConfig
from algobattle.team import Matchup, Team
from algobattle.docker_util import Image, get_os_type
from . import testsproblem

logging.disable(logging.CRITICAL)


class FightHandlertests(unittest.TestCase):
    """Tests for the match object."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up a generator and a solver that always run successfully and fight handlers with two different configs."""
        cls.problem_path = Path(testsproblem.__file__).parent
        if get_os_type() == "windows":
            cls.dockerfile = "Dockerfile_windows"
        else:
            cls.dockerfile = None
        cls.gen_succ = Image.build(cls.problem_path / "generator", "gen_succ", dockerfile=cls.dockerfile)
        cls.sol_succ = Image.build(cls.problem_path / "solver", "sol_succ", dockerfile=cls.dockerfile)

        cls.config_short = MatchConfig(timeout_generator=2, timeout_solver=2)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.gen_succ.remove()
        cls.sol_succ.remove()

    def _build_and_run(self, config: MatchConfig = MatchConfig(), gen_name: str = "gen_succ", sol_name: str = "sol_succ") -> float:
        generator = Image.build(self.problem_path / gen_name, f"test_{gen_name}", dockerfile=self.dockerfile)
        solver = Image.build(self.problem_path / sol_name, f"test_{sol_name}", dockerfile=self.dockerfile)
        team = Team(uuid4().hex[:8], generator, solver)
        matchup = Matchup(team, team)
        handler = FightHandler(problem=testsproblem.Problem, matchup=matchup, **config.docker_params)
        result = handler.fight(5)
        team.cleanup()
        if generator != self.gen_succ:
            generator.remove()
        if solver != self.sol_succ:
            solver.remove()
        return result.score

    def test_one_fight_gen_timeout(self):
        """An approximation of 1.0 is returned if the generator times out."""
        result = self._build_and_run(self.config_short, gen_name="generator_timeout")
        self.assertEqual(result, 1.0)

    def test_one_fight_gen_exec_error(self):
        """An approximation of 1.0 is returned if the generator fails on execution."""
        result = self._build_and_run(gen_name="generator_execution_error")
        self.assertEqual(result, 1.0)

    def test_one_fight_gen_wrong_instance(self):
        """An approximation of 1.0 is returned if the generator returns a bad instance."""
        result = self._build_and_run(gen_name="generator_wrong_instance")
        self.assertEqual(result, 1.0)

    def test_one_fight_gen_malformed_sol(self):
        """An approximation of 1.0 is returned if the generator returns a malformed certificate."""
        result = self._build_and_run(gen_name="generator_malformed_solution")
        self.assertEqual(result, 1.0)

    def test_one_fight_gen_wrong_cert(self):
        """An approximation of 1.0 is returned if the generator returns a bad certificate."""
        result = self._build_and_run(gen_name="generator_wrong_certificate")
        self.assertEqual(result, 1.0)

    def test_one_fight_sol_timeout(self):
        """An approximation ratio of 0.0 is returned if the solver times out."""
        result = self._build_and_run(self.config_short, sol_name="solver_timeout")
        self.assertEqual(result, 0.0)

    def test_one_fight_sol_exec_error(self):
        """An approximation ratio of 0.0 is returned if the solver fails on execution."""
        result = self._build_and_run(sol_name="solver_execution_error")
        self.assertEqual(result, 0.0)

    def test_one_fight_sol_malformed(self):
        """An approximation ratio of 0.0 is returned if the solver returns a malformed certificate."""
        result = self._build_and_run(sol_name="solver_malformed_solution")
        self.assertEqual(result, 0.0)

    def test_one_fight_sol_wrong_cert(self):
        """An approximation ratio of 0.0 is returned if the solver returns a bad certificate."""
        result = self._build_and_run(sol_name="solver_wrong_certificate")
        self.assertEqual(result, 0.0)

    def test_one_fight_successful(self):
        """An approximation ratio of 1.0 is returned if a solver correctly and optimally solves an instance."""
        result = self._build_and_run()
        self.assertEqual(result, 1.0)

    # TODO: Test approximation ratios != 1.0
    # TODO: Split up further into _run_generator and _run_solver?


if __name__ == "__main__":
    unittest.main()
