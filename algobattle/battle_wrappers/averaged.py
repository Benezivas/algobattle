"""Wrapper that iterates the instance size up to a point where the solving team is no longer able to solve an instance."""
import logging

from algobattle.battle_wrapper import BattleWrapper, argspec
from algobattle.docker_util import Generator, Solver
from algobattle.util import inherit_docs

logger = logging.getLogger("algobattle.battle_wrappers.averaged")


class Averaged(BattleWrapper):
    """Class of an adveraged battle Wrapper."""

    @inherit_docs
    class Config(BattleWrapper.Config):
        instance_size: int = argspec(default=10, help="Instance size that will be fought at.")
        iterations: int = argspec(default=10, help="Number of iterations in each round.")

    def run_battle(self, generator: Generator, solver: Solver, config: Config, min_size: int) -> None:
        """Execute one averaged battle between a generating and a solving team.

        Execute several fights between two teams on a fixed instance size
        and determine the average solution quality.
        """
        if config.instance_size < min_size:
            raise ValueError(
                f"The problem specifies a minimum size of {min_size} but the chosen size is only {config.instance_size}!"
            )
        self.iterations = config.iterations
        self.scores: list[float] = []
        for i in range(config.iterations):
            self.curr_iter = i + 1
            result = self.run_programs(generator, solver, config.instance_size)
            self.scores.append(result.score)

    @inherit_docs
    def score(self) -> float:
        if len(self.scores) == 0:
            return 0
        else:
            return sum(1 / x if x != 0 else 0 for x in self.scores) / len(self.scores)

    @inherit_docs
    @staticmethod
    def format_score(score: float) -> str:
        return format(score, ".0%")

    @inherit_docs
    def display(self) -> str:
        return (f"iteration: {self.curr_iter}/{self.iterations}\nscores: {self.scores}")
