"""Wrapper that repeats a battle on an instance size a number of times and averages the competitive ratio over all runs."""
from __future__ import annotations
import logging

from algobattle.battle_wrapper import BattleWrapper
from algobattle.fight_handler import FightHandler
from algobattle.util import CLIParsable, inherit_docs, argspec

logger = logging.getLogger("algobattle.battle_wrappers.iterated")


class Iterated(BattleWrapper):
    """Class of an iterated battle Wrapper."""

    @inherit_docs
    class Config(CLIParsable):
        iteration_cap: int = argspec(default=50_000, help="Maximum instance size that will be tried.")
        exponent: int = argspec(default=2, help="Determines how quickly the instance size grows.")
        approximation_ratio: float = argspec(default=1, help="Approximation ratio that a solver needs to achieve to pass.")

    def run_battle(self, config: Config, fight_handler: FightHandler, min_size: int) -> None:
        """Execute one iterative battle between a generating and a solving team.

        Incrementally try to search for the highest n for which the solver is
        still able to solve instances.  The base increment value is multiplied
        with the power of iterations since the last unsolvable instance to the
        given exponent.
        Only once the solver fails after the multiplier is reset, it counts as
        failed. Since this would heavily favour probabilistic algorithms (That
        may have only failed by chance and are able to solve a certain instance
        size on a second try), we cap the maximum solution size by the last
        value that an algorithm has failed on.

        The wrapper automatically ends the battle and declares the solver as the
        winner once the iteration cap is reached.

        During execution, this function updates the self.round_data dict,
        which automatically notifies all observers subscribed to this object.s
        """
        base_increment = 0
        alive = True
        self.reached = 0
        self.cap = config.iteration_cap
        self.current = min_size

        while alive:
            result = fight_handler.fight(self.current)
            score = result.score
            if score < config.approximation_ratio:
                logger.info(f"Solver does not meet the required solution quality at instance size "
                            f"{self.current}. ({score}/{config.approximation_ratio})")
                alive = False

            if not alive and base_increment > 1:
                # The step size increase was too aggressive, take it back and reset the base_increment
                logger.info(f"Setting the solution cap to {self.current}...")
                self.cap = self.current
                self.current -= base_increment ** config.exponent
                base_increment = 0
                alive = True
            elif self.current > self.reached and alive:
                # We solved an instance of bigger size than before
                self.reached = self.current

            if self.current + 1 > self.cap:
                alive = False
            else:
                base_increment += 1
                self.current += base_increment ** config.exponent

                if self.current >= self.cap:
                    # We have failed at this value of n already, reset the step size!
                    self.current -= base_increment ** config.exponent - 1
                    base_increment = 1


    @inherit_docs
    def score(self) -> float:
        return self.reached

    @inherit_docs
    @staticmethod
    def format_score(score: float) -> str:
        return str(int(score))

    @inherit_docs
    def display(self) -> str:
        return f"current cap: {self.cap}\nsolved: {self.reached}\nattempting: {self.current}"
