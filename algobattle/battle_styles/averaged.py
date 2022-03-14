"""Battle style that iterates the instance size up to a point where the solving team is no longer able to solve an instance."""

from __future__ import annotations
from dataclasses import dataclass, field
import itertools
import logging
from collections import defaultdict
from typing import Any, Generator

import algobattle.battle_style
from algobattle.fight import Fight
from algobattle.problem import Problem
from algobattle.team import Team, Matchup
from algobattle.util import format_table


logger = logging.getLogger("algobattle.battle_styles.averaged")


class Averaged(algobattle.battle_style.BattleStyle):
    """Class of an adveraged battle style."""

    def __init__(
        self,
        problem: Problem,
        fight: Fight,
        instance_size: int = 10,
        iterations: int = 25,
        **options: Any,
    ) -> None:
        """Create a battle style for an averaged battle.

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

    def run(self, matchup: Matchup) -> Generator[Averaged.Result, None, None]:
        """Execute one averaged battle between a generating and a solving team.

        Execute several fights between two teams on a fixed instance size
        and determine the average solution quality.

        During execution, this function updates the match_data of the match
        object which is passed to it.

        Parameters
        ----------
        match: Match
            The Match object on which the battle style is to be executed on.
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
    class Result(algobattle.battle_style.BattleStyle.Result):
        approx_ratios: list[float] = field(default_factory=list)

        @property
        def score(self) -> float:
            if len(self.approx_ratios) == 0:
                return 0
            else:
                return sum(self.approx_ratios) / len(self.approx_ratios)
