"""Match class, provides functionality for setting up and executing battles between given teams."""
from __future__ import annotations

import logging
from configparser import SectionProxy
from pathlib import Path
from collections.abc import Mapping
from typing import Any

from algobattle.battle_wrapper import BattleWrapper
from algobattle.battle_wrappers import get_battle_wrapper
from algobattle.team import Team, BattleMatchups
from algobattle.problem import Problem
from algobattle.docker import DockerError
from algobattle.ui import Ui


logger = logging.getLogger('algobattle.match')

class BuildError(Exception):
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

    def __init__(self, problem: Problem, config: SectionProxy, team_info: list[tuple[str, Path, Path]], ui: Ui | None = None,
                 runtime_overhead: float = 0, cache_docker_containers: bool = True) -> None:

        self.run_parameters = RunParameters(config, runtime_overhead)
        self.problem = problem
        self.config = config
        self.ui = ui

        self.teams: list[Team] = []
        for info in team_info:
            try:
                self.teams.append(Team(*info, timeout_build=self.run_parameters.timeout_build, cache_container=cache_docker_containers))
            except DockerError:
                logger.error(f"Removing team {info[0]} as their containers did not build successfully.")
            except ValueError as e:
                logger.error(f"Team name '{info[0]}' is used twice!")
                raise ValueError from e
        if len(self.teams) == 0:
            logger.critical("None of the team's containers built successfully.")
            raise BuildError()
        
        self.battle_matchups = BattleMatchups(self.teams)

    def run(self, battle_type: str = 'iterated', rounds: int = 5, **wrapper_options: dict[str, Any]) -> BattleWrapper.MatchResult:
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

        WrapperClass = get_battle_wrapper(battle_type)
        ResultClass = WrapperClass.Result

        if not WrapperClass.check_compatibility(self.problem, wrapper_options):
            logger.critical(f"Battle type, problem, and chosen options are incompatible!")
            raise SystemExit

        battle_wrapper = WrapperClass(self.problem, self.run_parameters, **wrapper_options)
        
        results = WrapperClass.MatchResult(self.battle_matchups, rounds)    # type: ignore

        if self.ui is not None:
            self.ui.update(results.format())
        
        for matchup in self.battle_matchups:
            for i in range(rounds):
                logger.info(f'{"#" * 20}  Running Battle {i + 1}/{rounds}  {"#" * 20}')
                results[matchup].append(ResultClass())

                for result in battle_wrapper.wrapper(matchup):
                    results[matchup][i] = result
                    if self.ui is not None:
                        self.ui.update(results.format())


        return results

    def cleanup(self) -> None:
        for team in self.teams:
            team.cleanup()
