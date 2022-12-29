"""Abstract base class for problem classes used in concrete problem implementations."""
from abc import ABC, abstractmethod
from dataclasses import InitVar, dataclass, field
from pathlib import Path
from typing import Any, Callable, ClassVar, Generic, Literal, Protocol, TypeVar, get_type_hints
from pydantic import BaseModel

from algobattle.util import inherit_docs


class ProblemError(Exception):
    """Parent class of all exceptions related to the problem module."""
    pass


class ContainerError(ProblemError):
    """Raised when the container returned malformed data."""
    pass


class Hidden:
    """Marker class indicating that a field will not be parsed into the solver input."""
    pass


_Self = TypeVar("_Self", bound="ProblemData")


class ProblemData(Protocol):
    """Represents problem data that docker containers can interact with."""

    @abstractmethod
    @classmethod
    def decode(cls: type[_Self], source_dir: Path, size: int) -> _Self:
        """Parses the container output into problem data."""
        ...

    def check_semantics(self, size: int) -> bool:
        """Validates that the parsed data is semantically correct."""
        ...

    @abstractmethod
    def encode(self, target_dir: Path, size: int, team: Literal["generator", "solver"]) -> None:
        """Encodes the problem data into files that can be passed to docker containers."""
        ...


_Self = TypeVar("_Self", bound="_JsonEncodable")


class _JsonEncodable(ProblemData, BaseModel, ABC):
    """Problem data that can easily be encoded into and decoded from json files."""

    filename: ClassVar[str]

    @inherit_docs
    @classmethod
    def decode(cls: type[_Self], source_dir: Path, size: int) -> _Self:
        try:
            return cls.parse_file(source_dir / cls.filename)
        except Exception as e:
            raise ContainerError from e

    @inherit_docs
    def check_semantics(self, size: int) -> bool:
        return True

    @inherit_docs
    def encode(self, target_dir: Path, size: int, team: Literal["generator", "solver"]) -> None:
        try:
            with open(target_dir / self.filename, "w") as f:
                f.write(self.json(exclude=self._excludes()))
        except Exception as e:
            raise ContainerError from e

    @classmethod
    def _excludes(cls) -> dict[str | int, Any]:
        excludes = {}
        for name, annotation in get_type_hints(cls, include_extras=True).items():
            if hasattr(annotation, "__metadata__") and Hidden in annotation.__metadata__:
                excludes[name] = True
            elif issubclass(annotation, _JsonEncodable):
                excludes[name] = annotation._excludes()
        return excludes


class Instance(_JsonEncodable, ABC):
    """Represents a specific instance of a problem."""

    filename = "instance.json"


class Solution(_JsonEncodable, ABC):
    """Represents a potential solution to an instance of a problem."""

    filename = "solution.json"


_InstanceT, _SolutionT = TypeVar("_InstanceT", bound=Instance), TypeVar("_SolutionT", bound=Solution)


@dataclass(kw_only=True, frozen=True)
class Problem(Generic[_InstanceT, _SolutionT]):
    """Dataclass specifying what a problem's instances and solutions look like."""

    name: str
    """Name of the problem."""
    start_size: int = 1
    """Smallest valid size for this problem"""
    instance_type: type[_InstanceT]
    """Type of the instances of this problem."""
    solution_type: type[_SolutionT]
    """Type of the solutions of this problem."""
    calculate_score: Callable[[_InstanceT, _SolutionT], float]
    """Scores a proposed solution for an instance.
    
    Return values are clamped to fall inside [0, 1].
    A value of 0 indicating that the solver failed completely
    and 1 that it solved the instance perfectly.
    """


@dataclass(kw_only=True, frozen=True)
class DecisionProblem(Problem[_InstanceT, _SolutionT]):
    """A :cls:`Problem` where all valid solutions are equally good."""

    calculate_score: Callable[[_InstanceT, _SolutionT], float] = field(init=False, default=lambda i, s: 1)


class OptimizationInstance(Instance, Protocol):
    """An instance that contains an optimal solution against which other solutions are checked."""

    solution: "OptimizationSolution"


class OptimizationSolution(Solution, Protocol):
    """A solution for an optimization problem."""

    @abstractmethod
    def valuate(self) -> float:
        """Evaluates this solution."""
        raise NotImplementedError


_OptiInstT, _OptiSolT = TypeVar("_OptiInstT", bound=OptimizationInstance), TypeVar("_OptiSolT", bound=OptimizationSolution)


@dataclass(kw_only=True, frozen=True)
class OptimizationProblem(Problem[_OptiInstT, _OptiSolT]):
    """A :cls:`Problem` that compares solver solutions to an optimal solution provided by the generator."""

    direction: InitVar[Literal["minimize", "maximize"]]
    calculate_score: Callable[[_OptiInstT, _OptiSolT], float] = field(init=False)

    def __post_init__(self, direction: Literal["minimize", "maximize"]):
        def score(instance: _OptiInstT, solution: _OptiSolT) -> float:
            gen = instance.solution.valuate()
            sol = solution.valuate()
            if gen == 0:
                return 1
            if sol == 0:
                return 0
            match direction:
                case "minimize":
                    score = gen / sol
                case "maximize":
                    score = sol / gen
            return max(0, min(1, score))
        object.__setattr__(self, "calculate_score", score)
