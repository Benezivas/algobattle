"""Tests for the Fight Handler class."""
from __future__ import annotations
import unittest
import logging

from configparser import ConfigParser
from pathlib import Path
from uuid import uuid4

import algobattle
from algobattle.fight_handler import FightHandler
from algobattle.team import Matchup, Team
from algobattle.docker_util import Image
from . import testsproblem

logging.disable(logging.CRITICAL)


class FightHandlertests(unittest.TestCase):
    """Tests for the match object."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up a generator and a solver that always run successfully and fight handlers with two different configs."""
        problem = testsproblem.Problem()
        cls.problem_path = Path(testsproblem.__file__).parent
        cls.gen_succ = Image(cls.problem_path / "generator", "gen_succ")
        cls.sol_succ = Image(cls.problem_path / "solver", "sol_succ")

        config = ConfigParser()
        config.read(Path(algobattle.__file__).parent / "config.ini")
        cls.fight_handler = FightHandler(problem, config)

        config_short_run_timeout = ConfigParser()
        config_short_run_timeout.read(cls.problem_path / "config_short_run_timeout.ini")
        cls.fight_handler_short_to = FightHandler(problem, config_short_run_timeout)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.gen_succ.remove()
        cls.sol_succ.remove()

    def _build_and_run(
        self, handler: FightHandler | None = None, generator: str | Image | None = None, solver: str | Image | None = None
    ) -> float:

        if isinstance(generator, str):
            generator = Image(self.problem_path / generator, f"test_{generator}")
        elif generator is None:
            generator = self.gen_succ

        if isinstance(solver, str):
            solver = Image(self.problem_path / solver, f"test_{solver}")
        elif solver is None:
            solver = self.sol_succ

        if handler is None:
            handler = self.fight_handler

        team = Team(uuid4().hex[:8], generator, solver)
        matchup = Matchup(team, team)
        result = handler.fight(matchup, 1)
        team.cleanup()
        if generator != self.gen_succ:
            generator.remove()
        if solver != self.sol_succ:
            solver.remove()
        return result

    def test_one_fight_gen_timeout(self):
        """An approximation of 1.0 is returned if the generator times out."""
        result = self._build_and_run(handler=self.fight_handler_short_to, generator="generator_timeout")
        self.assertEqual(result, 1.0)

    def test_one_fight_gen_exec_error(self):
        """An approximation of 1.0 is returned if the generator fails on execution."""
        result = self._build_and_run(generator="generator_execution_error")
        self.assertEqual(result, 1.0)

    def test_one_fight_gen_wrong_instance(self):
        """An approximation of 1.0 is returned if the generator returns a bad instance."""
        result = self._build_and_run(generator="generator_wrong_instance")
        self.assertEqual(result, 1.0)

    def test_one_fight_gen_malformed_sol(self):
        """An approximation of 1.0 is returned if the generator returns a malformed certificate."""
        result = self._build_and_run(generator="generator_malformed_solution")
        self.assertEqual(result, 1.0)

    def test_one_fight_gen_wrong_cert(self):
        """An approximation of 1.0 is returned if the generator returns a bad certificate."""
        result = self._build_and_run(generator="generator_wrong_certificate")
        self.assertEqual(result, 1.0)

    def test_one_fight_sol_timeout(self):
        """An approximation ratio of 0.0 is returned if the solver times out."""
        result = self._build_and_run(handler=self.fight_handler_short_to, solver="solver_timeout")
        self.assertEqual(result, 0.0)

    def test_one_fight_sol_exec_error(self):
        """An approximation ratio of 0.0 is returned if the solver fails on execution."""
        result = self._build_and_run(solver="solver_execution_error")
        self.assertEqual(result, 0.0)

    def test_one_fight_sol_malformed(self):
        """An approximation ratio of 0.0 is returned if the solver returns a malformed certificate."""
        result = self._build_and_run(solver="solver_malformed_solution")
        self.assertEqual(result, 0.0)

    def test_one_fight_sol_wrong_cert(self):
        """An approximation ratio of 0.0 is returned if the solver returns a bad certificate."""
        result = self._build_and_run(solver="solver_wrong_certificate")
        self.assertEqual(result, 0.0)

    def test_one_fight_successful(self):
        """An approximation ratio of 1.0 is returned if a solver correctly and optimally solves an instance."""
        result = self._build_and_run()
        self.assertEqual(result, 1.0)

    # TODO: Test approximation ratios != 1.0
    # TODO: Split up further into _run_generator and _run_solver?


if __name__ == "__main__":
    unittest.main()
