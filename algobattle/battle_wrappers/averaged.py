"""Wrapper that iterates the instance size up to a point where the solving team is no longer able to solve an instance."""

from __future__ import annotations
from dataclasses import dataclass, field
import itertools
import logging
from collections import defaultdict

import algobattle.battle_wrapper
from algobattle.matchups import Matchup
from algobattle.problem import Problem
from algobattle.team import Team
from algobattle.util import format_table
from typing import TYPE_CHECKING, Any, Generator

if TYPE_CHECKING:
    from algobattle.match import RunParameters

logger = logging.getLogger('algobattle.battle_wrappers.averaged')


class Averaged(algobattle.battle_wrapper.BattleWrapper):
    """Class of an adveraged battle Wrapper."""

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


    def __init__(self, problem: Problem, run_parameters: RunParameters = RunParameters(),
                instance_size: int = 10, iterations: int = 25,
                **options: Any) -> None:
        self.instance_size = instance_size
        self.iterations = iterations

        super().__init__(problem, run_parameters, **options)  

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
        res = Averaged.Result()
        logger.info(f'==================== Averaged Battle, Instance Size: {self.instance_size}, Rounds: {self.iterations} ====================')
        for i in range(self.iterations):
            logger.info(f'=============== Iteration: {i + 1}/{self.iterations} ===============')
            approx_ratio = self._one_fight(matchup, instance_size=self.instance_size)
            res.approx_ratios.append(approx_ratio)

        yield res

    @staticmethod
    def calculate_points(results: dict[Matchup, list[Averaged.Result]], achievable_points: int) -> dict[Team, float]:
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
        for pair in results.keys():
            teams = teams.union(set(pair))
        team_combinations = itertools.combinations(teams, 2)
        

        if len(teams) == 1:
            return {teams.pop(): achievable_points}

        rounds = len(next(iter(results.values())))
        if rounds == 0:
            return {}
        
        points_per_round = round(achievable_points / rounds, 1)
        for pair in team_combinations:
            for i in range(rounds):
                points[pair[0]] = points.get(pair[0], 0)
                points[pair[1]] = points.get(pair[1], 0)

                ratios1 = results[Matchup(*pair)][i].approx_ratios  # pair[1] was solver
                ratios0 = results[Matchup(*pair[::-1])][i].approx_ratios  # pair[0] was solver

                valuation0 = 0
                valuation1 = 0
                if ratios0 and sum(ratios0) != 0:
                    valuation0 = sum(1 / x if x != 0 else 0 for x in ratios0) / len(ratios0)
                if ratios1 and sum(ratios1) != 0:
                    valuation1 = sum(1 / x if x != 0 else 0 for x in ratios1) / len(ratios1)

                # Default values for proportions, assuming no team manages to solve anything
                points_proportion0 = 0.5
                points_proportion1 = 0.5

                # Normalize valuations
                if valuation0 + valuation1 > 0:
                    points_proportion0 = (valuation0 / (valuation0 + valuation1))
                    points_proportion1 = (valuation1 / (valuation0 + valuation1))

                points[pair[0]] += round(points_per_round * points_proportion0, 1)
                points[pair[1]] += round(points_per_round * points_proportion1, 1)

        return points

    @staticmethod
    def format(results: dict[Matchup, list[Averaged.Result]]) -> str:
        num_rounds = len(next(iter(results.values())))
        table = []
        table.append(["GEN", "SOL", *range(1, num_rounds + 1), "LAST"])
        for (matchup, res) in results.items():
            table.append([matchup.generator, matchup.solver, *res, res[-1].approx_ratios[-1]])

        return "Battle Type: Averaged Battle\n" + format_table(table)