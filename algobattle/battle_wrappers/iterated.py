"""Wrapper that repeats a battle on an instance size a number of times and averages the competitive ratio over all runs."""
from __future__ import annotations
from configparser import ConfigParser
from dataclasses import dataclass
import logging

from algobattle.battle_wrapper import BattleWrapper
from algobattle.fight_handler import FightHandler
from algobattle.observer import Observer
from algobattle.team import Matchup
from algobattle.util import inherit_docs

logger = logging.getLogger('algobattle.battle_wrappers.iterated')


class Iterated(BattleWrapper):
    """Class of an iterated battle Wrapper."""

    def __init__(self, fight_handler: FightHandler, config: ConfigParser, observer: Observer | None = None) -> None:
        super().__init__(fight_handler, observer)
        if 'iterated' in config:
            self.iteration_cap = int(config['iterated'].get('iteration_cap', "50000"))
            self.exponent = int(config['iterated'].get('exponent', "2"))
            self.approximation_ratio = float(config['iterated'].get('approximation_ratio', "1.0"))
        else:
            self.iteration_cap = 50000
            self.exponent = 2
            self.approximation_ratio = 1.0

    def run_round(self, matchup: Matchup) -> Iterated.Result:
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
        which automatically notifies all observers subscribed to this object.

        Parameters
        ----------
        fight_handler: FightHandler
            Fight handler that manages the execution of a concrete fight.
        """
        base_increment = 0
        exponent = self.exponent
        result = self.Result(0, self.iteration_cap, self.fight_handler.problem.n_start)
        alive = True

        logger.info(f"==================== Iterative Battle, Instanze Size Cap: {result.n_cap} ====================")
        while alive:
            logger.info(f"=============== Instance Size: {result.current}/{result.n_cap} ===============")

            approx_ratio = self.fight_handler.fight(matchup, result.current)
            if approx_ratio == 0.0 or approx_ratio > self.approximation_ratio:
                logger.info(f"Solver {matchup.solver} does not meet the required solution quality at instance size {result.current}."
                            f" ({approx_ratio}/{self.approximation_ratio})")
                alive = False

            if not alive and base_increment > 1:
                # The step size increase was too aggressive, take it back and reset the base_increment
                logger.info(f"Setting the solution cap to {result.current}...")
                result.n_cap = result.current
                result.current -= base_increment ** exponent
                base_increment = 0
                alive = True
            elif result.current > result.reached and alive:
                # We solved an instance of bigger size than before
                result.reached = result.current

            if result.current + 1 > result.n_cap:
                alive = False
            else:
                base_increment += 1
                result.current += base_increment ** exponent

                if result.current >= result.n_cap:
                    # We have failed at this value of n already, reset the step size!
                    result.current -= base_increment ** exponent - 1
                    base_increment = 1

        return result

    @inherit_docs
    @dataclass
    class Result(BattleWrapper.Result):
        reached: int
        n_cap: int
        current: int

        @inherit_docs
        @property
        def score(self) -> float:
            return self.reached

        @inherit_docs
        @staticmethod
        def format_score(score: float) -> str:
            return str(int(score))
        
        def display(self) -> str:
            return f"current cap: {self.n_cap}\nsolved: {self.reached}\nattempting: {self.current}"
