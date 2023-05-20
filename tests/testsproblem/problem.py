"""Problem class built for tests."""
from typing import ClassVar

from algobattle.problem import ProblemModel, SolutionModel
from algobattle.util import ValidationError


class TestProblem(ProblemModel):
    """Artificial problem used for tests."""

    name: ClassVar[str] = "Tests"
    with_solution: ClassVar[bool] = False

    class Solution(SolutionModel):
        """Solution class for :cls:`Tests`."""

        semantics: bool
        quality: bool

        def validate_solution(self, instance: "TestProblem"):
            if not self.semantics:
                raise ValidationError("")

    semantics: bool

    @property
    def size(self) -> int:
        return 0

    def validate_instance(self):
        if not self.semantics:
            raise ValidationError("")

    def calculate_score(self, solution: Solution, generator_solution: Solution | None) -> float:
        return solution.quality
