"""Wrapper that iterates the instance size up to a point where the solving team is no longer able to solve an instance."""
from __future__ import annotations
from dataclasses import InitVar, dataclass, field
import logging

from algobattle.battle_wrapper import BattleWrapper
from algobattle.observer import Observer
from algobattle.team import Matchup
from algobattle.util import ArgSpec, inherit_docs

logger = logging.getLogger("algobattle.battle_wrappers.averaged")


class Averaged(BattleWrapper):
    """Class of an adveraged battle Wrapper."""

    @inherit_docs
    @dataclass
    class Config(BattleWrapper.Config):
        instance_size: int = ArgSpec(10, help="Instance size that will be fought at.")
        iterations: int = ArgSpec(10, help="Number of iterations in each round.")

    config: Config

    def run_round(self, matchup: Matchup, observer: Observer | None = None) -> Averaged.Result:
        """Execute one averaged battle between a generating and a solving team.

        Execute several fights between two teams on a fixed instance size
        and determine the average solution quality.
        """
        logger.info(
            "=" * 20
            + f"Averaged Battle, Instance Size: {self.config.instance_size}, Rounds: {self.config.iterations} "
            + "=" * 20
        )
        result = self.Result(self.config.instance_size, self.config.iterations, observer=observer)
        for i in range(self.config.iterations):
            logger.info(f"=============== Iteration: {i + 1}/{self.config.iterations} ===============")
            result.curr_iter = i + 1
            approx_ratio = self.fight_handler.fight(matchup, self.config.instance_size)
            result.approx_ratios.append(approx_ratio)
        return result

    @inherit_docs
    @dataclass
    class Result(BattleWrapper.Result):
        size: int
        num_iter: int
        curr_iter: int = 0
        approx_ratios: list[float] = field(default_factory=list)
        observer: InitVar[Observer | None] = None

        @inherit_docs
        @property
        def score(self) -> float:
            if len(self.approx_ratios) == 0:
                return 0
            else:
                return sum(1 / x if x != 0 else 0 for x in self.approx_ratios) / len(self.approx_ratios)

        @inherit_docs
        @staticmethod
        def format_score(score: float) -> str:
            return format(score, ".0%")

        @inherit_docs
        def display(self) -> str:
            return (
                f"size: {self.size}\niteration: {self.curr_iter}/{self.num_iter}\napproximation ratios: {self.approx_ratios}"
            )
