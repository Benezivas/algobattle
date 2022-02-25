"""Match class, provides functionality for setting up and executing battles between given teams."""
from __future__ import annotations
from dataclasses import dataclass
import itertools

import logging
import configparser
from pathlib import Path
from typing import Mapping
from algobattle.battle_wrapper import BattleWrapper
from algobattle.matchups import BattleMatchups, Matchup

from algobattle.team import Team
from algobattle.problem import Problem
from algobattle.docker import DockerError, Image
from algobattle.battle_wrappers.averaged import Averaged
from algobattle.battle_wrappers.iterated import Iterated
from algobattle.ui import Ui

logger = logging.getLogger('algobattle.match')

class ConfigurationError(Exception):
    pass

class BuildError(Exception):
    pass

class UnknownBattleType(Exception):
    pass

class RunParameters:
    def __init__(self, config: Mapping[str, str] = {}, runtime_overhead: float = 0) -> None:
        def __access(key: str) -> int | None:
            if key in config.keys():
                return int(config[key])
            else:
                return None
        def __map(i: int | None, x: float) -> float | None:
            if i is not None:
                return i + x
            else:
                return None

        self.timeout_build      = __map(__access('timeout_build'), runtime_overhead)
        self.timeout_generator  = __map(__access('timeout_generator'), runtime_overhead)
        self.timeout_solver     = __map(__access('timeout_solver'), runtime_overhead)
        self.space_generator    = __access('space_generator')
        self.space_solver       = __access('space_solver')
        self.cpus               = __access('cpus')


class Match:
    """Match class, provides functionality for setting up and executing battles between given teams."""

    def __init__(self, problem: Problem, config_path: Path, teams: list[Team], ui: Ui | None = None,
                 runtime_overhead: float = 0, approximation_ratio: float = 1.0, cache_docker_containers: bool = True) -> None:

        config = configparser.ConfigParser()
        logger.debug(f'Using additional configuration options from file "{config_path}".')
        config.read(config_path)

        self.run_parameters = RunParameters(config["run_parameters"], runtime_overhead)
        self.problem = problem
        self.config = config
        self.approximation_ratio = approximation_ratio
        self.ui = ui
        self.battle_matchups = BattleMatchups(teams)
        
        if approximation_ratio != 1.0 and not problem.approximable:
            logger.error('The given problem is not approximable and can only be run with an approximation ratio of 1.0!')
            raise ConfigurationError
        
        self.results: dict[Matchup, list[BattleWrapper.Result]] = {}
        for matchup in self.battle_matchups:
            self.results[matchup] = []

        self._build(teams, cache_docker_containers)

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
                team.generator = Image(team.generator_path, f"generator-{team.name}", f"generator for team {team.name}", timeout=self.run_parameters.timeout_build, cache=cache_docker_containers)
                team.solver = Image(team.solver_path, f"solver-{team.name}", f"solver for team {team.name}", timeout=self.run_parameters.timeout_build, cache=cache_docker_containers)
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
            self.battle_wrapper = Iterated(self.problem, self.run_parameters, iterated_cap, iterated_exponent, self.approximation_ratio)
        elif battle_type == 'averaged':
            self.battle_wrapper = Averaged(self.problem, self.run_parameters, approximation_instance_size, approximation_iterations)
        else:
            logger.error(f'Unrecognized battle_type given: "{battle_type}"')
            raise UnknownBattleType

        for matchup in self.battle_matchups:
            for i in range(rounds):
                logger.info(f'{"#" * 20}  Running Battle {i + 1}/{rounds}  {"#" * 20}')
                self.results[matchup].append(self.battle_wrapper.Result())
                if self.ui is not None:
                    self.ui.update()
                for result in self.battle_wrapper.wrapper(matchup):
                    self.results[matchup][i] = result
                    if self.ui is not None:
                        self.ui.update()


        return self.battle_wrapper

    def format_as_utf8(self) -> str:
        assert self.battle_wrapper is not None
        return self.battle_wrapper.format_as_utf8()

    def cleanup(self) -> None:
        for team in self.teams:
            if team.generator is not None:
                team.generator.remove()
            if team.solver is not None:
                team.solver.remove()
