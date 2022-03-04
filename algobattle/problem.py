"""Abstract base class for problem classes used in concrete problem implementations."""
from __future__ import annotations, generators
from dataclasses import dataclass
from enum import Enum
import logging
from typing import Callable, Generic, TypeVar

logger = logging.getLogger("algobattle.problem")


class ApproxType(Enum):
    minimize = 1
    maximize = 2

Instance = TypeVar("Instance")
Solution = TypeVar("Solution")
@dataclass
class Problem(Generic[Instance, Solution]):
    """Problem Class, bundling together the verifier and parser of a problem.
    Enforces the attributes needed for the battle algorithm to work with the problem.
    """

    name: str
    """Name of the Problem."""
    n_start: int
    """Minimum instance size."""
    approx_type: ApproxType
    """Wether the goal is to minimize or maximize the weight of the solution."""
    generator_memory_scaler: Callable[[int, int], int]
    """Scales the amount of memory the generator will be given.
    
    Parameters
    ----------
    memory: int
        The amount of unscaled memory.
    size: int
        The size of the instance.
    
    Returns
    -------
    int
        The scaled memory
    """
    solver_memory_scaler: Callable[[int, int], int]
    """Scales the amount of memory the solver will be given.
    
    Parameters
    ----------
    memory: int
        The amount of unscaled memory.
    size: int
        The size of the instance.
    
    Returns
    -------
    int
        The scaled memory
    """
    
    split_into_instance_and_solution: Callable[[str], tuple[str, str]]
    """Split an input into instance and solution, discard anything else.

    Parameters
    ----------
    input : str
        The raw input.

    Returns
    -------
    str, str
        Returns a tuple containing the instance and the solution.
        The lines may still be syntactially and semantically incorrect.
    """
    parse_instance: Callable[[str, int], Instance]
    """Parses an instance removing syntactically wrong elements and checking its semantic correctness.

    Parameters
    ----------
    instance : str
        The raw instance.
    instance_size : int
        The size of the instance.

    Returns
    -------
    Instance
        Returns the parsed instance.
    
    Raises
    ------
    ValueError
        If the input does not encode a valid instance.
    """
    parse_solution: Callable[[str, int], Solution]
    """Parses a solution removing syntactically wrong elements and checking its semantic correctness.

    Parameters
    ----------
    solution : str
        The raw solution.
    instance_size : int
        The size of the instance.

    Returns
    -------
    Solution
        Returns the parsed solution.
    
    Raises
    ------
    ValueError
        If the input does not encode a valid solution.
    """
    encode_instance: Callable[[Instance], str]
    """Encodes an instance back into a string. Inverse of parse_instance.
    
    Parameters
    ----------
    instance: Instance
        The instance to be encoded.
    
    Returns
    -------
    str
        The encoded instance.
    """
    verify_solution: Callable[[Instance, int, Solution], bool]
    """Check the validity of a solution against an instance.

    Parameters
    ----------
    instance : Instance
        The instance.
    solution : Solution
        The solution.
    instance_size : int
        The maximum instance size.
    
    Returns
    -------
    bool
        Whether the solution is valid for the given instance.
    """
    solution_weight: Callable[[Instance, int, Solution], float]
    """Calculates the weight of the given Solution.
    Typically this is it's size or the sum of its elements or similar.
    
    Parameters
    ----------
    instance: Instance
        The instance corresponding to the solution.
    size: int
        The size of the instance.
    solution: Solution
        The solution to calculate a weight of.
    
    Returns
    -------
    float
        The weight of the solution.
    """
    approx_cap: float = 5
    """The worst case cap for the approximation ratio. Only relevant to prevent outliers skewing any further calculations."""

    def approximation_ratio(self, instance: Instance, size: int, generator: Solution, solver: Solution) -> float:
        """Calculates the approximation ratio of the solver's solution.
        A higher number always means the solver did better, even if the goal of the problem is to minimize the solution weight.
        Assuming the generator found the best solution it will be a number between 0 and 1. An output of eg 0.5 indicates that
        the solver found a solution twice as big if the goal is to minimize the weight and half as big if the goal is to maximize.

        Parameters
        ----------
        instance: Instance
            The fight instance.
        size: int
            The instance's size.
        generator: Solution
            The generator's solution.
        solver: Solution
            The solver's solution.
        
        Returns
        -------
        float
            The approximation ratio.
        """
        generator_weight = self.solution_weight(instance, size, generator)
        solver_weight = self.solution_weight(instance, size, solver)

        if self.approx_type == ApproxType.maximize:
            if generator_weight != 0:
                return min(solver_weight / generator_weight, self.approx_cap)
            else:
                return self.approx_cap
        else:
            if solver_weight != 0:
                return min(generator_weight / solver_weight, self.approx_cap)
            else:
                return self.approx_cap

    def __str__(self) -> str:
        return self.name
