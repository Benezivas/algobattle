"""Abstract base class for problem classes used in concrete problem implementations."""
from abc import ABC, abstractmethod
import importlib.util
from inspect import isclass
import sys
from pathlib import Path
from typing import Any, ClassVar, Literal, Protocol, SupportsFloat, Self, Generic, TypeAlias, TypeVar, runtime_checkable

from pydantic import Field
from pydantic.generics import GenericModel

from algobattle.util import Encodable, EncodableModel, Role, inherit_docs, ValidationError


_Problem: TypeAlias = Any
_Solution: TypeAlias = Any


@runtime_checkable
class Scored(Protocol):
    """A solution with an associated score."""

    direction: ClassVar[Literal["minimize", "maximize"]]

    @abstractmethod
    def score(self, instance: _Problem, size: int) -> float:
        """Calculate the score of this solution for the given problem instance."""
        raise NotImplementedError


class Problem(Encodable, ABC):
    """Problem base class."""

    name: ClassVar[str]
    """The name of the problem."""

    min_size: ClassVar[int] = 0
    """Minimum size of valid instances of this problem."""

    with_solution: ClassVar[bool] = True
    """Whether an instance of this problem also comes with a solution."""

    export: ClassVar[bool] = False
    """Wether the class should be exported.

    Helps with uniquely specifying a class to be executed in a problem file. For more details view the documentation.
    """

    def __init_subclass__(cls, export: bool = True) -> None:
        if "export" not in cls.__dict__:
            cls.export = export
        return super().__init_subclass__()

    def validate_instance(self, size: int):
        """Validates that the parsed instance is semantically correct.

        Should raise a :cls:`ValidationError` if the created instance is invalid."""
        return

    def calculate_score(self, solution: _Solution, generator_solution: _Solution | None, size: int) -> SupportsFloat:
        """Calculates how well a solution solves this problem instance.

        Return values are should be inside [0, 1].
        With a value of 0 indicating that the solver failed completely
        and 1 that it solved the instance perfectly.
        """
        if isinstance(generator_solution, self.Solution) and isinstance(generator_solution, Scored):
            # we have a default impl if the problem comes with a generator solution and the solution type
            # implements the Scored protocol. we can't check data protocol subclass relationships at runtime
            # so we need to check if the solution is an instance instead.
            # we know that the generator's and solver's solutions are of the same type so we don't need to check both.
            assert isinstance(solution, Scored)
            gen_score = generator_solution.score(self, size)
            if gen_score == 0:
                return 1
            sol_score = solution.score(self, size)
            if sol_score == 0:
                return 0

            if generator_solution.direction == "minimize":
                return gen_score / sol_score
            else:
                return sol_score / gen_score
        else:
            raise NotImplementedError

    @classmethod
    def io_schema(cls) -> str | None:
        """Generates a schema specifying the I/O for this problem."""
        return None

    @staticmethod
    def _is_importable(val: Any):
        return isclass(val) and issubclass(val, Problem) and val.export

    @classmethod
    def import_from_path(cls, path: Path) -> type["Problem"]:
        """Try to import a Problem class object from a given path.

        Raises
        ------
        ValueError
            If the path doesn't point to a file containing a valid problem.
        """
        if path.is_file():
            pass
        elif (path / "__init__.py").is_file():
            path /= "__init__.py"
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
            problem_classes = [val for val in vars(problem_module).values() if cls._is_importable(val)]
            if len(problem_classes) == 0:
                raise ValueError(f"'{path}' contains no Problem classes.")
            elif len(problem_classes) == 1:
                problem_cls = problem_classes[0]
            elif hasattr(problem_classes, "Problem") and issubclass(getattr(problem_classes, "Problem"), Problem):
                problem_cls: type[Problem] = problem_module.Problem
            else:
                raise ValueError(f"'{path}' contains {len(problem_classes)} different problem classes!")

            if issubclass(problem_cls, EncodableModel):
                problem_cls.update_forward_refs(Solution=problem_cls.Solution)
            if issubclass(problem_cls.Solution, EncodableModel):
                problem_cls.Solution.update_forward_refs()
            return problem_cls

        except Exception as e:
            raise ValueError from e
        finally:
            sys.modules.pop("_problem")

    class Solution(Encodable, ABC):
        """A proposed solution for an instance of this problem."""

        @classmethod
        @abstractmethod
        def decode(cls: type[Self], source_dir: Path, size: int, team: Role) -> Self:
            """Parses the container output into problem data."""
            raise NotImplementedError

        @abstractmethod
        def encode(self, target_dir: Path, size: int, team: Role) -> None:
            """Encodes the solution into files that can be passed to docker containers."""
            raise NotImplementedError

        def validate_solution(self, instance: _Problem, size: int):
            """Validates that the parsed instance is semantically correct.

            Should raise a :cls:`ValidationError` if the created instance is invalid."""
            return

        @classmethod
        def io_schema(cls) -> str | None:
            """Generates a schema specifying the I/O for this solution."""
            return None


