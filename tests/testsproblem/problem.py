"""Problem class built for tests."""
import logging
from typing import Annotated, SupportsFloat

from algobattle.problem import ProblemModel, SolutionModel
from algobattle.util import Hidden

logger = logging.getLogger('algobattle.problems.testsproblem')


class Solution(SolutionModel):
    val: int

    def check_semantics(self, size: int, instance: "Tests") -> bool:
        return super().check_semantics(size, instance)



class Tests(ProblemModel):
    """Artificial problem used for tests."""

    name = "Tests"
    min_size = 0
    Solution = Solution

    val: int
    solution: Annotated[Solution, Hidden()]

    def check_semantics(self, size: int) -> bool:
        return self.val <= size and self.solution.val <= self.val

    def calculate_score(self, solution: Solution, size: int) -> SupportsFloat:
        return solution.val / self.val
