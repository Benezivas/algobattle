"""Match class, provides functionality for setting up and executing battles between given teams."""
from __future__ import annotations
import itertools

import logging
import configparser
from pathlib import Path
from typing import Any
from algobattle.battle_wrapper import BattleWrapper

from algobattle.team import Team
from algobattle.problem import Problem
from algobattle.util import team_roles_set
from algobattle.docker import DockerError, Image
from algobattle.subject import Subject
from algobattle.observer import Observer
from algobattle.battle_wrappers.averaged import Averaged
from algobattle.battle_wrappers.iterated import Iterated

logger = logging.getLogger('algobattle.match')

class ConfigurationError(Exception):
    pass

class BuildError(Exception):
    pass

class UnknownBattleType(Exception):
    pass

class Match(Subject):
    """Match class, provides functionality for setting up and executing battles between given teams."""

    _observers: list[Observer] = []
    generating_team = None
    solving_team = None
    battle_wrapper = None

    def __init__(self, problem: Problem, config_path: Path, teams: list[Team],
                 runtime_overhead: float = 0, approximation_ratio: float = 1.0, cache_docker_containers: bool = True) -> None:

        config = configparser.ConfigParser()
        logger.debug('Using additional configuration options from file "%s".', config_path)
        config.read(config_path)

        self.timeout_build           = int(config['run_parameters']['timeout_build']) + runtime_overhead
        self.timeout_generator       = int(config['run_parameters']['timeout_generator']) + runtime_overhead
        self.timeout_solver          = int(config['run_parameters']['timeout_solver']) + runtime_overhead
        self.space_generator         = int(config['run_parameters']['space_generator'])
        self.space_solver            = int(config['run_parameters']['space_solver'])
        self.cpus                    = int(config['run_parameters']['cpus'])
        self.problem = problem
        self.config = config
        self.approximation_ratio = approximation_ratio
        
        if approximation_ratio != 1.0 and not problem.approximable:
            logger.error('The given problem is not approximable and can only be run with an approximation ratio of 1.0!')
            raise ConfigurationError

        self._build(teams, cache_docker_containers)

    def attach(self, observer: Observer) -> None:
        """Subscribe a new Observer by adding them to the list of observers."""
        self._observers.append(observer)

    def detach(self, observer: Observer) -> None:
        """Unsubscribe an Observer by removing them from the list of observers."""
        self._observers.remove(observer)

    def notify(self) -> None:
        """Notify all subscribed Observers by calling their update() functions."""
        for observer in self._observers:
            observer.update(self)

    def _build(self, teams: list[Team], cache_docker_containers: bool=True) -> None:
        """Build docker containers for the given generators and solvers of each team.

        Any team for which either the generator or solver does not build successfully
        will be removed from the match.

        Parameters
        ----------
        teams : list
            List of Team objects.
        cache_docker_containers : bool
            Flag indicating whether to cache built docker containers.

        Returns
        -------
        Bool
            Boolean indicating whether the build process succeeded.
        """
        if not isinstance(teams, list) or any(not isinstance(team, Team) for team in teams):
            logger.error('Teams argument is expected to be a list of Team objects!')
            raise TypeError

        self.teams = teams
        if len(self.teams) != len(set(self.teams)):
            logger.error('At least one team name is used twice!')
            raise TypeError

        self.single_player = (len(teams) == 1)

        for team in teams:
            try:
                team.generator = Image(team.generator_path, f"generator-{team.name}", f"generator for team {team.name}", timeout=self.timeout_build, cache=cache_docker_containers)
                team.solver = Image(team.solver_path, f"solver-{team.name}", f"solver for team {team.name}", timeout=self.timeout_build, cache=cache_docker_containers)
            except DockerError:
                logger.error(f"Removing team {team.name} as their containers did not build successfully.")
                self.teams.remove(team)

        if len(self.teams) == 0:
            logger.critical("None of the team's containers built successfully.")
            raise BuildError()

    def all_battle_pairs(self) -> list[tuple[Team, Team]]:
        """Generate and return a list of all team pairings for battles."""
        if self.single_player:
            return [(self.teams[0], self.teams[0])]
        else:
            return list(itertools.permutations(self.teams, 2))

    def run(self, battle_type: str = 'iterated', rounds: int = 5, iterated_cap: int = 50000, iterated_exponent: int = 2,
            approximation_instance_size: int = 10, approximation_iterations: int = 25) -> BattleWrapper:
        """Match entry point, executes rounds fights between all teams and returns the results of the battles.

        Parameters
        ----------
        battle_type : str
            Type of battle that is to be run.
        rounds : int
            Number of Battles between each pair of teams (used for averaging results).
        iterated_cap : int
            Iteration cutoff after which an iterated battle is automatically stopped, declaring the solver as the winner.
        iterated_exponent : int
            Exponent used for increasing the step size in an iterated battle.
        approximation_instance_size : int
            Instance size on which to run an averaged battle.
        approximation_iterations : int
            Number of iterations for an averaged battle between two teams.

        Returns
        -------
        BattleWrapper
            A wrapper instance containing information about the executed battle.
        """

        if battle_type == 'iterated':
            self.battle_wrapper = Iterated(self, self.problem.name, rounds, iterated_cap, iterated_exponent)
        elif battle_type == 'averaged':
            self.battle_wrapper = Averaged(self, self.problem.name, rounds, approximation_instance_size, approximation_iterations)
        else:
            logger.error(f'Unrecognized battle_type given: "{battle_type}"')
            raise UnknownBattleType

        for pair in self.all_battle_pairs():
            self.battle_wrapper.curr_pair = pair
            for i in range(rounds):
                logger.info(f'{"#" * 20}  Running Battle {i + 1}/{rounds}  {"#" * 20}')
                self.battle_wrapper.curr_round = i

                self.battle_wrapper.wrapper(self, pair[0], pair[1])

        return self.battle_wrapper

    def _one_fight(self, generating: Team, solving: Team, instance_size: int) -> float:
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
        instance, generator_solution = self._run_generator(generating, instance_size)

        if not instance and not generator_solution:
            return 1.0

        solver_solution = self._run_solver(solving, instance_size, instance)

        if not solver_solution:
            return 0.0

        approximation_ratio = self.problem.verifier.calculate_approximation_ratio(instance, instance_size,
                                                                                  generator_solution, solver_solution)
        logger.info('Solver of group {} yields a valid solution with an approx. ratio of {}.'
                    .format(self.solving_team, approximation_ratio))
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
        scaled_memory = self.problem.generator_memory_scaler(self.space_generator, instance_size)

        logger.debug(f'Running generator of group {self.generating_team}...\n')
        try:
            output = team.generator.run(str(instance_size), timeout=self.timeout_generator, memory=scaled_memory, cpus=self.cpus)
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
            logger.warning(f'Generator {self.generating_team} created a malformed instance!')
            return None, None

        if not self.problem.verifier.verify_semantics_of_solution(generator_solution, instance_size, True):
            logger.warning(f'Generator {self.generating_team} created a malformed solution at instance size!')
            return None, None

        if not self.problem.verifier.verify_solution_against_instance(instance, generator_solution, instance_size, True):
            logger.warning(f'Generator {self.generating_team} failed due to a wrong certificate for its generated instance!')
            return None, None

        self.problem.parser.postprocess_instance(instance, instance_size)

        logger.info(f'Generated instance and certificate by group {self.generating_team} are valid!\n')

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
        scaled_memory = self.problem.solver_memory_scaler(self.space_solver, instance_size)
        instance_str = self.problem.parser.encode(instance)

        logger.debug(f'Running solver of group {self.solving_team}...\n')
        try:
            output = team.solver.run(instance_str, timeout=self.timeout_solver, memory=scaled_memory, cpus=self.cpus)
        except DockerError:
            return None
        
        if not output:
            logger.warning(f'No output was generated when running the solver of group {self.solving_team}!')
            return None

        raw_solver_solution = self.problem.parser.decode(output)

        logger.debug('Checking validity of the solvers solution...')

        solver_solution = self.problem.parser.parse_solution(raw_solver_solution, instance_size)
        if not self.problem.verifier.verify_semantics_of_solution(solver_solution, instance_size, True):
            logger.warning('Solver of group {} created a malformed solution at instance size {}!'
                           .format(self.solving_team, instance_size))
            return None
        elif not self.problem.verifier.verify_solution_against_instance(instance, solver_solution, instance_size, False):
            logger.warning('Solver of group {} yields a wrong solution at instance size {}!'
                           .format(self.solving_team, instance_size))
            return None

        return solver_solution

    def format_as_utf8(self) -> str:
        assert self.battle_wrapper is not None
        return self.battle_wrapper.format_as_utf8()

    def cleanup(self) -> None:
        for team in self.teams:
            if team.generator is not None:
                team.generator.remove()
            if team.solver is not None:
                team.solver.remove()
