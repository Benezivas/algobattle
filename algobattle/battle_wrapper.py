from __future__ import annotations
"""Base class for wrappers that execute a specific kind of battle.

The battle wrapper class is a base class for specific wrappers, which are
responsible for executing specific types of battle. They share the
characteristic that they are responsible for updating some match data during
their run, such that it contains the current state of the match.
"""
import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Generator, Generic, Type, TypeVar
from inspect import isabstract

from algobattle.problem import Problem
from algobattle.team import Team, BattleMatchups, Matchup
from algobattle.docker import DockerError
if TYPE_CHECKING:
    from algobattle.match import RunParameters

logger = logging.getLogger('algobattle.battle_wrapper')

Instance = TypeVar("Instance")
Solution = TypeVar("Solution")
class BattleWrapper(ABC, Generic[Instance, Solution]):
    """Base class for wrappers that execute a specific kind of battle.
    Its state contains information about the battle and its history."""

    battle_args: list[tuple[list[str], dict[str, Any]]] = []
    
    wrapper_classes: dict[str, Type[BattleWrapper]] = {}
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if not isabstract(cls):
            BattleWrapper.wrapper_classes[cls.__name__.lower()] = cls

    def __init__(self, problem: Problem[Instance, Solution], run_parameters: RunParameters | None = None, **options: dict[str, Any]):
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
        if run_parameters is not None:
            self.run_parameters = run_parameters
        else:
            from algobattle.match import RunParameters
            self.run_parameters = RunParameters()
    
    @staticmethod
    def getWrapperClass(battle_type: str) -> Type[BattleWrapper]:
        if battle_type.lower() in BattleWrapper.wrapper_classes.keys():
            return BattleWrapper.wrapper_classes[battle_type]
        else:
            logger.error(f'Unrecognized battle_type given: "{battle_type}"')
            raise ValueError

    @classmethod
    def check_compatibility(cls, problem: Problem, options: dict[str, Any]) -> bool:
        return True
    
    @abstractmethod
    def wrapper(self, matchup: Matchup) -> Generator[Result, None, None]:
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
        try:
            instance, generator_solution = self._run_generator(matchup.generator, instance_size)
        except ValueError:
            return self.problem.approx_cap

        try:
            solver_solution = self._run_solver(matchup.solver, instance_size, instance)
        except ValueError:
            return 0

        approximation_ratio = self.problem.approximation_ratio(instance, instance_size, generator_solution, solver_solution)
        logger.info(f'Solver of group {matchup.solver} yields a valid solution with an approx. ratio of {approximation_ratio}.')
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
        if self.run_parameters.space_generator is not None:
            scaled_memory = self.problem.generator_memory_scaler(self.run_parameters.space_generator, instance_size)
        else:
            scaled_memory = None

        logger.debug(f'Running generator of group {team}...')
        try:
            output = team.generator.run(str(instance_size), timeout=self.run_parameters.timeout_generator, memory=scaled_memory, cpus=self.run_parameters.cpus)
        except DockerError:
            logger.warning(f"generator of team '{team}' didn't run successfully!")
            raise ValueError

        if not output:
            logger.warning(f'No output was generated when running {team.generator}!')
            raise ValueError

        logger.debug('Checking generated instance and certificate...')
        raw_instance, raw_solution = self.problem.split(output)
        try:
            instance = self.problem.parse_instance(raw_instance, instance_size)
        except ValueError:
            logger.warning(f'Generator {team} created a malformed instance!')
            raise
        
        try:
            solution = self.problem.parse_solution(raw_solution, instance_size)
        except ValueError:
            logger.warning(f'Generator {team} created a malformed solution at instance size!')
            raise

        if not self.problem.verify_solution(instance, instance_size, solution):
            logger.warning(f'Generator {team} failed due to a wrong certificate for its generated instance!')
            raise ValueError

        logger.info(f'Generated instance and certificate by group {team} are valid!')
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
        if self.run_parameters.space_solver is not None:
            scaled_memory = self.problem.solver_memory_scaler(self.run_parameters.space_solver, instance_size)
        else:
            scaled_memory = None
        instance_str = self.problem.encode_instance(instance)

        logger.debug(f'Running solver of group {team}...')
        try:
            output = team.solver.run(instance_str, timeout=self.run_parameters.timeout_solver, memory=scaled_memory, cpus=self.run_parameters.cpus)
        except DockerError:
            logger.warning(f"Solver of team '{team}' didn't run successfully!")
            raise ValueError
        
        if not output:
            logger.warning(f'No output was generated when running the solver of group {team}!')
            raise ValueError

        logger.debug('Checking validity of the solvers solution...')
        try:
            solution = self.problem.parse_solution(output.splitlines(), instance_size)
        except ValueError:
            logger.warning(f'Solver of group {team} created a malformed solution at instance size {instance_size}!')
            raise

        if not self.problem.verify_solution(instance, instance_size, solution):
            logger.warning(f'Solver of group {team} yields a wrong solution at instance size {instance_size}!')
            raise ValueError

        return solution

    class Result:
        pass

    Res = TypeVar("Res", covariant=True, bound=Result)
    class MatchResult(dict[Matchup, list[Res]], ABC):

        def __init__(self, matchups: BattleMatchups, rounds: int) -> None:
            self.rounds = rounds
            for matchup in matchups:
                self[matchup] = []
        
        def format(self) -> str:
            """Format the match_data for the battle wrapper as a UTF-8 string.

            The output should not exceed 80 characters, assuming the default
            of a battle of 5 rounds.

            Returns
            -------
            str
                A formatted string on the basis of the match_data.
            """

            formatted_output_string = f"Battles of this type are currently not compatible with the ui.\n"
            formatted_output_string += "Here is a dump of the result objects anyway:\n"
            formatted_output_string += "\n".join(f"{matchup}: {res}" for (matchup, res) in self.items())

            return formatted_output_string
        
        def __str__(self) -> str:
            return self.format()

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
