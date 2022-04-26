"""Match class, provides functionality for setting up and executing battles between given teams."""
from __future__ import annotations
from collections import defaultdict
from itertools import combinations

import logging
from pathlib import Path
from typing import Any, Type

from algobattle.battle_style import BattleStyle
from algobattle.events import SharedSubject
from algobattle.fight import Fight
from algobattle.team import Team, MatchupInfo, Matchup
from algobattle.problem import Problem
from algobattle.docker import DockerConfig, DockerError
from algobattle.util import format_table


logger = logging.getLogger("algobattle.match")


class Match(SharedSubject):
    """Match class, provides functionality for setting up and executing battles between given teams."""

    default_event = "match"

    def __init__(self, problem: Problem, docker_config: DockerConfig, team_info: list[tuple[str, Path, Path]]) -> None:
        """Creates a match instance.

        Parameters
        ----------
        problem : Problem
            The problem that the teams will have to solve.
        docker_config : DockerConfig
            Docker config used to build and run images.
        team_info : list[tuple[str, Path, Path]]
            For each team a name, path to their generator, and path to their solver.

        Raises
        ------
        ValueError
            If a team name is used twice.
        SystemExit
            If None of the teams containers built successfully.
        """
        super().__init__()
        self.problem = problem
        self.docker_config = docker_config

        self.teams: list[Team] = []
        for info in team_info:
            try:
                self.teams.append(
                    Team(*info, timeout_build=docker_config.timeout_build, cache_image=docker_config.cache_containers)
                )
            except DockerError:
                logger.error(f"Removing team {info[0]} as their containers did not build successfully.")
            except ValueError as e:
                logger.error(f"Team name '{info[0]}' is used twice!")
                raise ValueError from e
        if len(self.teams) == 0:
            logger.critical("None of the teams containers built successfully.")
            raise SystemExit

        self.battle_matchups = MatchupInfo(self.teams)

    def run(self, battle_style: Type[BattleStyle], rounds: int = 5, **battle_options: dict[str, Any]) -> MatchResult:
        """Executes a match.

        Parameters
        ----------
        battle_style : Type[BattleStyle]
            Type of battle that is to be run.
        rounds : int
            Number of Battles between each pair of teams (used for averaging results).
        iterated_cap : int
            Iteration cutoff after which an iterated battle is automatically stopped, declaring the solver as the winner.
        **battle_options : dict[str, Any]
            further options that will be passed to the battle style.

        Returns
        -------
        MatchResult
            The result of the match.
        """
        fight = Fight(self.problem, self.docker_config)
        battle = battle_style(self.problem, fight, **battle_options)
        results = MatchResult(self.battle_matchups, rounds)

        self.notify(results.format())

        for matchup in self.battle_matchups:
            for i in range(rounds):
                logger.info(f'{"#" * 20}  Running Battle {i + 1}/{rounds}  {"#" * 20}')
                result = battle.run(matchup)
                results[matchup].append(result)
                self.notify(results.format())

        return results

    def cleanup(self) -> None:
        """Removes all involved docker images."""
        for team in self.teams:
            team.cleanup()


class MatchResult(dict[Matchup, list[BattleStyle.Result]]):
    """The result of a whole match.

    Primarily a mapping of matchups to a list of Results, one per round.
    """

    def __init__(self, matchups: MatchupInfo, rounds: int) -> None:
        self.rounds = rounds
        self.matchups = matchups
        for matchup in matchups:
            self[matchup] = []

    def format(self) -> str:
        """Format the match_data for the battle battle style as a string.

        The output should not exceed 80 characters, assuming the default
        of a battle of 5 rounds.

        Returns
        -------
        str
            A formatted string on the basis of the match_data.
        """
        table = []
        table.append(["GEN", "SOL", *range(1, self.rounds + 1), "AVG"])

        for matchup, results in self.items():
            padding = [""] * (self.rounds - len(results))
            if len(results) == 0:
                avg = ""
            else:
                avg = results[0].fmt_score(sum(r.score for r in results) / len(results))
            table.append([matchup.generator, matchup.solver, *results, *padding, avg])

        return format_table(table, {i + 2: 5 for i in range(self.rounds)})

    def __str__(self) -> str:
        return self.format()

    def calculate_points(self, achievable_points: int) -> dict[Team, float]:
        """Calculate the number of achieved points, given results.

        As awarding points completely depends on the type of battle that
        was fought, each battle style should implement a method that determines
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
        points = defaultdict(lambda: 0.)

        teams: set[Team] = set()
        for pair in self.keys():
            teams = teams.union(set(pair))
        team_combinations = combinations(teams, 2)

        if len(teams) == 1:
            return {teams.pop(): achievable_points}

        if self.rounds == 0:
            return {}

        points_per_round = round(achievable_points / self.rounds, 1)
        for pair in team_combinations:
            for i in range(self.rounds):
                score1 = self[Matchup(*pair)][i].score  # pair[1] was solver
                score0 = self[Matchup(*pair[::-1])][i].score  # pair[0] was solver

                # Default values for proportions, assuming no team manages to solve anything
                points_proportion0 = 0.5
                points_proportion1 = 0.5

                if score0 + score1 > 0:
                    points_proportion0 = score0 / (score0 + score1)
                    points_proportion1 = score1 / (score0 + score1)

                points[pair[0]] += round(points_per_round * points_proportion0, 1)
                points[pair[1]] += round(points_per_round * points_proportion1, 1)

        return points
