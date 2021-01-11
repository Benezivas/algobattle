from abc import ABC, abstractmethod

class Verifier(ABC):

    @abstractmethod
    def verify_solution_against_instance(self, instance, solution, instance_size, solution_type):
        """ Check the validity of a solution against an instace.

        Parameters:
        ----------
        instance: list
            The instance, given as a list of Tuples.
        solution: list
            The solution, given as a list of Tuples.
        instance_size: int
            The maximum instance size.
        solution_type: bool
            Indicates whether the given solution is a certificate (True) or solver solution (False)

        Returns:
        ----------
        bool
            Returns True if the solution is valid for the given instance.
        """
        raise NotImplementedError

    @abstractmethod
    def verify_solution_quality(self, instance, instance_size, generator_solution, solver_solution):
        """ Check if the solvers solution achieves the wanted quality over the generators solution.

        Parameters:
        ----------
        instance: list
            The instance, given as a list of Tuples.
        instance_size: int
            The current iteration size.
        generator_solution: list
            The generator solution, given as a list of Tuples.
        solver_solution: list
            The solvers solution, given as a list of Tuples.

        Returns:
        ----------
        bool
            Returns True if the solvers solution has the wanted quality over the generators solution.
        """
        return len(solver_solution) >= len(generator_solution)