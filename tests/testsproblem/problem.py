"""Problem class built for tests."""

from algobattle.problem import Problem, InstanceModel, SolutionModel
from algobattle.util import Role, ValidationError


class TestInstance(InstanceModel):
    """Artificial problem used for tests."""

    semantics: bool

    @property
    def size(self) -> int:
        return 0

    def validate_instance(self):
        if not self.semantics:
            raise ValidationError("")


class TestSolution(SolutionModel[TestInstance]):
    """Solution class for :class:`Tests`."""

    semantics: bool
    quality: bool

    def validate_solution(self, instance: TestInstance, role: Role) -> None:
        if not self.semantics:
            raise ValidationError("")


def score(instance: TestInstance, solution: TestSolution) -> float:
    """Test score function."""
    return solution.quality


TestProblem = Problem(
    name="Test Problem",
    instance_cls=TestInstance,
    solution_cls=TestSolution,
    with_solution=False,
    score_function=score,
)
