"""Class managing the execution of generators and solvers."""
import logging
from configparser import ConfigParser
from typing import Any, Tuple
from algobattle.docker_wrapper import DockerError

from algobattle.team import Matchup, Team
from algobattle.problem import Problem

logger = logging.getLogger("algobattle.fight_handler")


class FightHandler:
    """Class managing the execution of generators and solvers."""

    def __init__(self, problem: Problem, config: ConfigParser) -> None:
        self.timeout_generator = int(config["run_parameters"]["timeout_generator"])
        self.timeout_solver = int(config["run_parameters"]["timeout_solver"])
        self.space_generator = int(config["run_parameters"]["space_generator"])
        self.space_solver = int(config["run_parameters"]["space_solver"])
        self.cpus = int(config["run_parameters"]["cpus"])
        self.problem = problem

    def fight(self, matchup: Matchup, instance_size: int) -> float:
        """Execute a single fight of a battle between a given generator and solver for a given instance size.

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
        except RuntimeError:
            return 1.0

        try:
            solver_solution = self._run_solver(matchup.solver, instance_size, instance)
        except RuntimeError:
            return 0

        approximation_ratio = self.problem.verifier.calculate_approximation_ratio(
            instance, instance_size, generator_solution, solver_solution
        )
        logger.info(
            f"Solver of group {matchup.generator} yields a valid solution with an approx. ratio of {approximation_ratio}."
        )
        return approximation_ratio

    def _run_generator(self, team: Team, instance_size: int) -> Tuple[Any, Any]:
        """Execute the generator of `team` and check the validity of the generated output.

        If the validity checks pass, return the instance and the certificate solution.

        Parameters
        ----------
        instance_size : int
            The instance size, expected to be a positive int.

        Returns
        -------
        Any, Any
            If the validity checks pass, the (instance, solution) in whatever
            format that is specified

        Raises
        ------
        RuntimeError
            If the container doesn't run successfully or any of the checks don't pass
        """
        scaled_memory = self.problem.generator_memory_scaler(self.space_generator, instance_size)

        logger.debug(f"Running generator of group {team}...\n")

        try:
            encoded_output = team.generator.run(str(instance_size), self.timeout_generator, scaled_memory, self.cpus)
        except DockerError:
            logger.warning(f"Generator of team '{team}' didn't run successfully!")
            raise RuntimeError

        if not encoded_output:
            logger.warning(f"No output was generated when running the generator group {team}!")
            raise RuntimeError

        raw_instance_with_solution = self.problem.parser.decode(encoded_output)

        logger.debug("Checking generated instance and certificate...")

        raw_instance, raw_solution = self.problem.parser.split_into_instance_and_solution(raw_instance_with_solution)
        instance = self.problem.parser.parse_instance(raw_instance, instance_size)
        generator_solution = self.problem.parser.parse_solution(raw_solution, instance_size)

        if not self.problem.verifier.verify_semantics_of_instance(instance, instance_size):
            logger.warning("Generator {} created a malformed instance!".format(team))
            raise RuntimeError

        if not self.problem.verifier.verify_semantics_of_solution(generator_solution, instance_size, True):
            logger.warning("Generator {team} created a malformed solution at instance size!")
            raise RuntimeError

        if not self.problem.verifier.verify_solution_against_instance(instance, generator_solution, instance_size, True):
            logger.warning(f"Generator {team} failed due to a wrong certificate for its generated instance!")
            raise RuntimeError

        self.problem.parser.postprocess_instance(instance, instance_size)

        logger.info(f"Generated instance and certificate by group {team} are valid!\n")

        return instance, generator_solution

    def _run_solver(self, team: Team, instance_size: int, instance: Any) -> Any:
        """Execute the solver of `team` and check the validity of the generated output.

        If the validity checks pass, return the solver solution.

        Parameters
        ----------
        instance_size : int
            The instance size, expected to be a positive int.

        Returns
        -------
        any
            If the validity checks pass, solution in whatever
            format that is specified.

        Raises
        ------
        RuntimeError
            If the container doesn't run successfully or any of the checks don't pass
        """
        scaled_memory = self.problem.solver_memory_scaler(self.space_solver, instance_size)
        try:
            encoded_output = team.solver.run(
                self.problem.parser.encode(instance), self.timeout_solver, scaled_memory, self.cpus
            )
        except DockerError:
            logger.warning(f"Solver of team '{team}' didn't run successfully!")
            raise RuntimeError

        if not encoded_output:
            logger.warning(f"No output was generated when running the solver of group {team}!")
            raise ValueError

        raw_solver_solution = self.problem.parser.decode(encoded_output)

        logger.debug("Checking validity of the solvers solution...")

        solver_solution = self.problem.parser.parse_solution(raw_solver_solution, instance_size)
        if not self.problem.verifier.verify_semantics_of_solution(solver_solution, instance_size, True):
            logger.warning(f"Solver of group {team} created a malformed solution at instance size {instance_size}!")
            raise RuntimeError
        elif not self.problem.verifier.verify_solution_against_instance(instance, solver_solution, instance_size, False):
            logger.warning(f"Solver of group {team} yields an incorrect solution at instance size {instance_size}!")
            raise RuntimeError

        return solver_solution
