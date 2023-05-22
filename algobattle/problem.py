"""Module defining the Problem and Solution base classes and related objects."""
from abc import ABC, abstractmethod
from importlib.metadata import entry_points
import importlib.util
from inspect import isclass
import sys
from pathlib import Path
from typing import Any, ClassVar, Literal, Protocol, Self, Generic, TypeAlias, TypeVar, runtime_checkable

from pydantic import Field
from pydantic.generics import GenericModel

from algobattle.util import u64, Encodable, EncodableModel, ValidationError


_Problem: TypeAlias = Any
"""Type alias used to generate correct typings when subclassing :cls:`Problem` and :cls:`Problem.Solution`.

Each problem's and solution's methods are guaranteed to be passed a instance of the correct problem/solution objects.
But due to limitations in the python type system we are currently not able to express this properly.
When creating your own problem it is recommended to not use this alias and instead use the :cls:`Problem` and
:cls:`Solution` you are creating directly.
"""
_Solution: TypeAlias = Any
"""Type alias used to generate correct typings when subclassing :cls:`Problem` and :cls:`Problem.Solution`.

Each problem's and solution's methods are guaranteed to be passed a instance of the correct problem/solution objects.
But due to limitations in the python type system we are currently not able to express this properly.
When creating your own problem it is recommended to not use this alias and instead use the :cls:`Problem` and
:cls:`Solution` you are creating directly.
"""


