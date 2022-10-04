"""Abstract base class for verifiers used in concrete problem implementations."""
from __future__ import annotations
from abc import ABC, abstractmethod
import logging
from typing import Any

logger = logging.getLogger('algobattle.verifier')


class Verifier(ABC):
    """Verifier class, responsible for semantically checking parsed instances and solutions.

    Checks the validity of a solution against a given instance
    as well as verifying that a solution is of a demanded quality, which
    usually refers to the solution size.
    """

    def verify_semantics_of_instance(self, instance: Any, instance_size: int) -> bool:
        """Check the semantical correctness of an instance.

        For most problems, this function does not need to be overwritten.

        If the given instance is semantically ill-formed in a way that
        it cannot be passed to a solver, return False.

        Parameters
        ----------
        instance : Any
            The syntactically checked instance.
        instance_size : int
            The maximum instance size.

        Returns
        -------
        bool
            Returns True if the instance is processable by a solver.
        """
        if not instance:
            logger.error('The instance is empty!')
            return False
        return True

    def verify_semantics_of_solution(self, solution: Any, instance_size: int, solution_type: bool) -> bool:
        """Check whether a given solution is semantically correct.

        For most problems, this function does not need to be overwritten.

        Parameters
        ----------
        instance : Any
            The syntactically checked instance.
        solution : Any
            The syntactically checked solution.
        instance_size : int
            The maximum instance size.
        solution_type : bool
            Indicates whether the given solution is a certificate (True) or solver solution (False)

        Returns
        -------
        bool
            Returns True if the solution is semantically correct.
        """
        if not solution:
            logger.error('The solution is empty!')
            return False
        return True

    @abstractmethod
    def verify_solution_against_instance(self, instance: Any, solution: Any, instance_size: int, solution_type: bool) -> bool:
        """Check the validity of a solution against an instance.

        Parameters
        ----------
        instance : Any
            The syntactically checked instance.
        solution : Any
            The syntactically checked solution.
        instance_size : int
            The maximum instance size.
        solution_type : bool
            Indicates whether the given solution is a certificate (True) or solver solution (False)

        Returns
        -------
        bool
            Returns True if the solution is valid for the given instance.
        """
        raise NotImplementedError

    @abstractmethod
    def calculate_approximation_ratio(self, instance: Any, instance_size: int,
                                      generator_solution: Any, solver_solution: Any) -> float:
        """Calculate how good a solvers solution is compared to a generators solution.

        Assuming an approximation problem, this method returns the approximation
        factor of the solvers solution to the generators solution.

        Parameters
        ----------
        instance : Any
            The syntactically checked instance.
        instance_size : int
            The current iteration size.
        generator_solution : Any
            The syntactically checked generator solution.
        solver_solution : Any
            The syntactically checked solver solution.

        Returns
        -------
        float
            Returns the solution quality of the solver solution relative to the generator solution.
            The return value is the approximation ratio of the solver against
            the generator (1 if optimal, 0 if failed, else >1).
        """
        raise NotImplementedError
