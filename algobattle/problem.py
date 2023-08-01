"""Module defining the Problem and Solution base classes and related objects."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import wraps
from importlib.metadata import entry_points
import importlib.util
import sys
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    ClassVar,
    Literal,
    ParamSpec,
    Protocol,
    Self,
    Generic,
    TypeVar,
    overload,
)
from math import inf, isnan

from algobattle.util import EncodableModel, Role, Encodable, inherit_docs


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

    @inherit_docs
    @classmethod
    @abstractmethod
    def decode(cls, source: Path, max_size: int, role: Role, instance: InstanceT | None = None) -> Self:
        raise NotImplementedError

    def validate_solution(self, instance: InstanceT, role: Role) -> None:
        """Confirms that the parsed solution is valid.

        Should be idempotent, but may also perform additional postprocessing such as bringing the solution
        into a normal form.

        Args:
            instance: The problem instance this solution is purported to solve.
            role: The role of the team that generated this solution.

        Raises:
            ValidationError: if the created instance is invalid.
        """
        return

    def score(self, instance: InstanceT, role: Role) -> float:
        """Calculate the score of this solution for the given problem instance.

        The default implementation always returns 1, indicating that all solutions of this problem are equally good.

        Args:
            instance: The instance this solution solves
            role: The role of the team that generated this solution
        Returns:
            The calculates score of this solution. Must be a nonnegative number. Bigger scores are considered better,
            if your score rates better scores lower you can use the @minimize decorator.
        """
        return 1


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


class ScoreFunctionWithSol(Protocol, Generic[_I, _S]):
    """Type of `score` function passed to Problem if `with_solution` is set."""

    def __call__(self, instance: _I, *, generator_solution: _S, solver_solution: _S) -> float:
        """Calculates how well a solution solves this problem instance.

        Args:
            instance: The generated instance.
            generator_solution: The solution output by the generator.
            solver_solution: The solution created by the solver.

        Returns:
            The calculated score, a number in [0, 1] with a value of 0 indicating that the solver failed completely and
            1 that it solved the instance perfectly.
        """
        ...


class ScoreFunctionNoSol(Protocol, Generic[_I, _S]):
    """Type of `score` function passed to Problem if `with_solution` is not set."""

    def __call__(self, instance: _I, *, solution: _S) -> float:
        """Calculates how well a solution solves this problem instance.

        Args:
            instance: The generated instance.
            solution: The solution output by the generator.

        Returns:
            The calculated score, a number in [0, 1] with a value of 0 indicating that the solver failed completely and
            1 that it solved the instance perfectly.
        """
        ...


ScoreFunction = ScoreFunctionWithSol[InstanceT, SolutionT] | ScoreFunctionNoSol[InstanceT, SolutionT]


@overload
def default_score(instance: Instance, *, solution: Solution[Instance]) -> float:
    ...


@overload
def default_score(instance: Instance, *, generator_solution: SolutionT, solver_solution: SolutionT) -> float:
    ...


def default_score(
    instance: Instance,
    solution: SolutionT | None = None,
    generator_solution: SolutionT | None = None,
    solver_solution: SolutionT | None = None,
) -> float:
    """Calculates how well a solution solves this problem instance.

    If the problem is `with_solution` it calculates the ratio between the solver's and generator's solutions.
    Otherwise it just returns the solution's score clamped to [0, 1].

    Args:
        instance: The generated instance.
        solution: The solution if the problem is with_solution=False.
        solver_solution: The solution created by the solver.
        generator_solution: The solution output by the generator.

    Returns:
        The calculated score, a number in [0, 1] with a value of 0 indicating that the solver failed completely and
        1 that it solved the instance perfectly.
    """
    if solution is None:
        assert generator_solution is not None
        assert solver_solution is not None
        gen_score = generator_solution.score(instance, Role.generator)
        if gen_score < 0 or isnan(gen_score):
            raise RuntimeError("Score function didn't return a nonnegative value.")
        sol_score = solver_solution.score(instance, Role.solver)
        if sol_score < 0 or isnan(sol_score):
            raise RuntimeError("Score function didn't return a nonnegative value.")

        try:
            return max(0, min(1, sol_score / gen_score))
        except ZeroDivisionError:
            return float(sol_score < 0)
    else:
        return max(0, min(1, solution.score(instance, Role.solver)))


@dataclass(kw_only=True)
class ProblemBase(Generic[InstanceT, SolutionT]):
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

    score_function: ScoreFunction[InstanceT, SolutionT] = default_score
    """Function used to score how well a solution solves a problem instance.

    The default scoring function uses the `Scored` protocol to compare the solver's solution to the generator's. If the
    used solution class does not support this, it  will always return 1 and thus score all valid solutions equally.

    The score function always takes the instance as the first argument. If `with_solution` is set it then gets the
    generated solutions at `generator_solution` and `solver_solution`. If it is not set it receives the solver's
    solution at `solution`. It should return the calculated score, a number in [0, 1] with a value of 0 indicating that
    the solver failed completely and 1 that it solved the instance perfectly.
    """

    _installed: ClassVar[dict[str, Self]] = {}

    def __post_init__(self) -> None:
        if self.export and self.name not in ProblemBase._installed:
            ProblemBase._installed[self.name] = self

    @overload
    def score(self, instance: InstanceT, *, solution: SolutionT) -> float:
        ...

    @overload
    def score(self, instance: InstanceT, *, generator_solution: SolutionT, solver_solution: SolutionT) -> float:
        ...

    def score(
        self,
        instance: InstanceT,
        *,
        solution: SolutionT | None = None,
        generator_solution: SolutionT | None = None,
        solver_solution: SolutionT | None = None,
    ) -> float:
        """Helper function to call self.score_function with easier to use overloads."""
        if self.with_solution:
            if solution is not None or generator_solution is None or solver_solution is None:
                raise TypeError
            if TYPE_CHECKING:
                assert isinstance(self.score_function, ScoreFunctionWithSol)
            return self.score_function(instance, generator_solution=generator_solution, solver_solution=solver_solution)
        else:
            if solution is None or generator_solution is not None or solver_solution is not None:
                raise TypeError
            if TYPE_CHECKING:
                assert isinstance(self.score_function, ScoreFunctionNoSol)
            return self.score_function(instance, solution=solution)

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
            if entrypoint.name not in cls._installed:
                problem = entrypoint.load()
                if not isinstance(problem, cls):
                    raise RuntimeError(
                        f"The entrypoint '{entrypoint.name}' doesn't point to a problem but rather: {problem}."
                    )
                cls._installed[entrypoint.name] = problem
        return cls._installed


# Helper class to provide overloads for the __init__ so that score function type and with_solution match up
class Problem(ProblemBase[InstanceT, SolutionT]):
    """The definition of a problem."""

    @inherit_docs
    @overload
    def __init__(
        self,
        *,
        name: str,
        instance_cls: type[InstanceT],
        solution_cls: type[SolutionT],
        min_size: int = 0,
        with_solution: Literal[True] = True,
        export: bool = True,
        score_function: ScoreFunctionWithSol[InstanceT, SolutionT] = default_score,
    ) -> None:
        ...

    @inherit_docs
    @overload
    def __init__(
        self,
        *,
        name: str,
        instance_cls: type[InstanceT],
        solution_cls: type[SolutionT],
        min_size: int = 0,
        with_solution: Literal[False],
        export: bool = True,
        score_function: ScoreFunctionNoSol[InstanceT, SolutionT] = default_score,
    ) -> None:
        ...

    @inherit_docs
    def __init__(self, *args, **kwargs) -> None:
        return super().__init__(*args, **kwargs)


class InstanceModel(Instance, EncodableModel, ABC):
    """An instance that can easily be parsed to/from a json file."""

    _algobattle_model_type: ClassVar[Literal["instance"]] = "instance"


class SolutionModel(Solution[InstanceT], EncodableModel, ABC):
    """A solution that can easily be parsed to/from a json file."""

    _algobattle_model_type: ClassVar[Literal["solution"]] = "solution"

    @classmethod
    def decode(cls, source: Path, max_size: int, role: Role, instance: InstanceT | None = None) -> Self:
        """Uses pydantic to create a python object from a `.json` file."""
        context = {"max_size": max_size, "role": role}
        if instance is not None:
            context["instance"] = instance
        return cls._decode(source, **context)
