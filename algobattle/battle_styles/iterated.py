"""Battle style that repeats a battle on an instance size a number of times and averages the competitive ratio over all runs."""

from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass
import itertools
import logging

import algobattle.battle_style
from algobattle.problem import Problem
from algobattle.fight import Fight
from algobattle.team import Matchup, Team
from algobattle.util import format_table
from typing import Generator

logger = logging.getLogger("algobattle.battle_styles.iterated")


class Iterated(algobattle.battle_style.BattleStyle):
    """Class of an iterated battle style."""

    def __init__(
        self,
        problem: Problem,
        fight: Fight,
        cap: int = 50000,
        exponent: int = 2,
        approximation_ratio: float = 1,
        **options,
    ) -> None:
        """Create a battle style for an iterated battle.

        Parameters
        ----------
        problem : Problem
            The problem that the teams will have to solve.
        docker_config : DockerConfig
            Docker config for the runs.
        cap : int
            The maximum instance size up to which a battle is to be fought.
        exponent : int
            The exponent used for the step size increase.
        approximation_ratio : float, optional
            Tolerated approximation ratio of a solution, if the problem is compatible with approximation.
        """
        self.exponent = exponent
        self.cap = cap
        self.approx_ratio = approximation_ratio

        super().__init__(problem, fight, **options)

    def run(self, matchup: Matchup) -> Generator[Iterated.Result, None, None]:
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

        The battle style automatically ends the battle and declares the solver as the
        winner once the iteration cap is reached.

        During execution, this function updates the match_data of the match
        object which is passed to it.

        Parameters
        ----------
        match: Match
            The Match object on which the battle style is to be executed on.
        """
        n = self.problem.n_start
        maximum_reached_n = 0
        i = 0
        exponent = self.exponent
        n_cap = self.cap
        alive = True

        logger.info(f"==================== Iterative Battle, Instanze Size Cap: {n_cap} ====================")
        while alive:
            logger.info(f"=============== Instance Size: {n}/{n_cap} ===============")
            approx_ratio = self.fight(matchup, instance_size=n)
            if approx_ratio == 0.0:
                alive = False
            elif approx_ratio > self.approx_ratio:
                logger.info(
                    f"Solver {matchup.solver} does not meet the required solution quality at instance size {n}. "
                    "({approx_ratio}/{self.approx_ratio})"
                )
                alive = False

            if not alive and i > 1:
                # The step size increase was too aggressive, take it back and reset the increment multiplier
                logger.info(f"Setting the solution cap to {n}...")
                n_cap = n
                n -= i**exponent
                i = 0
                alive = True
            elif n > maximum_reached_n and alive:
                # We solved an instance of bigger size than before
                maximum_reached_n = n

            if n + 1 > n_cap:
                alive = False
            else:
                i += 1
                n += i**exponent

                if n >= n_cap:
                    # We have failed at this value of n already, reset the step size!
                    n -= i**exponent - 1
                    i = 1

            yield self.Result(n_cap, maximum_reached_n, n)

    @dataclass
    class Result(algobattle.battle_style.BattleStyle.Result):
        cap: int = 0
        solved: int = 0
        attempting: int = 0

        @property
        def score(self) -> float:
            return self.solved
