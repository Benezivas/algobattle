"""Wrapper that iterates the instance size up to a point where the solving team is no longer able to solve an instance."""
from __future__ import annotations
from configparser import ConfigParser
from dataclasses import dataclass, field
import logging

from algobattle.battle_wrapper import BattleWrapper
from algobattle.fight_handler import FightHandler
from algobattle.observer import Observer
from algobattle.team import Matchup
from algobattle.util import inherit_docs

logger = logging.getLogger("algobattle.battle_wrappers.averaged")


class Averaged(BattleWrapper):
    """Class of an adveraged battle Wrapper."""

    def __init__(self, fight_handler: FightHandler, config: ConfigParser, observer: Observer | None = None) -> None:
        super().__init__(fight_handler, observer)
        if "averaged" in config:
            self.instance_size = int(config["averaged"].get("approximation_instance_size", "10"))
            self.iterations = int(config["averaged"].get("approximation_iterations", "10"))
        else:
            self.instance_size = 10
            self.iterations = 10

    def run_round(self, matchup: Matchup) -> Averaged.Result:
        """Execute one averaged battle between a generating and a solving team.

        Execute several fights between two teams on a fixed instance size
        and determine the average solution quality.
        """
        logger.info("=" * 20 + f"Averaged Battle, Instance Size: {self.instance_size}, Rounds: {self.iterations} " + "=" * 20)
        result = self.Result(self.instance_size, self.iterations)
        for i in range(self.iterations):
            logger.info(f"=============== Iteration: {i + 1}/{self.iterations} ===============")
            result.curr_iter = i + 1
            approx_ratio = self.fight_handler.fight(matchup, self.instance_size)
            result.approx_ratios.append(approx_ratio)
        return result

    @inherit_docs
    @dataclass
    class Result(BattleWrapper.Result):
        size: int
        num_iter: int
        curr_iter: int = 0
        approx_ratios: list[float] = field(default_factory=list)

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
