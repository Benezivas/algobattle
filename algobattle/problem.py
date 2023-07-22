"""Module defining the Problem and Solution base classes and related objects."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import wraps
from importlib.metadata import entry_points
import importlib.util
import sys
from pathlib import Path
from typing import Any, Callable, ClassVar, ParamSpec, Protocol, Self, Generic, TypeVar
from math import inf, isnan

from algobattle.util import Role, Encodable, InstanceSolutionModel


class Instance(Encodable, ABC):
    """Instance base class."""

    @property
    @abstractmethod
    def size(self) -> int:
        """The instance's size."""
        raise NotImplementedError

    def validate_instance(self) -> None:
        """Confirms that the parsed instance is valid.

        Should be idempotent, but may also perform additional postprocessing such as bringing the instance
        into a normal form.

        Raises:
            ValidationError: if the created instance is invalid.
        """
        return


InstanceT = TypeVar("InstanceT", bound=Instance, contravariant=True)
P = ParamSpec("P")


class Solution(Encodable, Generic[InstanceT], ABC):
    """A proposed solution for an instance of this problem."""

    def validate_solution(self, instance: InstanceT, role: Role) -> None:
        """Confirms that the parsed solution is valid.

        Should be idempotent, but may also perform additional postprocessing such as bringing the solution
        into a normal form.

        Args:
            instance: The problem instance this solution is purported to solve.

        Raises:
            ValidationError: if the created instance is invalid.
        """
        return


class Scored(Solution[InstanceT]):
    """A solution with an associated score."""

    @abstractmethod
    def score(self, instance: InstanceT) -> float:
        """Calculate the score of this solution for the given problem instance.

        Args:
            instance: The instance this solution solves
        Returns:
            The calculates score of this solution. Must be a nonnegative number. Bigger scores are considered better,
            if your score rates better scores lower you can use the @minimize decorator.
        """
        raise NotImplementedError


def minimize(function: Callable[P, float]) -> Callable[P, float]:
    """Wraps a score function such that smaller scores are considered better."""

    @wraps(function)
    def inner(*args: P.args, **kwargs: P.kwargs) -> float:
        try:
            return 1 / function(*args, **kwargs)
        except ZeroDivisionError:
            return inf

    return inner


def maximize(function: Callable[P, float]) -> Callable[P, float]:
    """No-op decorator to indicate that bigger scores are considered better."""
    return function


SolutionT = TypeVar("SolutionT", bound=Solution[Any])


_I = TypeVar("_I", bound=Instance, contravariant=True)
_S = TypeVar("_S", bound=Solution[Instance], contravariant=True)


class ScoreFunction(Protocol, Generic[_I, _S]):
    """Type of `score` function passed to Problem."""

    def __call__(self, instance: _I, solver_solution: _S, generator_solution: _S | None) -> Any:
        """Calculates how well a solution solves this problem instance.

        Args:
            instance: The generated instance.
            solver_solution: The solution created by the solver.
            generator_solution: The solution output by the generator, if any.

        Returns:
            The calculated score, a number in [0, 1] with a value of 0 indicating that the solver failed completely and
            1 that it solved the instance perfectly.
        """


def default_score(instance: Instance, solver_solution: SolutionT, generator_solution: SolutionT | None) -> float:
    """Calculates how well a solution solves this problem instance.

    If the solution is `Scored` the score is the ratio of the generator's solution score to the solver's
    solution score. Otherwise, it simply defaults to 1 since the solver generated a valid solution.

    Args:
        instance: The generated instance.
        solver_solution: The solution created by the solver.
        generator_solution: The solution output by the generator, if any.

    Returns:
        The calculated score, a number in [0, 1] with a value of 0 indicating that the solver failed completely and
        1 that it solved the instance perfectly.
    """
    if isinstance(generator_solution, Scored):
        assert isinstance(solver_solution, Scored)
        gen_score = generator_solution.score(instance)
        if gen_score < 0 or isnan(gen_score):
            raise RuntimeError("Score function didn't return a nonnegative value.")
        sol_score = solver_solution.score(instance)
        if sol_score < 0 or isnan(sol_score):
            raise RuntimeError("Score function didn't return a nonnegative value.")

        try:
            return max(0, min(1, sol_score / gen_score))
        except ZeroDivisionError:
            return float(sol_score < 0)
    else:
        return 1