@runtime_checkable
class Scored(Protocol):
    """A solution with an associated score."""

    direction: ClassVar[Literal["minimize", "maximize"]]
    """The direction that better scores are found at."""

    @abstractmethod
    def score(self, instance: _Problem) -> float:
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

    _installed: ClassVar[dict[str, type["Problem"]]] = {}

    def __init_subclass__(cls, export: bool = True) -> None:
        if "export" not in cls.__dict__:
            cls.export = export
        if cls.export and cls.name not in Problem._installed:
            Problem._installed[cls.name] = cls
        return super().__init_subclass__()

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

    def score(self, solver_solution: _Solution, generator_solution: _Solution | None) -> float:
        """Calculates how well a solution solves this problem instance.

        If the solution is :cls:`Scored` the score is the ratio of the generator's solution score to the solver's
        solution score. Otherwise, it simply defaults to 1 since the solver generated a valid solution.

        Args:
            solver_solution: The solution created by the solver.
            generator_solution: The solution output by the generator, if any.

        Returns:
            The calculated score, a number in [0, 1] with a value of 0 indicating that the solver failed completely and
            1 that it solved the instance perfectly.
        """
        if isinstance(generator_solution, self.Solution) and isinstance(generator_solution, Scored):
            assert isinstance(solver_solution, Scored)
            gen_score = generator_solution.score(self)
            if gen_score == 0:
                return 1
            sol_score = solver_solution.score(self)
            if sol_score == 0:
                return 0

            if generator_solution.direction == "minimize":
                return gen_score / sol_score
            else:
                return sol_score / gen_score
        else:
            return 1

    @staticmethod
    def _is_importable(val: Any):
        return isclass(val) and issubclass(val, Problem) and val.export

    @classmethod
    def import_from_path(cls, path: Path) -> type[Self]:
        """Try to import a Problem class object from a given path.

        The specified file will be imported using the standard python loaders. If the created module contains exactly
        one class inheriting from :cls:`Problem` with the `export` flag set, it will be imported. Otherwise, if one of
        the classes is named `Problem` it will be imported. If neither procedure finds a unique problem class the method
        fails.

        Args:
            path: A path to a python file or a folder containing a `__init__.py` or `problem.py` file.

        Raises:
            ValueError: If the path doesn't point to a valid file or the file cannot be imported properly.
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
            problem_classes = [val for val in vars(problem_module).values() if cls._is_importable(val)]
            if len(problem_classes) == 0:
                raise ValueError(f"'{path}' contains no Problem classes.")
            elif len(problem_classes) == 1:
                problem_cls = problem_classes[0]
            elif hasattr(problem_classes, "Problem") and issubclass(getattr(problem_classes, "Problem"), Problem):
                problem_cls: type[Self] = problem_module.Problem
            else:
                raise ValueError(f"'{path}' contains {len(problem_classes)} different problem classes!")

            if issubclass(problem_cls, EncodableModel):
                problem_cls.update_forward_refs(Solution=problem_cls.Solution)
            if issubclass(problem_cls.Solution, EncodableModel):
                problem_cls.Solution.update_forward_refs()
            return problem_cls

        finally:
            sys.modules.pop("_problem")

    @classmethod
    def all(cls) -> dict[str, type[Self]]:
        """Returns a dictionary mapping the names of all installed problems to their python classes.

        It includes all subclasses of :cls:`Problem` that have been initialized so far, including ones exposed to the
        algobattle module via the `algobattle.problem` entrypoint hook.

        Raises:
            RuntimeError: If an entrypoint is not a problem class.
        """
        for entrypoint in entry_points(group="algobattle.problem"):
            if entrypoint.name not in Problem._installed:
                problem = entrypoint.load()
                if not issubclass(problem, cls):
                    raise RuntimeError(
                        f"The entrypoint '{entrypoint.name}' doesn't point to a problem class but rather: {problem}."
                    )
                cls._installed[entrypoint.name] = problem
        return cls._installed

    class Solution(Encodable, ABC):
        """A proposed solution for an instance of this problem."""

        def validate_solution(self, instance: _Problem) -> None:
            """Confirms that the parsed solution is valid.

            Should be idempotent, but may also perform additional postprocessing such as bringing the solution
            into a normal form.

            Args:
                instance: The problem instance this solution is purported to solve.

            Raises:
                ValidationError: if the created instance is invalid.
            """
            return


class ProblemModel(EncodableModel, Problem, ABC):
    """A Problem that can easily be parsed to/from a json file."""

    export: ClassVar[bool] = False

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

    class Config(EncodableModel.Config):
        """Pydantic config object to hide these fields in the json if someone redeclared them incorrectly."""

        fields: dict[str, Any] = {"filename": {"exclude": True}}


class DirectedGraph(ProblemModel):
    """Base class for problems on directed graphs."""

    export: ClassVar[bool] = False

    num_vertices: u64
    edges: list[tuple[u64, u64]] = Field(unique_items=True)

    @property
    def size(self) -> int:
        """A graph's size is the number of vertices in it."""
        return self.num_vertices

    def validate_instance(self):
        """Validates that the graph contains at most `size` many vertices and all edges are well defined."""
        if any(u >= self.num_vertices for edge in self.edges for u in edge):
            raise ValidationError("Graph contains edges whose endpoints aren't valid vertices")


class UndirectedGraph(DirectedGraph):
    """Base class for problems on undirected graphs."""

    export: ClassVar[bool] = False

    def validate_instance(self):
        """Validates that the graph is well formed and contains no self loops.

        Also brings it into a normal form where every edge {u, v} occurs exactly once in the list.
        I.e. `[(0, 1), (1, 0), (1, 2)]` is accepted as valid and normalised to `[(0, 1), (1, 2)]`.
        """
        super().validate_instance()
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

    export: ClassVar[bool] = False

    edge_weights: list[Weight]

    def validate_instance(self):
        """Validates that each edge has an associated weight."""
        super().validate_instance()
        if len(self.edge_weights) != len(self.edges):
            raise ValidationError("Number of edge weights doesn't match the number of edges.")


class VertexWeights(DirectedGraph, GenericModel, Generic[Weight]):
    """Mixin for graphs with weighted vertices."""

    export: ClassVar[bool] = False

    vertex_weights: list[Weight]

    def validate_instance(self):
        """Validates that each vertex has an associated weight."""
        super().validate_instance()
        if len(self.vertex_weights) != self.num_vertices:
            raise ValidationError("Number of vertex weights doesn't match the number of vertices.")
