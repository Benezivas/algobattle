"""Match class, provides functionality for setting up and executing battles between given teams."""
from __future__ import annotations

import logging
import configparser
from pathlib import Path
from collections.abc import Mapping
from algobattle.battle_wrapper import BattleWrapper
from algobattle.matchups import BattleMatchups

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

    def __init__(self, problem: Problem, config_path: Path, team_info: list[tuple[str, Path, Path]], ui: Ui | None = None,
                 runtime_overhead: float = 0, approximation_ratio: float = 1.0, cache_docker_containers: bool = True) -> None:

        config = configparser.ConfigParser()
        logger.debug(f'Using additional configuration options from file "{config_path}".')
        config.read(config_path)

        self.run_parameters = RunParameters(config["run_parameters"], runtime_overhead)
        self.problem = problem
        self.config = config
        self.approximation_ratio = approximation_ratio
        self.ui = ui
        
        if approximation_ratio != 1.0 and not problem.approximable:
            logger.error('The given problem is not approximable and can only be run with an approximation ratio of 1.0!')
            raise ConfigurationError

        self.teams: list[Team] = []
        for info in team_info:
            try:
                self.teams.append(Team(*info, timeout_build=self.run_parameters.timeout_build, cache_container=cache_docker_containers))
            except DockerError:
                logger.error(f"Removing team {info[0]} as their containers did not build successfully.")
            except ValueError as e:
                logger.error(f"Team name '{info[0]}' is used twice!")
                raise TypeError from e
        if len(self.teams) == 0:
            logger.critical("None of the team's containers built successfully.")
            raise BuildError()
        
        self.battle_matchups = BattleMatchups(self.teams)

    def run(self, battle_type: str = 'iterated', rounds: int = 5, iterated_cap: int = 50000, iterated_exponent: int = 2,
            approximation_instance_size: int = 10, approximation_iterations: int = 25) -> BattleWrapper.MatchResult:
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
            res = Iterated.Result
            battle_wrapper = Iterated(self.problem, self.run_parameters, iterated_cap, iterated_exponent, self.approximation_ratio)
        elif battle_type == 'averaged':
            res = Averaged.Result
            battle_wrapper = Averaged(self.problem, self.run_parameters, approximation_instance_size, approximation_iterations)
        else:
            logger.error(f'Unrecognized battle_type given: "{battle_type}"')
            raise UnknownBattleType
        
        results: BattleWrapper.MatchResult[res] = type(battle_wrapper).MatchResult(self.battle_matchups, rounds)

        if self.ui is not None:
            self.ui.update(results.format())
        
        for matchup in self.battle_matchups:
            for i in range(rounds):
                logger.info(f'{"#" * 20}  Running Battle {i + 1}/{rounds}  {"#" * 20}')
        
                for result in battle_wrapper.wrapper(matchup):
                    results[matchup][i] = result
                    if self.ui is not None:
                        self.ui.update(results.format())


        return results

    def cleanup(self) -> None:
        for team in self.teams:
            if team.generator is not None:
                team.generator.remove()
            if team.solver is not None:
                team.solver.remove()
