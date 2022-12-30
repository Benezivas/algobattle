"""Class managing the execution of generators and solvers."""
from __future__ import annotations
from dataclasses import dataclass, field
import logging
from typing import Any, Generic, TypeGuard, TypeVar

from algobattle.docker_util import DockerError
from algobattle.team import Matchup, Team
from algobattle.problem import Instance, Problem, ProblemData, Solution
from algobattle.util import TempDir

logger = logging.getLogger("algobattle.fight_handler")


_T = TypeVar("_T", bound=ProblemData)
_Instance, _Solution = TypeVar("_Instance", bound=Instance), TypeVar("_Solution", bound=Solution[Any])


@dataclass
class Result(Generic[_T]):
    """Result of a single generator or solver execution."""
    data: _T
    time: float


class FightError(Exception):
    """Raised when a team's program doesn't generate valid output."""


class InvalidOutput(FightError):
    """Indicates that the created instance or solution is invalid."""
    pass


@dataclass
class FightResult(Generic[_Instance, _Solution]):
    """The result of a single fight."""
    score: float
    generator: Result[_Instance] | FightError
    solver: Result[_Solution] | FightError | None

def generator_success(result: FightResult[_Instance, _Solution]) -> TypeGuard[GeneratorSuccess[_Instance, _Solution]]:
    """Checks whether both programs ran successfully."""
    return isinstance(result.generator, Result)

def is_success(result: FightResult[_Instance, _Solution]) -> TypeGuard[Success[_Instance, _Solution]]:
    """Checks whether both programs ran successfully."""
    return isinstance(result.solver, Result)

@dataclass
class GeneratorFailure(FightResult[_Instance, _Solution]):
    """The result of a fight where the generator didn't run successfully."""
    generator: FightError
    solver: None = field(default=None, init=False)


@dataclass
class GeneratorSuccess(FightResult[_Instance, _Solution]):
    """The result of a fight where the generator ran successfully."""
    generator: Result[_Instance]
    solver: Result[_Solution] | FightError


@dataclass
class Success(FightResult[_Instance, _Solution]):
    """The result of a fight were both programs ran successfully."""
    generator: Result[_Instance]
    solver: Result[_Solution]


@dataclass(kw_only=True)
class FightHandler(Generic[_Instance, _Solution]):
    """Class managing the execution of generators and solvers."""

    problem: Problem[_Instance, _Solution]
    matchup: Matchup
    timeout_generator: float | None = None
    timeout_solver: float | None = None
    space_generator: int | None = None
    space_solver: int | None = None
    cpus: int = 1

    def fight(self, size: int, timeout_generator: float | None = ..., space_genrator: int | None = ..., timeout_solver: float | None = ..., space_solver: int | None = ..., cpus: int = ...) -> FightResult[_Instance, _Solution]:
        """Execute a single fight of a battle, running the generator and solver and handling any errors gracefully."""
        try:
            gen_result = self.generate(size=size, timeout=timeout_generator, space=space_genrator, cpus=cpus)
        except FightError as e:
            return GeneratorFailure(score=1, generator=e)

        try:
            sol_result = self.solve(size=size, timeout=timeout_solver, space=space_solver, cpus=cpus)
        except FightError as e:
            return GeneratorSuccess(score=1, generator=gen_result, solver=e)

        score = self.problem.calculate_score(gen_result.data, sol_result.data)
        logger.info(f"Solver of group {self.matchup.generator} yields a valid solution with an approx. ratio of {score}.")
        return Success(score, gen_result, sol_result)

    def generate(self, size: int, timeout: float | None = ..., space: int | None = ..., cpus: int = ...) -> Result[_Instance]:
        """Execute the generator and process its output."""
        logger.debug(f"Running generator of team {self.matchup.generator}.")
        if timeout is ellipsis:
            timeout = self.timeout_generator
        if space is ellipsis:
            space = self.space_generator
        if cpus is ellipsis:
            cpus = self.cpus

        with TempDir() as input, TempDir() as output:
            with open(input / "size") as f:
                f.write(str(size))

            try:
                runtime = self.matchup.generator.generator.run(input, output, timeout=timeout, memory=space, cpus=cpus)
            except ExecutionError as e:
                logger.warning(f"Generator of team '{self.matchup.generator}' crashed!")
                return Failure("execution", time=e.time)
            except DockerError:
                logger.warning(f"Generator of team '{self.matchup.generator}' couldn't be executed successfully!")
                return Failure("execution", time=-1)

            

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

    def solve(self, size: int, timeout: float | None = ..., space: int | None = ..., cpus: int = ...) -> Result[_Solution]:
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
            raise RuntimeError

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
