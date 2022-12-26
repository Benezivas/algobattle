"""Abstract base class for problem classes used in concrete problem implementations."""
from abc import ABC
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar, get_type_hints
from pydantic import BaseModel

from algobattle.util import FileArchive


_Self = TypeVar("_Self", bound="Instance")


class ProblemError(Exception):
    """Parent class of all exceptions related to the problem module."""
    pass


class ContainerError(ProblemError):
    """Raised when the container returned malformed data."""
    pass


class Hidden:
    """Marker class indicating that a field will not be parsed into the solver input."""
    pass


class Instance(ABC, BaseModel):
    """Represents a specific instance of a problem."""

    @classmethod
    def parse(cls: type[_Self], source: FileArchive) -> _Self:
        """Parses the generator output into a problem instance.
        
        The default implementation expects the object to be json encoded at a file 'instance.json'.
        """
        try:
            return cls.parse_raw(source[Path("instance.json")])
        except KeyError:
            raise ContainerError

    def verify_semantics(self):
        """Validates that the instance is semantically correct."""
        pass

    def encode(self, **kwargs: dict[str, Any]) -> FileArchive:
        """Encodes the instance into files so it can be passed to docker containers.
        
        By default a single file `instance.json` is generated and attributes annotated with :cls:`Hidden` are ignored.
        Battle wrappers may specify additional arguments via `kwargs` to fine tune the info passed to containers.
        """
        return FileArchive({Path("instance.json"): self.json(exclude=self._excludes()).encode()})

    @classmethod
    def _excludes(cls) -> dict[str | int, Any]:
        excludes = {}
        for name, annotation in get_type_hints(cls, include_extras=True).items():
            if hasattr(annotation, "__metadata__") and Hidden in annotation.__metadata__:
                excludes[name] = True
            elif issubclass(annotation, Instance):
                excludes[name] = annotation._excludes()
        return excludes


_Self = TypeVar("_Self", bound="Solution")


class Solution(BaseModel):
    """Represents a potential solution to an instance of a problem."""

    @classmethod
    def parse(cls: type[_Self], source: FileArchive) -> _Self:
        """Parses the generator output into a problem instance.
        
        The default implementation expects the object to be json encoded at a file 'solution.json'.
        """
        try:
            return cls.parse_raw(source[Path("solution.json")])
        except KeyError:
            raise ContainerError


@dataclass(kw_only=True)
class Problem:
    """Dataclass specifying what a problem's instances and solutions look like."""

    name: str
    """Name of the problem."""
    start_size: int = 1
    """Smallest valid size for this problem"""
    instance_type: type[Instance]
    """Type of the instances of this problem."""
    solution_type: type[Solution]
    """Type of the solutions of this problem."""

    def __str__(self) -> str:
        return self.name
