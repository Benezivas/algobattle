"""Problem class built for tests."""
import logging
from typing import ClassVar, SupportsFloat

from algobattle.problem import ProblemModel, SolutionModel

logger = logging.getLogger('algobattle.problems.testsproblem')






class Tests(ProblemModel):
    """Artificial problem used for tests."""

    name: ClassVar[str] = "Tests"
    with_solution: ClassVar[bool] = False

    class Solution(SolutionModel):
        semantics: bool
        quality: bool

        def check_semantics(self, size: int, instance: "Tests") -> bool:
            return self.semantics

    semantics: bool

    def check_semantics(self, size: int) -> bool:
        return self.semantics

    def calculate_score(self, solution: Solution, size: int) -> SupportsFloat:
        return solution.quality