@dataclass(kw_only=True)
class Problem(Generic[InstanceT, SolutionT]):
    """The definition of a problem."""

    name: str
    """The name of the problem."""

    instance_cls: type[InstanceT]
    """Class defining what instances of this problem look like."""

    solution_cls: type[SolutionT]
    """Class definitng what solutions of this problem look like."""

    min_size: int = 0
    """Minimum size of valid instances of this problem."""

    with_solution: bool = True
    """Whether the generator should also create a solution."""

    export: bool = True
    """Wether the class should be exported.

    If a battle is run by specifying a module, exactly one Problem in it must have `export=True`. It will then be used
    to run the battle.
    """

    score: ScoreFunction[InstanceT, SolutionT] = default_score
    """Function used to score how well a solution solves a problem instance.

    The default scoring function uses the `Scored` protocol to compare the solver's solution to the generator's. If the
    used solution class does not support this, it  will always return 1 and thus score all valid solutions equally.

    The signature of the `score` function is as follows:

    Args:
        instance: The generated instance.
        solver_solution: The solution created by the solver.
        generator_solution: The solution output by the generator, if any.

    Returns:
        The calculated score, a number in [0, 1] with a value of 0 indicating that the solver failed completely and
        1 that it solved the instance perfectly.
    """

    _installed: ClassVar[dict[str, Self]] = {}

    def __post_init__(self) -> None:
        if self.export and self.name not in Problem._installed:
            Problem._installed[self.name] = self

    @classmethod
    def import_from_path(cls, path: Path) -> Self:
        """Try to import a Problem from a given path.

        The specified file will be imported using the standard python loaders. If the created module contains exactly
        one Problem with the `export` flag set, it will be imported.

        Args:
            path: A path to a module, or a folder containing an `__init__.py` or `problem.py` file.

        Raises:
            ValueError: If the path doesn't point to a module or the file cannot be imported properly.
        """
        if path.is_file():
            pass
        elif (path / "problem.py").is_file():
            path /= "problem.py"
        else:
            raise ValueError(f"'{path}' does not point to a python file or a proper parent folder of one.")

        try:
            spec = importlib.util.spec_from_file_location("_problem", path)
            assert spec is not None
            assert spec.loader is not None
            problem_module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = problem_module
            spec.loader.exec_module(problem_module)
        except Exception as e:
            raise ValueError from e

        try:
            problems = [obj for obj in vars(problem_module).values() if isinstance(obj, cls) and obj.export]
            match len(problems):
                case 0:
                    raise ValueError(f"'{path}' contains no Problems.")
                case 1:
                    problem = problems[0]
                case _:
                    raise ValueError(
                        f"'{path}' contains {len(problems)} different problems: {', '.join(p.name for p in problems)}."
                    )

            return problem

        finally:
            sys.modules.pop("_problem")

    @classmethod
    def all(cls) -> dict[str, Self]:
        """Returns a dictionary mapping the names of all installed problems to their python objects.

        It includes all Problem objects that have been created so far and ones exposed to the algobattle module via the
        `algobattle.problem` entrypoint hook.

        Raises:
            RuntimeError: If an entrypoint is not a Problem.
        """
        for entrypoint in entry_points(group="algobattle.problem"):
            if entrypoint.name not in Problem._installed:
                problem = entrypoint.load()
                if not isinstance(problem, cls):
                    raise RuntimeError(
                        f"The entrypoint '{entrypoint.name}' doesn't point to a problem but rather: {problem}."
                    )
                cls._installed[entrypoint.name] = problem
        return cls._installed


class InstanceModel(InstanceSolutionModel, Instance, ABC):
    """An instance that can easily be parsed to/from a json file."""

    def validate_instance(self) -> None:
        """Validate the instance again, this time also passing itself in the context.

        Very inefficient implementation to make SizeIndex and similar types work.
        """
        super().validate_instance()
        if self._validate_with_self("instance"):
            self.model_validate(self, context={"instance": self, "self": self, "role": Role.generator})


class SolutionModel(Solution[InstanceT], InstanceSolutionModel, ABC):
    """A solution that can easily be parsed to/from a json file."""

    def validate_solution(self, instance: InstanceT, role: Role) -> None:
        """Validate the solution again, this time also passing itself and the instance in the context.

        Very inefficient implementation to make SizeIndex and similar types work.
        """
        super().validate_solution(instance, role)
        if self._validate_with_self("solution"):
            self.model_validate(self, context={"instance": instance, "solution": self, "solution": self, "role": role})
