"""Abstract base class for problem classes used in concrete problem implementations."""
from abc import ABC
from dataclasses import dataclass
from io import BytesIO
from tarfile import TarFile
from typing import Type, TypeVar
from pydantic import BaseModel


_Self = TypeVar("_Self", bound="Instance")


class ProblemError(Exception):
    """Parent class of all exceptions related to the problem module."""
    pass


class ContainerError(ProblemError):
    """Raised when the container returned malformed data."""
    pass


class Instance(ABC, BaseModel):
    """Represents a specific instance of a problem."""

    @classmethod
    def parse(cls: Type[_Self], archive: bytes) -> _Self:
        """Parses the generator output into a problem instance."""
        with BytesIO(initial_bytes=archive) as fh, TarFile.open(fileobj=fh, mode="r") as tar:
            try:
                output_file = tar.extractfile("output")
                assert output_file is not None
            except (KeyError, AssertionError):
                raise ContainerError
            return cls.parse_raw(output_file.read())


class Solution(BaseModel):
    """Represents a potential solution to an instance of a problem."""


@dataclass(kw_only=True)
class Problem:
    """Dataclass specifying what a problem's instances and solutions look like."""

    name: str
    """Name of the problem."""
    start_size: int = 1
    """Smallest valid size for this problem"""
    instance_type: Type[Instance]
    """Type of the instances of this problem."""
    solution_type: Type[Solution]
    """Type of the solutions of this problem."""

    def __str__(self) -> str:
        return self.name
