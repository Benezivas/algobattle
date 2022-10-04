"""Abstract base class for problem classes used in concrete problem implementations."""
from typing import Protocol

from algobattle.parser import Parser
from algobattle.verifier import Verifier


class Problem(Protocol):
    """Problem Class, bundling together the verifier and parser of a problem.

    Enforces the necessary attribute n_start which is the smallest iteration
    size for a problem as well as a flag indicating whether a problem is
    usable in an approximation setting.
    """

    name: str
    n_start: int
    """Lowest value on which a battle should be executed."""
    parser: Parser
    """Parser object for the corresponding problem."""
    verifier: Verifier
    """Verifier object for the corresponding problem."""
    approximable: bool
    """Boolean flag indicating whether a problem can have an approximate solution."""

    def generator_memory_scaler(self, memory, instance_size):
        """Method that scales the amount of memory of the generator in relation to the given instance size."""
        return memory

    def solver_memory_scaler(self, memory, instance_size):
        """Method that scales the amount of memory of the solver in relation to the given instance size."""
        return memory

    def __str__(self) -> str:
        return self.name
