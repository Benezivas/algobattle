"""Wrapper that iterates the instance size up to a point where the solving team is no longer able to solve an instance."""

from __future__ import annotations
from dataclasses import dataclass, field
import itertools
import logging
from collections import defaultdict
from typing import Any, Generator

import algobattle.battle_wrapper
from algobattle.fight import Fight
from algobattle.problem import Problem
from algobattle.team import Team, Matchup
from algobattle.util import format_table


logger = logging.getLogger("algobattle.battle_wrappers.averaged")


class Averaged(algobattle.battle_wrapper.BattleWrapper):
    """Class of an adveraged battle Wrapper."""

    def __init__(
        self,
        problem: Problem,
        fight: Fight,
        instance_size: int = 10,
        iterations: int = 25,
        **options: Any,
    ) -> None:
        """Create a wrapper for an averaged battle.

        Parameters
        ----------
        problem : Problem
            The problem that the teams will have to solve.
        doker_config : DockerConfig
            Docker configuration for the runs.
        instance_size : int
            The instance size on which the averaged run is to be made.
        iterations : int
            The number of iterations that are to be averaged.
        """
        self.instance_size = instance_size
        self.iterations = iterations

        super().__init__(problem, fight, **options)

    def wrapper(self, matchup: Matchup) -> Generator[Averaged.Result, None, None]:
        """Execute one averaged battle between a generating and a solving team.

        Execute several fights between two teams on a fixed instance size
        and determine the average solution quality.

        During execution, this function updates the match_data of the match
        object which is passed to it.

        Parameters
        ----------
        match: Match
            The Match object on which the battle wrapper is to be executed on.
        """
        res = self.Result()
        logger.info(
            f"==================== Averaged Battle, Instance Size: {self.instance_size}, "
            "Rounds: {self.iterations} ===================="
        )
        for i in range(self.iterations):
            logger.info(f"=============== Iteration: {i + 1}/{self.iterations} ===============")
            approx_ratio = self.fight(matchup, instance_size=self.instance_size)
            res.approx_ratios.append(approx_ratio)
            yield res

    @dataclass
    class Result(algobattle.battle_wrapper.BattleWrapper.Result):
        approx_ratios: list[float] = field(default_factory=list)

        def __float__(self) -> float:
            successful_iters = [x for x in self.approx_ratios if x != 0]
            return sum(successful_iters) / len(successful_iters)

        def __str__(self) -> str:
            return str(float(self))

        def __repr__(self) -> str:
            return str(self.approx_ratios)

    class MatchResult(algobattle.battle_wrapper.BattleWrapper.MatchResult[Result]):
        def format(self) -> str:
            table = []
            table.append(["GEN", "SOL", *range(1, self.rounds + 1), "LAST"])
            for matchup, res in self.items():
                if len(res) == 0:
                    last_ratio = ""
                else:
                    if len(res[-1].approx_ratios) == 0:
                        if len(res) == 1:
                            last_ratio = ""
                        else:
                            last_ratio = res[-2].approx_ratios[-1]
                    else:
                        last_ratio = res[-1].approx_ratios[-1]
                padding = [""] * (self.rounds - len(res))

                table.append([matchup.generator, matchup.solver, *res, *padding, last_ratio])

            return "Battle Type: Averaged Battle\n" + format_table(table)

        def calculate_points(self, achievable_points: int) -> dict[Team, float]:
            """Calculate the number of achieved points.

            The valuation of an averaged battle is calculating by summing up
            the reciprocals of each solved fight. This sum is then divided by
            the total number of ratios to account for unsuccessful battles.

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
            points: defaultdict[Team, float] = defaultdict(lambda: 0)

            teams: set[Team] = set()
            for pair in self.keys():
                teams = teams.union(set(pair))
            team_combinations = itertools.combinations(teams, 2)

            if len(teams) == 1:
                return {teams.pop(): achievable_points}

            if self.rounds == 0:
                return {}

            points_per_round = round(achievable_points / self.rounds, 1)
            for pair in team_combinations:
                for i in range(self.rounds):
                    points[pair[0]] = points.get(pair[0], 0)
                    points[pair[1]] = points.get(pair[1], 0)

                    ratios1 = self[Matchup(*pair)][i].approx_ratios  # pair[1] was solver
                    ratios0 = self[Matchup(*pair[::-1])][i].approx_ratios  # pair[0] was solver
                    valuation0 = sum(ratios0) / len(ratios0)
                    valuation1 = sum(ratios1) / len(ratios1)

                    # Default values for proportions, assuming no team manages to solve anything
                    points_proportion0 = 0.5
                    points_proportion1 = 0.5

                    # Normalize valuations
                    if valuation0 + valuation1 > 0:
                        points_proportion0 = valuation0 / (valuation0 + valuation1)
                        points_proportion1 = valuation1 / (valuation0 + valuation1)

                    points[pair[0]] += round(points_per_round * points_proportion0, 1)
                    points[pair[1]] += round(points_per_round * points_proportion1, 1)

            return points
