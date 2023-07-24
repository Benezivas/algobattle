"""Module defining the Problem and Solution base classes and related objects."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import wraps
from importlib.metadata import entry_points
import importlib.util
import sys
from pathlib import Path
from typing import Any, Callable, ClassVar, Literal, ParamSpec, Protocol, Self, Generic, TypeVar, cast, get_args
from math import inf, isnan

from pydantic import GetCoreSchemaHandler, ValidationInfo
from pydantic_core import CoreSchema
from pydantic_core.core_schema import general_after_validator_function
from pydantic._internal._decorators import inspect_validator

from algobattle.util import Role, Encodable, EncodableModel


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
            role: The role of the team that generated this solution.

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


class InstanceSolutionModel(EncodableModel, ABC):
    """Base Model class for instances or solution classes."""

    @classmethod
    def _annotation_needs_self(cls, annotation: object, model_type: Literal["instance", "solution"]) -> bool:
        if isinstance(annotation, AttributeReferenceValidator):
            return annotation.needs_self(model_type)
        return any(cls._annotation_needs_self(e, model_type) for e in get_args(annotation))

    @classmethod
    def _validate_with_self(cls, model_type: Literal["instance", "solution"]) -> bool:
        return any(cls._annotation_needs_self(info.annotation, model_type) for info in cls.model_fields.values())


ModelReference = Literal["instance", "solution", "self"]


@dataclass(frozen=True, slots=True)
class AttributeReference:
    """Creates a reference to the attribute of a model to be used in validaton schemas."""

    model: ModelReference
    attribute: str

    def get_value(self, info: ValidationInfo) -> Any | None:
        """Returns the referenced value from the correct object in the info context.

        If the correct object is not in the context or doesn't have the referenced attribute it returns None.
        """
        if info.context is None or self.model not in info.context:
            return None
        model = info.context[self.model]
        if hasattr(model, self.attribute):
            return getattr(model, self.attribute)
        else:
            return None

    def __str__(self) -> str:
        return f"{self.model}.{self.attribute}"

    def needs_self(self, model_type: Literal["instance", "solution"]) -> bool:
        """Checks if an attribute reference needs a reference to the current model in order to be resolved."""
        if self.model == "self":
            return True
        else:
            return self.model == model_type


NoInfoAttrValidatorFunction = Callable[[Any, Any], Any]
GeneralAttrValidatorFunction = Callable[[Any, Any, ValidationInfo], Any]
AttrValidatorFunction = NoInfoAttrValidatorFunction | GeneralAttrValidatorFunction


@dataclass(frozen=True, slots=True)
class AttributeReferenceValidator:
    """An AfterValidator that can resolve a reference to a model attribute and pass it to the validator function.

    Using this with a reference to an attribute in the model it is defined may significantly impact performance.
    """

    func: AttrValidatorFunction
    attribute: AttributeReference

    def __get_pydantic_core_schema__(self, source_type: Any, handler: GetCoreSchemaHandler) -> CoreSchema:
        schema = handler(source_type)
        info_arg = inspect_validator(self.func, "after")
        if info_arg:
            func = cast(GeneralAttrValidatorFunction, self.func)

            def wrapper(value: Any, info: ValidationInfo) -> Any:
                attribute_val = self.attribute.get_value(info)
                if attribute_val is None:
                    return value
                return func(value, attribute_val, info)

        else:
            func = cast(NoInfoAttrValidatorFunction, self.func)

            def wrapper(value: Any, info: ValidationInfo) -> Any:
                attribute_val = self.attribute.get_value(info)
                if attribute_val is None:
                    return value
                return func(value, attribute_val)

        return general_after_validator_function(wrapper, schema=schema)

    def needs_self(self, model_type: Literal["instance", "solution"]) -> bool:
        """Checks if the validator needs a reference to the current model in order to work fully."""
        if self.attribute.model == "self":
            return True
        else:
            return self.attribute.model == model_type


@dataclass
class AttributeReferenceMaker:
    """Helper class to easily create attribute references."""

    _attr_ref_maker_model: ModelReference

    def __getattr__(self, __name: str) -> Any:
        return AttributeReference(self._attr_ref_maker_model, __name)


SelfRef = AttributeReferenceMaker("self")


InstanceRef = AttributeReferenceMaker("instance")


SolutionRef = AttributeReferenceMaker("solution")


class InstanceModel(InstanceSolutionModel, Instance, ABC):
    """An instance that can easily be parsed to/from a json file."""

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        super().__pydantic_init_subclass__(**kwargs)
        for name in cls.model_fields:
            setattr(cls, name, AttributeReference("instance", name))

    def validate_instance(self) -> None:
        """Validate the instance again, this time also passing itself in the context.

        Very inefficient implementation to make SizeIndex and similar types work.
        """
        super().validate_instance()
        if self._validate_with_self("instance"):
            self.model_validate(self, context={"instance": self, "self": self, "role": Role.generator})


class SolutionModel(Solution[InstanceT], InstanceSolutionModel, ABC):
    """A solution that can easily be parsed to/from a json file."""

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        super().__pydantic_init_subclass__(**kwargs)
        for name in cls.model_fields:
            setattr(cls, name, AttributeReference("solution", name))

    def validate_solution(self, instance: InstanceT, role: Role) -> None:
        """Validate the solution again, this time also passing itself and the instance in the context.

        Very inefficient implementation to make SizeIndex and similar types work.
        """
        super().validate_solution(instance, role)
        if self._validate_with_self("solution"):
            self.model_validate(self, context={"instance": instance, "solution": self, "self": self, "role": role})
