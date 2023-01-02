"""Abstract base class for problem classes used in concrete problem implementations."""
from abc import ABC, abstractmethod
import importlib.util
import logging
import sys
from pathlib import Path
from typing import Any, ClassVar, SupportsFloat, Self
from algobattle.util import CustomEncodable, BaseModel, Role

logger = logging.getLogger("algobattle.problem")


class ProblemError(Exception):
    """Parent class of all exceptions related to the problem module."""
    pass


class ContainerError(ProblemError):
    """Raised when the container returned malformed data."""
    pass


class Problem(CustomEncodable, ABC):
    """Problem base class."""

    name: ClassVar[str]
    """The name of the problem."""

    min_size: ClassVar[int] = 0
    """Minimum size of valid instances of this problem."""

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

        def check_semantics(self, size: int, instance: Any) -> bool:
            """Validates that the parsed solution is semantically correct."""
            return True

    @abstractmethod
    def calculate_score(self, solution: Any, size: int) -> SupportsFloat:
        """Calculates how well a solution solves this problem instance.
        
        Return values are clamped to fall inside [0, 1].
        A value of 0 indicating that the solver failed completely
        and 1 that it solved the instance perfectly.
        """
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
            Problem = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = Problem
            spec.loader.exec_module(Problem)
            if isinstance(Problem, BaseModel):
                Problem.update_forward_refs(Solution=Problem.Solution)
            return Problem.Problem
        except Exception as e:
            logger.critical(f"Importing the given problem failed with the following exception: {e}")
            raise ValueError from e


class ProblemModel(BaseModel, Problem, ABC):
    """A Problem that can easily be parsed to/from a json file."""

    filename = "instance.json"

    class Config:
        fields = {
            "filename": {"exclude": True},
            "name": {"exclude": True},
            "min_size": {"exclude": True},
            "Solution": {"exclude": True},
        }


class SolutionModel(BaseModel, Problem.Solution, ABC):
    """A solution that can easily be parsed to/from a json file."""

    filename = "solution.json"

    class Config:
        fields = {
            "filename": {"exclude": True},
        }
