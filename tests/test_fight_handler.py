"""Tests for the Fight Handler class."""
from __future__ import annotations
from typing import cast
import unittest
import logging
import importlib

from configparser import ConfigParser
from pathlib import Path

import algobattle
from algobattle.fight_handler import FightHandler
from algobattle.team import Team
from algobattle.docker import Image

logging.disable(logging.CRITICAL)


class FightHandlertests(unittest.TestCase):
    """Tests for the match object."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up a generator and a solver that always run successfully and fight handlers with two different configs."""
        Problem = importlib.import_module("algobattle.problems.testsproblem")
        cls.problem = Problem.Problem()
        cls.problem_path = Path(cast(str, Problem.__file__)).parent

        cls.gen_succ = Image(cls.problem_path / "generator", "gen_succ")
        cls.sol_succ = Image(cls.problem_path / "solver", "sol_succ")

        cls.config_base_path = Path(Path(algobattle.__file__).parent, "config")
        cls.config = ConfigParser()
        cls.config.read(Path(cls.config_base_path, "config.ini"))

        cls.config_short_run_timeout = ConfigParser()
        cls.config_short_run_timeout.read(Path(cls.config_base_path, "config_short_run_timeout.ini"))

        cls.fight_handler = FightHandler(cls.problem, cls.config)
        cls.fight_handler_short_to = FightHandler(cls.problem, cls.config_short_run_timeout)

    @classmethod
    def tearDown(cls) -> None:
        cls.gen_succ.remove()
        cls.sol_succ.remove()

    def _build_and_run(
        self, handler: FightHandler | None = None, generator: str | Image | None = None, solver: str | Image | None = None
    ) -> float:
        built_images: set[Image] = set()

        if isinstance(generator, str):
            generator = Image(self.problem_path / generator, f"test_generator_{generator}", cache=False)
            built_images.add(generator)
        elif generator is None:
            generator = self.gen_succ

        if isinstance(solver, str):
            solver = Image(self.problem_path / solver, f"test_generator_{solver}", cache=False)
            built_images.add(solver)
        elif solver is None:
            solver = self.sol_succ

        if handler is None:
            handler = self.fight_handler

        team = Team("test", generator, solver)
        self.fight_handler_short_to.set_roles(generating=team, solving=team)
        result = handler.fight(1)
        for image in built_images:
            image.remove()
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
