"""Wrapper that iterates the instance size up to a point where the solving team is no longer able to solve an instance."""
from __future__ import annotations
from configparser import ConfigParser
from dataclasses import dataclass, field
import logging

from algobattle.battle_wrapper import BattleWrapper
from algobattle.fight_handler import FightHandler
from algobattle.team import Matchup
from algobattle.util import inherit_docs

logger = logging.getLogger('algobattle.battle_wrappers.averaged')


class Averaged(BattleWrapper):
    """Class of an adveraged battle Wrapper."""

    def __init__(self, config: ConfigParser) -> None:
        super().__init__()
        if 'averaged' in config:
            self.instance_size = int(config['averaged'].get('approximation_instance_size', "10"))
            self.iterations = int(config['averaged'].get('approximation_iterations', "10"))
        else:
            self.instance_size = 10
            self.iterations = 10

    def run_round(self, fight_handler: FightHandler, matchup: Matchup) -> Averaged.Result:
        """Execute one averaged battle between a generating and a solving team.

        Execute several fights between two teams on a fixed instance size
        and determine the average solution quality.

        During execution, this function updates the match_data of the match
        object which is passed to it by
        calls to the match.update_match_data function.

        Parameters
        ----------
        fight_handler: FightHandler
            Fight handler that manages the execution of a concrete fight.
        """
        logger.info("=" * 20 + f"Averaged Battle, Instance Size: {self.instance_size}, Rounds: {self.iterations} " + "=" * 20)
        ratios = []
        for i in range(self.iterations):
            logger.info(f"=============== Iteration: {i + 1}/{self.iterations} ===============")
            approx_ratio = fight_handler.fight(matchup, self.instance_size)
            ratios.append(approx_ratio)
            self.notify("battle_info", {
                "size": self.instance_size,
                "iteration": f"{i+1:>4d}/{self.iterations:>4d}",
                "approximation ratios": ratios}
            )
        return self.Result(ratios)

    @inherit_docs
    @dataclass
    class Result(BattleWrapper.Result):
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
