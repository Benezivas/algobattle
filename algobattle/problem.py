"""Abstract base class for problem classes used in concrete problem implementations."""
from abc import ABC
from dataclasses import dataclass
from typing import Type
from pydantic import BaseModel

class Instance(ABC, BaseModel):
    """Represents a specific instance of a problem."""

    @classmethod
    def parse(cls, source: )


class Solution(BaseModel):
    """Represents a potential solution to an instance of a problem."""


@dataclass(kw_only=True)
class Problem:
    """Dataclass specifying what a problem's instances and solutions look like."""

    name: str
    """Name of the problem."""
    n_start: int = 1
    """Lowest value of n valid for this problem"""
    instance_type: Type[Instance]
    """Type of the instances of this problem."""
    solution_type: Type[Solution]
    """Type of the solutions of this problem."""

    def __str__(self) -> str:
        return self.name
