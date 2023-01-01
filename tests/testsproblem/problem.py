"""Problem class built for tests."""
import logging
from typing import Annotated, SupportsFloat

from algobattle.problem import ProblemModel, SolutionModel
from algobattle.util import Hidden

logger = logging.getLogger('algobattle.problems.testsproblem')


class Tests(ProblemModel):
    """Artificial problem used for tests."""

    class Solution(SolutionModel):
        difference: int

    name = "Tests"
    min_size = 0

    first_val: int
    second_val: int
    solution: Annotated[Solution, Hidden()]

    def check_semantics(self, size: int) -> bool:
        return self.first_val + self.second_val <= size and self.solution.check_semantics(size, self)

    def calculate_score(self, solution: Solution, size: int) -> SupportsFloat:
        return self.first_val - self.second_val == solution.difference
