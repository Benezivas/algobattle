"""Problem class built for tests."""
import logging
from typing import Annotated, ClassVar, SupportsFloat

from algobattle.problem import ProblemModel, SolutionModel
from algobattle.util import Hidden

logger = logging.getLogger('algobattle.problems.testsproblem')


class Solution(SolutionModel):
    val: int

    def check_semantics(self, size: int, instance: "Tests") -> bool:
        return self.val <= instance.val



class Tests(ProblemModel):
    """Artificial problem used for tests."""

    name: ClassVar[str] = "Tests"
    min_size: ClassVar[int] = 5
    Solution = Solution

    val: int
    solution: Annotated[Solution, Hidden()]

    def check_semantics(self, size: int) -> bool:
        return self.val <= size and self.solution.check_semantics(size, self)

    def calculate_score(self, solution: Solution, size: int) -> SupportsFloat:
        return solution.val / self.val