class ProblemModel(EncodableModel, Problem, ABC):
    """A Problem that can easily be parsed to/from a json file."""

    filename: ClassVar[str] = "instance.json"
    export: ClassVar[bool] = False

    @classmethod
    def io_schema(cls) -> str | None:
        """Generates the default json schema specifying the I/O for this problem."""
        return cls.schema_json(indent=4)

    class Config(EncodableModel.Config):
        """Pydantic config object to hide these fields in the json if someone redeclared them incorrectly."""

        fields: dict[str, Any] = {
            "filename": {"exclude": True},
            "name": {"exclude": True},
            "min_size": {"exclude": True},
            "has_solution": {"exclude": True},
            "Solution": {"exclude": True},
            "export": {"exclude": True},
        }


class SolutionModel(EncodableModel, Problem.Solution, ABC):
    """A solution that can easily be parsed to/from a json file."""

    filename: ClassVar[str] = "solution.json"

    @classmethod
    def io_schema(cls) -> str | None:
        """Generates the default json schema specifying the I/O for this solution."""
        return cls.schema_json(indent=4)

    class Config(EncodableModel.Config):
        """Pydantic config object to hide these fields in the json if someone redeclared them incorrectly."""

        fields: dict[str, Any] = {"filename": {"exclude": True}}


class DirectedGraph(ProblemModel):
    """Base class for problems on directed graphs."""

    export: ClassVar[bool] = False

    num_vertices: int = Field(ge=0, le=2**63 - 1)
    edges: list[tuple[int, int]] = Field(ge=0, le=2**63 - 1, unique_items=True)

    @inherit_docs
    def validate_instance(self, size: int):
        if self.num_vertices > size:
            raise ValidationError("Graph contains too many vertices.")
        if any(u >= self.num_vertices or v >= self.num_vertices for u, v in self.edges):
            raise ValidationError("Graph contains edges whose endpoints aren't valid vertices")


class UndirectedGraph(DirectedGraph):
    """Base class for problems on undirected graphs."""

    export: ClassVar[bool] = False

    @inherit_docs
    def validate_instance(self, size: int):
        super().validate_instance(size)
        if any(u == v for u, v in self.edges):
            raise ValidationError("Undirected graph contains self loops.")

        # we remove the redundant edge definitions to create an easy to use normal form
        normalized_edges: set[tuple[int, int]] = set()
        for u, v in self.edges:
            if (v, u) not in normalized_edges:
                normalized_edges.add((u, v))
        self.edges = list(normalized_edges)


Weight = TypeVar("Weight")


class EdgeWeights(DirectedGraph, GenericModel, Generic[Weight]):
    """Mixin for graphs with weighted edges."""

    edge_weights: list[Weight]

    @inherit_docs
    def validate_instance(self, size: int):
        super().validate_instance(size)
        if len(self.edge_weights) == len(self.edges):
            raise ValidationError("Number of edge weights doesn't match the number of edges.")


class VertexWeights(DirectedGraph, GenericModel, Generic[Weight]):
    """Mixin for graphs with weighted vertices."""

    vertex_weights: list[Weight]

    @inherit_docs
    def validate_instance(self, size: int):
        super().validate_instance(size)
        if len(self.vertex_weights) == self.num_vertices:
            raise ValidationError("Number of vertex weights doesn't match the number of vertices.")
