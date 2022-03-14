"""Match class, provides functionality for setting up and executing battles between given teams."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Type

from algobattle.battle_style import BattleStyle
from algobattle.fight import Fight
from algobattle.team import Team, BattleMatchups
from algobattle.problem import Problem
from algobattle.docker import DockerConfig, DockerError
from algobattle.ui import Ui


logger = logging.getLogger("algobattle.match")


class Match:
    """Match class, provides functionality for setting up and executing battles between given teams."""

    def __init__(
        self, problem: Problem, docker_config: DockerConfig, team_info: list[tuple[str, Path, Path]], ui: Ui | None = None
    ) -> None:

        self.problem = problem
        self.ui = ui
        self.docker_config = docker_config

        self.teams: list[Team] = []
        for info in team_info:
            try:
                self.teams.append(
                    Team(*info, timeout_build=docker_config.timeout_build, cache_container=docker_config.cache_containers)
                )
            except DockerError:
                logger.error(f"Removing team {info[0]} as their containers did not build successfully.")
            except ValueError as e:
                logger.error(f"Team name '{info[0]}' is used twice!")
                raise ValueError from e
        if len(self.teams) == 0:
            logger.critical("None of the teams containers built successfully.")
            raise SystemExit

        self.battle_matchups = BattleMatchups(self.teams)

    def run(
        self, battle_style: Type[BattleStyle], rounds: int = 5, **battle_options: dict[str, Any]
    ) -> BattleStyle.MatchResult:
        """Match entry point, executes rounds fights between all teams and returns the results of the battles.

        Parameters
        ----------
        battle_style : str
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
        BattleStyle
            A battle style instance containing information about the executed battle.
        """
        fight = Fight(self.problem, self.docker_config)
        battle = battle_style(self.problem, fight, **battle_options)
        results = battle.MatchResult(self.battle_matchups, rounds)  # type: ignore

        if self.ui is not None:
            self.ui.update(results.format())

        for matchup in self.battle_matchups:
            for i in range(rounds):
                logger.info(f'{"#" * 20}  Running Battle {i + 1}/{rounds}  {"#" * 20}')
                results[matchup].append(battle.Result())

                for result in battle.run(matchup):
                    results[matchup][i] = result
                    if self.ui is not None:
                        self.ui.update(results.format())

        return results

    def cleanup(self) -> None:
        for team in self.teams:
            team.cleanup()
