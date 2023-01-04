"""Abstract base class for problem classes used in concrete problem implementations."""
from abc import ABC, abstractmethod
import importlib.util
import logging
import sys
from pathlib import Path
from typing import Any, ClassVar, Literal, Protocol, SupportsFloat, Self, Generic, TypeAlias, TypeVar, runtime_checkable
from pydantic import Field
from pydantic.generics import GenericModel
from algobattle.util import CustomEncodable, EncodableModel, Role

logger = logging.getLogger("algobattle.problem")


_Problem: TypeAlias = Any
_Solution: TypeAlias = Any


class ProblemError(Exception):
    """Parent class of all exceptions related to the problem module."""
    pass


class ContainerError(ProblemError):
    """Raised when the container returned malformed data."""
    pass


@runtime_checkable
class Scored(Protocol):
    """A solution with an associated score."""

    direction: ClassVar[Literal["minimize", "maximize"]]

    @abstractmethod
    def score(self, size: int, instance: _Problem) -> float:
        """Calculate the score of this solution for the given problem instance."""
        raise NotImplementedError  


class Problem(CustomEncodable, ABC):
    """Problem base class."""

    name: ClassVar[str]
    """The name of the problem."""

    min_size: ClassVar[int] = 0
    """Minimum size of valid instances of this problem."""

    with_solution: ClassVar[bool] = True
    """Whether an instance of this problem also comes with a solution."""

    solution: "Solution | None"
    """The generator's solution for this instance."""

    @classmethod
    @abstractmethod
    def decode(cls: type[Self], source_dir: Path, size: int) -> Self:
        """Parses the container output into a problem instance."""
        raise NotImplementedError

    @abstractmethod
    def encode(self, target_dir: Path, size: int, team: Role) -> None:
        """Encodes the problem instance into files that can be passed to docker containers."""
        raise NotImplementedError

    def check_semantics(self, size: int) -> bool:
        """Validates that the parsed instance is semantically correct."""
        return True

    def calculate_score(self, solution: _Solution, size: int) -> SupportsFloat:
        """Calculates how well a solution solves this problem instance.
        
        Return values are should be inside [0, 1].
        With a value of 0 indicating that the solver failed completely
        and 1 that it solved the instance perfectly.
        """
        if isinstance(self.solution, self.Solution) and isinstance(self.solution, Scored):
            # we have a default impl if the problem comes with a generator solution and the solution type implements the ScoredSolution protocol
            # we can't check data protocol subclass relationships at runtime so we need to check if the solution is an instance instead
            # we know that the generator's and solver's solutions are of the same type so we don't need to check both
            assert isinstance(solution, Scored)
            gen_score = self.solution.score(size, self)
            if gen_score == 0:
                return 1
            sol_score = solution.score(size, self)
            if sol_score == 0:
                return 0

            if self.solution.direction == "minimize":
                return gen_score / sol_score
            else:
                return sol_score / gen_score 
        else:
            raise NotImplementedError

    @staticmethod
    def import_from_path(path: Path) -> type["Problem"]:
        """Try to import a Problem class object from a given path.

        Raises
        ------
        ValueError
            If the path doesn't point to a file containing a valid problem.
        """
        if not (path / "__init__.py").is_file():
            raise ValueError

        try:
            spec = importlib.util.spec_from_file_location("problem", path / "__init__.py")
            assert spec is not None
            assert spec.loader is not None
            problem_module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = problem_module
            spec.loader.exec_module(problem_module)
            problem_cls = problem_module.Problem
            if not issubclass(problem_cls, Problem):
                raise ValueError(f"Variable 'Problem' in {path / '__init__.py'} is not a Problem class.")
            if issubclass(problem_cls, EncodableModel):
                problem_cls.update_forward_refs(Solution=problem_cls.Solution)
            if issubclass(problem_cls.Solution, EncodableModel):
                problem_cls.Solution.update_forward_refs()
            return problem_cls
        except Exception as e:
            logger.critical(f"Importing the given problem failed with the following exception: {e}")
            raise ValueError from e

    class Solution(CustomEncodable, ABC):
        """A proposed solution for an instance of this problem."""

        @classmethod
        @abstractmethod
        def decode(cls: type[Self], source_dir: Path, size: int) -> Self:
            """Parses the container output into problem data."""
            raise NotImplementedError

        @abstractmethod
        def encode(self, target_dir: Path, size: int, team: Role) -> None:
            """Encodes the solution into files that can be passed to docker containers."""
            raise NotImplementedError

        def check_semantics(self, size: int, instance: _Problem) -> bool:
            """Validates that the parsed solution is semantically correct."""
            return True


class ProblemModel(EncodableModel, Problem, ABC):
    """A Problem that can easily be parsed to/from a json file."""

    filename: ClassVar[str] = "instance.json"

    class Config:
        fields = {
            "filename": {"exclude": True},
            "name": {"exclude": True},
            "min_size": {"exclude": True},
            "Solution": {"exclude": True},
            "has_solution": {"exclude": True},
            "solution": {"exclude": True},
        }


class SolutionModel(EncodableModel, Problem.Solution, ABC):
    """A solution that can easily be parsed to/from a json file."""

    filename: ClassVar[str] = "solution.json"

    class Config:
        fields = {
            "filename": {"exclude": True},
        }


class DirectedGraph(ProblemModel):
    """Base class for problems on directed graphs."""

    num_vertices: int = Field(ge=0, le=2**63-1)
    edges: list[tuple[int, int]] = Field(ge=0, le=2**63-1)

    def check_semantics(self, size: int) -> bool:
        return (
            self.num_vertices <= size
            and all(u < self.num_vertices and v < self.num_vertices for u, v in self.edges)
            and len(self.edges) == len(set(self.edges))
        )


class UndirectedGraph(DirectedGraph):
    """Base class for problems on undirected graphs."""

    def check_semantics(self, size: int) -> bool:
        if not super().check_semantics(size):
            return False
        edges = set(self.edges)
        return (
            all(u != v for u, v in edges)
            and all((v, u) not in edges for u, v in edges)
        )


Weight = TypeVar("Weight")


class EdgeWeights(GenericModel, Generic[Weight]):
    """Mixin for graphs with weighted edges."""

    edge_weights: list[Weight]

    def check_semantics(self, size: int) -> bool:
        assert isinstance(self, DirectedGraph)
        as_parent = super()
        if isinstance(as_parent, Problem):
            if not as_parent.check_semantics(size):
                return False

        return len(self.edge_weights) == len(self.edges)


class VertexWeights(GenericModel, Generic[Weight]):
    """Mixin for graphs with weighted vertices."""

    vertex_weights: list[Weight]

    def check_semantics(self, size: int) -> bool:
        assert isinstance(self, DirectedGraph)
        as_parent = super()
        if isinstance(as_parent, Problem):
            if not as_parent.check_semantics(size):
                return False

        return len(self.vertex_weights) == self.num_vertices