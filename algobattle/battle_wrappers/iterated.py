"""Wrapper that repeats a battle on an instance size a number of times and averages the competitive ratio over all runs."""

from __future__ import annotations
from dataclasses import dataclass
import itertools
import logging

import algobattle.battle_wrapper
from algobattle.problem import Problem
from algobattle.team import Team
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from algobattle.match import Match, RunParameters

logger = logging.getLogger('algobattle.battle_wrappers.iterated')


class Iterated(algobattle.battle_wrapper.BattleWrapper):
    """Class of an iterated battle Wrapper."""
    
    @dataclass
    class Result(algobattle.battle_wrapper.BattleWrapper.Result):
        cap: int = 0
        solved: int = 0
        attempting: int = 0

    def __init__(self, problem: Problem, run_parameters: RunParameters, rounds: int = 5,
                cap: int = 50000, exponent: int = 2,
                **options) -> None:
        self.exponent = exponent
        self.cap = cap
        
        self.pairs: dict[tuple[Team, Team], list[Iterated.Result]]
        super().__init__(problem, run_parameters, rounds, **options)

    def wrapper(self, match: Match, generating: Team, solving: Team) -> None:
        """Execute one iterative battle between a generating and a solving team.

        Incrementally try to search for the highest n for which the solver is
        still able to solve instances.  The base increment value is multiplied
        with the power of iterations since the last unsolvable instance to the
        given exponent.
        Only once the solver fails after the multiplier is reset, it counts as
        failed. Since this would heavily favour probabilistic algorithms (That
        may have only failed by chance and are able to solve a certain instance
        size on a second try), we cap the maximum solution size by the first
        value that an algorithm has failed on.

        The wrapper automatically ends the battle and declares the solver as the
        winner once the iteration cap is reached.

        During execution, this function updates the match_data of the match
        object which is passed to it.

        Parameters
        ----------
        match: Match
            The Match object on which the battle wrapper is to be executed on.
        """
        curr_pair = self.curr_pair
        assert curr_pair is not None
        curr_round = self.curr_round

        n = match.problem.n_start
        maximum_reached_n = 0
        i = 0
        exponent = self.exponent
        n_cap = self.cap
        self.pairs[curr_pair][curr_round].cap = n_cap
        alive = True

        logger.info(f'==================== Iterative Battle, Instanze Size Cap: {n_cap} ====================')
        while alive:
            logger.info(f'=============== Instance Size: {n}/{n_cap} ===============')
            approx_ratio = self._one_fight(generating, solving, instance_size=n)
            if approx_ratio == 0.0:
                alive = False
            elif approx_ratio > match.approximation_ratio:
                logger.info(f'Solver {match.solving_team} does not meet the required solution quality at instance size {n}. ({approx_ratio}/{match.approximation_ratio})')
                alive = False

            if not alive and i > 1:
                # The step size increase was too aggressive, take it back and reset the increment multiplier
                logger.info(f'Setting the solution cap to {n}...')
                n_cap = n
                n -= i ** exponent
                i = 0
                alive = True
            elif n > maximum_reached_n and alive:
                # We solved an instance of bigger size than before
                maximum_reached_n = n

            if n + 1 > n_cap:
                alive = False
            else:
                i += 1
                n += i ** exponent

                if n >= n_cap:
                    # We have failed at this value of n already, reset the step size!
                    n -= i ** exponent - 1
                    i = 1

            self.pairs[curr_pair][curr_round].cap = n_cap
            self.pairs[curr_pair][curr_round].solved = maximum_reached_n
            self.pairs[curr_pair][curr_round].attempting = n

    def calculate_points(self, achievable_points: int) -> dict[Team, float]:
        """Calculate the number of achieved points.

        Each pair of teams fights for the achievable points among one another.
        These achievable points are split over all matches, as one run reaching
        the iteration cap poisons the average number of points.

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

        points_per_iteration = round(achievable_points / self.rounds, 1)
        for pair in team_combinations:
            for i in range(self.rounds):
                points[pair[0]] = points.get(pair[0], 0)
                points[pair[1]] = points.get(pair[1], 0)

                solved1 = self.pairs[pair][i].solved  # pair[1] was solver
                solved0 = self.pairs[pair[::-1]][i].solved  # pair[0] was solver

                # Default values for proportions, assuming no team manages to solve anything
                points_proportion0 = 0.5
                points_proportion1 = 0.5

                if solved0 + solved1 > 0:
                    points_proportion0 = (solved0 / (solved0 + solved1))
                    points_proportion1 = (solved1 / (solved0 + solved1))

                points[pair[0]] += round(points_per_iteration * points_proportion0, 1)
                points[pair[1]] += round(points_per_iteration * points_proportion1, 1)

        return points

    def format_as_utf8(self) -> str:
        """Format the executed battle.

        Returns
        -------
        str
            A formatted string on the basis of the wrapper.
        """
        formatted_output_string = ""
        formatted_output_string += 'Battle Type: Iterated Battle\n\r'
        formatted_output_string += '╔═════════╦═════════╦' \
                                   + ''.join(['══════╦' for _ in range(self.rounds)]) \
                                   + '══════╦══════╗' + '\n\r' \
                                   + '║   GEN   ║   SOL   ' \
                                   + ''.join([f'║{"R" + str(i + 1):^6s}' for i in range(self.rounds)]) \
                                   + '║  CAP ║  AVG ║' + '\n\r' \
                                   + '╟─────────╫─────────╫' \
                                   + ''.join(['──────╫' for _ in range(self.rounds)]) \
                                   + '──────╫──────╢' + '\n\r'

        for pair in self.pairs.keys():
            curr_round = self.curr_round
            avg = sum(self.pairs[pair][i].solved for i in range(self.rounds)) // self.rounds

            formatted_output_string += f'║{pair[0]:>9s}║{pair[1]:>9s}' \
                                        + ''.join([f'║{self.pairs[pair][i].solved:>6d}'
                                                    for i in range(self.rounds)]) \
                                        + f'║{self.pairs[pair][curr_round].cap:>6d}║{avg:>6d}║' + '\r\n'
        formatted_output_string += '╚═════════╩═════════╩' \
                                   + ''.join(['══════╩' for _ in range(self.rounds)]) \
                                   + '══════╩══════╝' + '\n\r'

        return formatted_output_string


