"""Battle style that repeats a battle on an instance size a number of times and averages the solution quality."""

from __future__ import annotations
from dataclasses import dataclass, field
import logging
from typing import Any, Generator

from algobattle.battle_style import BattleStyle
from algobattle.fight import Fight
from algobattle.problem import Problem
from algobattle.team import Matchup
from algobattle.util import inherit_docs


logger = logging.getLogger("algobattle.battle_styles.averaged")


class Averaged(BattleStyle):
    """Class of an averaged battle.

    This battle style fights on a specific instance size a number of times and then averages the solution quality.
    """

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
        fight : Fight
            Fight that will be used.
        instance_size : int
            The instance size on which the averaged run is to be made.
        iterations : int
            The number of iterations that are to be averaged.
        """
        self.instance_size = instance_size
        self.iterations = iterations

        super().__init__(problem, fight, **options)

    def run(self, matchup: Matchup) -> Result:
        """Execute one averaged battle between a generating and a solving team.

        Execute several fights between two teams on a fixed instance size
        and determine the average solution quality.

        Parameters
        ----------
        matchup: Matchup
            The matchup of teams that participate in this battle.

        Returns
        -------
        Generator[Result, None, None]
            A generator of intermediate results, the last yielded is the final result.
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
        return res

    @dataclass
    class Result(BattleStyle.Result):
        """The result of an averaged battle."""

        approx_ratios: list[float] = field(default_factory=list)

        @inherit_docs
        @property
        def score(self) -> float:
            if len(self.approx_ratios) == 0:
                return 0
            else:
                return sum(self.approx_ratios) / len(self.approx_ratios)

        @inherit_docs
        @staticmethod
        def fmt_score(score: float) -> str:
            if 0 <= score <= 10:
                return f"{score: >5.0%}"
            else:
                return f"{score: >3.1}"
