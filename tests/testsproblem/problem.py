"""Problem class built for tests."""
from typing import ClassVar, SupportsFloat

from algobattle.problem import ProblemModel, SolutionModel


class TestProblem(ProblemModel):
    """Artificial problem used for tests."""

    name: ClassVar[str] = "Tests"
    with_solution: ClassVar[bool] = False

    class Solution(SolutionModel):
        """Solution class for :cls:`Tests`."""

        semantics: bool
        quality: bool

        def is_valid(self, instance: "TestProblem", size: int) -> bool:
            return self.semantics

    semantics: bool

    def is_valid(self, size: int) -> bool:
        return self.semantics

    def calculate_score(self, solution: Solution, generator_solution: Solution | None, size: int) -> SupportsFloat:
        return solution.quality
