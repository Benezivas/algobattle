"""Wrapper that iterates the instance size up to a point where the solving team is no longer able to solve an instance."""

from __future__ import annotations
from dataclasses import dataclass, field
import itertools
import logging

import algobattle.battle_wrapper
from algobattle.team import Team
from typing import TYPE_CHECKING, Any
if TYPE_CHECKING:
    from algobattle.match import Match

logger = logging.getLogger('algobattle.battle_wrappers.averaged')


class Averaged(algobattle.battle_wrapper.BattleWrapper):
    """Class of an adveraged battle Wrapper."""

    @dataclass
    class Result(algobattle.battle_wrapper.BattleWrapper.Result):
        approx_ratios: list[float] = field(default_factory=list)

    def __init__(self, match: Match, problem: str, rounds: int = 5,
                instance_size: int = 10, iterations: int = 25,
                **options: Any) -> None:
        self.instance_size = instance_size
        self.iterations = iterations

        self.pairs: dict[tuple[Team, Team], list[Averaged.Result]]
        super().__init__(match, problem, rounds, **options)  

    def wrapper(self, match: Match) -> None:
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
        approximation_ratios = []
        logger.info('==================== Averaged Battle, Instance Size: {}, Rounds: {} ===================='
                    .format(self.instance_size, self.iterations))
        for i in range(self.iterations):
            logger.info(f'=============== Iteration: {i + 1}/{self.iterations} ===============')
            approx_ratio = match._one_fight(instance_size=self.instance_size)
            approximation_ratios.append(approx_ratio)

            curr_pair = self.curr_pair
            assert curr_pair is not None
            curr_round = self.curr_round
            self.pairs[curr_pair][curr_round].approx_ratios.append(approx_ratio)

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
        points = dict()

        teams: set[Team] = set()
        for pair in self.pairs.keys():
            teams = teams.union(set(pair))
        team_combinations = itertools.combinations(teams, 2)

        if len(teams) == 1:
            return {teams.pop(): achievable_points}

        if self.rounds <= 0:
            return {}
        points_per_round = round(achievable_points / self.rounds, 1)
        for pair in team_combinations:
            for i in range(self.rounds):
                points[pair[0]] = points.get(pair[0], 0)
                points[pair[1]] = points.get(pair[1], 0)

                ratios1 = self.pairs[pair][i].approx_ratios  # pair[1] was solver
                ratios0 = self.pairs[pair[::-1]][i].approx_ratios  # pair[0] was solver

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

    def format_as_utf8(self) -> str:
        """Format the executed battle.

        Returns
        -------
        str
            A formatted string on the basis of the wrapper.
        """
        formatted_output_string = ""
        formatted_output_string += 'Battle Type: Averaged Battle\n\r'
        formatted_output_string += '╔═════════╦═════════╦' \
                                   + ''.join(['══════╦' for _ in range(self.rounds)]) \
                                   + '══════╦══════╦════════╗' + '\n\r' \
                                   + '║   GEN   ║   SOL   ' \
                                   + ''.join([f'║{"R" + str(i + 1):^6s}' for i in range(self.rounds)]) \
                                   + '║ LAST ║ SIZE ║  ITER  ║' + '\n\r' \
                                   + '╟─────────╫─────────╫' \
                                   + ''.join(['──────╫' for _ in range(self.rounds)]) \
                                   + '──────╫──────╫────────╢' + '\n\r'

        for pair in self.pairs.keys():
            avg = [0.0 for _ in range(self.rounds)]

            for i in range(self.rounds):
                executed_iters = len(self.pairs[pair][i].approx_ratios)
                n_dead_iters = executed_iters - len([i for i in self.pairs[pair][i].approx_ratios if i != 0.0])

                if executed_iters - n_dead_iters > 0:
                    avg[i] = sum(self.pairs[pair][i].approx_ratios) / (executed_iters - n_dead_iters)

            curr_round = self.curr_round
            curr_iter = len(self.pairs[pair][curr_round].approx_ratios)
            latest_approx_ratio = 0.0
            if self.pairs[pair][curr_round].approx_ratios:
                latest_approx_ratio = self.pairs[pair][curr_round].approx_ratios[-1]

            formatted_output_string += f'║{pair[0]:>9s}║{pair[1]:>9s}' \
                                        + ''.join([f'║{avg[i]:>6.2f}' for i in range(self.rounds)]) \
                                        + '║{:>6.2f}║{:>6d}║{:>3d}/{:>3d} ║'.format(latest_approx_ratio,
                                                                                    self.instance_size,
                                                                                    curr_iter,
                                                                                    self.iterations) + '\r\n'
        formatted_output_string += '╚═════════╩═════════╩' \
                                   + ''.join(['══════╩' for _ in range(self.rounds)]) \
                                   + '══════╩══════╩════════╝' + '\n\r'

        return formatted_output_string
