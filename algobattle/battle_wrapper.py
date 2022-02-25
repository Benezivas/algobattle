"""Base class for wrappers that execute a specific kind of battle.

The battle wrapper class is a base class for specific wrappers, which are
responsible for executing specific types of battle. They share the
characteristic that they are responsible for updating some match data during
their run, such that it contains the current state of the match.
"""
from __future__ import annotations
from dataclasses import dataclass
import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Generator
from algobattle.matchups import Matchup
from algobattle.problem import Problem
from algobattle.team import Team
from algobattle.docker import DockerError
from algobattle.ui import Ui
if TYPE_CHECKING:
    from algobattle.match import Match, RunParameters


logger = logging.getLogger('algobattle.battle_wrapper')


class BattleWrapper(ABC):
    """Base class for wrappers that execute a specific kind of battle.
    Its state contains information about the battle and its history."""

    class Result:
        pass
    
    def __init__(self, problem: Problem, run_parameters: RunParameters = RunParameters(), **options: Any):
        """Builds a battle wrapper object with the given option values.
        Logs warnings if there were options provided that this wrapper doesn't use. 

        Parameters
        ----------
        match: Match
            The match object this wrapper will be used for.
        problem: str
            The problem this wrapper will be used for.
        rounds: int
            The number of rounds that will be executed.
        options: dict[str, Any]
            Dict containing option values.
        """
        self.problem = problem
        self.run_parameters = run_parameters

        self.error: str | None = None

        for arg, value in options.items():
            if arg not in vars(type(self)):
                logger.warning(f"Option '{arg}={value}' was provided, but is not used by {type(self)} type battles.")

    @abstractmethod
    def wrapper(self, matchup: Matchup) -> Generator[BattleWrapper.Result, None, None]:
        """The main base method for a wrapper.

        A wrapper should update the match.match_data object during its run. The callback functionality
        around it is executed automatically.

        It is assumed that the match.generating_team and match.solving_team are
        set before calling a wrapper.

        Parameters
        ----------
        match: Match
            The Match object on which the battle wrapper is to be executed on.
        """
        raise NotImplementedError
    
    def _one_fight(self, matchup: Matchup, instance_size: int) -> float:
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
        instance, generator_solution = self._run_generator(matchup.generator, instance_size)

        if not instance and not generator_solution:
            return 1.0

        solver_solution = self._run_solver(matchup.solver, instance_size, instance)

        if not solver_solution:
            return 0.0

        approximation_ratio = self.problem.verifier.calculate_approximation_ratio(instance, instance_size,
                                                                                  generator_solution, solver_solution)
        logger.info(f'Solver of group {matchup.solver} yields a valid solution with an approx. ratio of {approximation_ratio}.')
        return approximation_ratio

    def _run_generator(self, team: Team, instance_size: int) -> tuple[Any, Any]:
        """Execute the generator of match.generating_team and check the validity of the generated output.

        If the validity checks pass, return the instance and the certificate solution.

        Parameters
        ----------
        instance_size : int
            The instance size, expected to be a positive int.

        Returns
        -------
        any, any
            If the validity checks pass, the (instance, solution) in whatever
            format that is specified, else (None, None).
        """
        assert team.generator is not None
        scaled_memory = self.problem.generator_memory_scaler(self.run_parameters.space_generator, instance_size)

        logger.debug(f'Running generator of group {team}...\n')
        try:
            output = team.generator.run(str(instance_size), timeout=self.run_parameters.timeout_generator, memory=scaled_memory, cpus=self.run_parameters.cpus)
        except DockerError:
            return None, None

        if not output:
            logger.warning(f'No output was generated when running {team.generator}!')
            return None, None

        raw_instance_with_solution = self.problem.parser.decode(output)

        logger.debug('Checking generated instance and certificate...')

        raw_instance, raw_solution = self.problem.parser.split_into_instance_and_solution(raw_instance_with_solution)
        instance                   = self.problem.parser.parse_instance(raw_instance, instance_size)
        generator_solution         = self.problem.parser.parse_solution(raw_solution, instance_size)

        if not self.problem.verifier.verify_semantics_of_instance(instance, instance_size):
            logger.warning(f'Generator {team} created a malformed instance!')
            return None, None

        if not self.problem.verifier.verify_semantics_of_solution(generator_solution, instance_size, True):
            logger.warning(f'Generator {team} created a malformed solution at instance size!')
            return None, None

        if not self.problem.verifier.verify_solution_against_instance(instance, generator_solution, instance_size, True):
            logger.warning(f'Generator {team} failed due to a wrong certificate for its generated instance!')
            return None, None

        self.problem.parser.postprocess_instance(instance, instance_size)

        logger.info(f'Generated instance and certificate by group {team} are valid!\n')

        return instance, generator_solution

    def _run_solver(self, team: Team, instance_size: int, instance: Any) -> Any:
        """Execute the solver of match.solving_team and check the validity of the generated output.

        If the validity checks pass, return the solver solution.

        Parameters
        ----------
        instance_size : int
            The instance size, expected to be a positive int.

        Returns
        -------
        any
            If the validity checks pass, solution in whatever
            format that is specified, else None.
        """
        assert team.solver is not None
        scaled_memory = self.problem.solver_memory_scaler(self.run_parameters.space_solver, instance_size)
        instance_str = self.problem.parser.encode(instance)

        logger.debug(f'Running solver of group {team}...\n')
        try:
            output = team.solver.run(instance_str, timeout=self.run_parameters.timeout_solver, memory=scaled_memory, cpus=self.run_parameters.cpus)
        except DockerError:
            return None
        
        if not output:
            logger.warning(f'No output was generated when running the solver of group {team}!')
            return None

        raw_solver_solution = self.problem.parser.decode(output)

        logger.debug('Checking validity of the solvers solution...')

        solver_solution = self.problem.parser.parse_solution(raw_solver_solution, instance_size)
        if not self.problem.verifier.verify_semantics_of_solution(solver_solution, instance_size, True):
            logger.warning(f'Solver of group {team} created a malformed solution at instance size {instance_size}!')
            return None
        elif not self.problem.verifier.verify_solution_against_instance(instance, solver_solution, instance_size, False):
            logger.warning(f'Solver of group {team} yields a wrong solution at instance size {instance_size}!')
            return None

        return solver_solution

    @abstractmethod
    def calculate_points(self, achievable_points: int) -> dict[Team, float]:
        """Calculate the number of achieved points, given results.

        As awarding points completely depends on the type of battle that
        was fought, each wrapper should implement a method that determines
        how to split up the achievable points among all teams.

        Parameters
        ----------
        achievable_points : int
            Number of achievable points.

        Returns
        -------
        dict
            A mapping between team names and their achieved points.
            The format is {team_name: points [...]} for each
            team for which there is an entry in match_data and points is a
            float value. Returns an empty dict if no battle was fought.
        """
        raise NotImplementedError

    def format_as_utf8(self) -> str:
        """Format the match_data for the battle wrapper as a UTF-8 string.

        The output should not exceed 80 characters, assuming the default
        of a battle of 5 rounds.

        Returns
        -------
        str
            A formatted string on the basis of the match_data.
        """
        formatted_output_string = ""

        formatted_output_string += f'Battles of type {type(self).__name__} are currently not compatible with the ui.'
        formatted_output_string += f'Here is a dump of the battle wrapper object anyway:\n{self}'

        return formatted_output_string
    