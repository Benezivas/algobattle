"""Wrapper that repeats a battle on an instance size a number of times and averages the competitive ratio over all runs."""

from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass
import itertools
import logging
from typing import Any

import algobattle.battle_wrapper
from algobattle.problem import Problem
from algobattle.team import Matchup, Team
from algobattle.util import format_table
from typing import TYPE_CHECKING, Generator
if TYPE_CHECKING:
    from algobattle.match import RunParameters

logger = logging.getLogger('algobattle.battle_wrappers.iterated')


class Iterated(algobattle.battle_wrapper.BattleWrapper):
    """Class of an iterated battle Wrapper."""

    battle_args = [([
            "--cap",
        ], {
            "dest": "cap",
            "type": int,
            "default": 50000,
            "help": "The maximum instance size up to which a battle is to be fought. Default: 50000",
        }), ([
            "--exponent",
        ], {
            "dest": "exponent",
            "type": int,
            "default": "2",
            "help": "The exponent used for the step size increase. Default: 2"
        }), ([
            "--approx_ratio",
        ], {
            "dest": "approximation_ratio",
            "type": float,
            "default": 1.0,
            "help": "Tolerated approximation ratio of a solution, if the problem is compatible with approximation. Default: 1.0"
        }),
    ]

    def __init__(self, problem: Problem, run_parameters: RunParameters | None = None,
                cap: int = 50000, exponent: int = 2, approximation_ratio: float = 1,
                **options) -> None:
        self.exponent = exponent
        self.cap = cap
        self.approx_ratio = approximation_ratio
        
        super().__init__(problem, run_parameters, **options)
    
    def wrapper(self, matchup: Matchup) -> Generator[Iterated.Result, None, None]:
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

        n = self.problem.n_start
        maximum_reached_n = 0
        i = 0
        exponent = self.exponent
        n_cap = self.cap
        alive = True

        logger.info(f'==================== Iterative Battle, Instanze Size Cap: {n_cap} ====================')
        while alive:
            logger.info(f'=============== Instance Size: {n}/{n_cap} ===============')
            approx_ratio = self._one_fight(matchup, instance_size=n)
            if approx_ratio == 0.0:
                alive = False
            elif approx_ratio > self.approx_ratio:
                logger.info(f'Solver {matchup.solver} does not meet the required solution quality at instance size {n}. ({approx_ratio}/{self.approx_ratio})')
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

            yield self.Result(n_cap, maximum_reached_n, n)
    
    @dataclass
    class Result(algobattle.battle_wrapper.BattleWrapper.Result):
        cap: int = 0
        solved: int = 0
        attempting: int = 0

        def __int__(self) -> int:
            return self.solved

        def __str__(self) -> str:
            return str(int(self))
        
        def __repr__(self) -> str:
            return f"Result(cap={self.cap}, solved={self.solved}, attempting={self.attempting}"


    class MatchResult(algobattle.battle_wrapper.BattleWrapper.MatchResult[Result]):
        
        def format(self) -> str:
            table = []
            table.append(["GEN", "SOL", *range(1, self.rounds + 1), "CAP", "AVG"])
            
            for matchup, res in self.items():
                padding = [""] * (self.rounds - len(res))
                if len(res) == 0:
                    last_cap = ""
                    avg = ""
                else:
                    last_cap = res[-1].cap
                    avg = sum(int(r) for r in res) // len(res)
                table.append([matchup.generator, matchup.solver, *res, *padding, last_cap, avg])

            return "Battle Type: Iterated Battle\n" + format_table(table)

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
            points: defaultdict[Team, float] = defaultdict(lambda: 0)

            teams: set[Team] = set()
            for pair in self.keys():
                teams = teams.union(set(pair))
            team_combinations = itertools.combinations(teams, 2)
            

            if len(teams) == 1:
                return {teams.pop(): achievable_points}

            rounds = len(next(iter(self.values())))
            if rounds == 0:
                return {}

            points_per_round = round(achievable_points / rounds, 1)
            for pair in team_combinations:
                for i in range(rounds):
                    solved1 = self[Matchup(*pair)][i].solved  # pair[1] was solver
                    solved0 = self[Matchup(*pair[::-1])][i].solved  # pair[0] was solver

                    # Default values for proportions, assuming no team manages to solve anything
                    points_proportion0 = 0.5
                    points_proportion1 = 0.5

                    if solved0 + solved1 > 0:
                        points_proportion0 = (solved0 / (solved0 + solved1))
                        points_proportion1 = (solved1 / (solved0 + solved1))

                    points[pair[0]] += round(points_per_round * points_proportion0, 1)
                    points[pair[1]] += round(points_per_round * points_proportion1, 1)

            return points
