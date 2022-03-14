"""Module for the Fight class which is responsible for executing a fight with a given matchup."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Generic, TypeVar
from logging import getLogger
from algobattle.docker import DockerConfig, DockerError
from algobattle.problem import Problem
from algobattle.team import Team, Matchup

logger = getLogger("algobattle.fight")

Instance = TypeVar("Instance")
Solution = TypeVar("Solution")

@dataclass
class Fight(Generic[Instance, Solution]):
    """Class that executes a single fight with a given matchup."""

    problem: Problem[Instance, Solution]
    docker_config: DockerConfig

    def __call__(self, matchup: Matchup, instance_size: int) -> float:
        """Execute a fight of a battle between a given generator and solver for a given instance size.

        Parameters
        ----------
        instance_size : int
            The instance size, expected to be a positive int.

        Returns
        -------
        float
            Returns the approximation ratio of the solver against
            the generator (1 if optimal, 0 if failed, >=1 if the
            generator solution is optimal).
        """
        try:
            instance, generator_solution = self._run_generator(matchup.generator, instance_size)
        except ValueError:
            return self.problem.approx_cap

        try:
            solver_solution = self._run_solver(matchup.solver, instance_size, instance)
        except ValueError:
            return 0

        approximation_ratio = self.problem.approximation_ratio(instance, instance_size, generator_solution, solver_solution)
        logger.info(
            f"Solver of group {matchup.solver} yields a valid solution with an approx. ratio of {approximation_ratio}."
        )
        return approximation_ratio

    def _run_generator(self, team: Team, instance_size: int) -> tuple[Instance, Solution]:
        """Execute the generator of match.generating_team and check the validity of the generated output.

        If the validity checks pass, return the instance and the certificate solution.

        Parameters
        ----------
        instance_size : int
            The instance size, expected to be a positive int.

        Returns
        -------
        Instance, Solution
            The generated instance and solution.

        Raises
        ------
        ValueError
            If no valid instance and solution can be generated.
        """
        if self.docker_config.space_generator is not None:
            scaled_memory = self.problem.generator_memory_scaler(self.docker_config.space_generator, instance_size)
        else:
            scaled_memory = None

        logger.debug(f"Running generator of group {team}...")
        try:
            output = team.generator.run(
                str(instance_size),
                timeout=self.docker_config.timeout_generator,
                memory=scaled_memory,
                cpus=self.docker_config.cpus,
            )
        except DockerError:
            logger.warning(f"generator of team '{team}' didn't run successfully!")
            raise ValueError

        if not output:
            logger.warning(f"No output was generated when running {team.generator}!")
            raise ValueError

        logger.debug("Checking generated instance and certificate...")
        raw_instance, raw_solution = self.problem.split(output)
        try:
            instance = self.problem.parse_instance(raw_instance, instance_size)
        except ValueError:
            logger.warning(f"Generator {team} created a malformed instance!")
            raise

        try:
            solution = self.problem.parse_solution(raw_solution, instance_size)
        except ValueError:
            logger.warning(f"Generator {team} created a malformed solution at instance size!")
            raise

        if not self.problem.verify_solution(instance, instance_size, solution):
            logger.warning(f"Generator {team} failed due to a wrong certificate for its generated instance!")
            raise ValueError

        logger.info(f"Generated instance and certificate by group {team} are valid!")
        return instance, solution

    def _run_solver(self, team: Team, instance_size: int, instance: Instance) -> Solution:
        """Execute the solver of match.solving_team and check the validity of the generated output.

        If the validity checks pass, return the solver solution.

        Parameters
        ----------
        team : Team
            Solving team.
        instance_size : int
            The instance size, expected to be a positive int.
        instance : Instance
            The generated instance.

        Returns
        -------
        Solution
            The solver's solution.

        Raises
        ------
        ValueError
            If no solution can be generated
        """
        if self.docker_config.space_solver is not None:
            scaled_memory = self.problem.solver_memory_scaler(self.docker_config.space_solver, instance_size)
        else:
            scaled_memory = None
        instance_str = self.problem.encode_instance(instance)

        logger.debug(f"Running solver of group {team}...")
        try:
            output = team.solver.run(
                instance_str, timeout=self.docker_config.timeout_solver, memory=scaled_memory, cpus=self.docker_config.cpus
            )
        except DockerError:
            logger.warning(f"Solver of team '{team}' didn't run successfully!")
            raise ValueError

        if not output:
            logger.warning(f"No output was generated when running the solver of group {team}!")
            raise ValueError

        logger.debug("Checking validity of the solvers solution...")
        try:
            solution = self.problem.parse_solution(output.splitlines(), instance_size)
        except ValueError:
            logger.warning(f"Solver of group {team} created a malformed solution at instance size {instance_size}!")
            raise

        if not self.problem.verify_solution(instance, instance_size, solution):
            logger.warning(f"Solver of group {team} yields a wrong solution at instance size {instance_size}!")
            raise ValueError

        return solution