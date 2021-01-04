from abc import ABC, abstractmethod

class Verifier(ABC):

    @abstractmethod
    def verify_solution_against_instance(self, instance, solution, instance_size):
        """ Check the validity of a solution against an instace.

        Parameters:
        ----------
        instance: list
            The instance, given as a list of Tuples.
        solution: list
            The solution, given as a list of Tuples.
        instance_size: int
            The maximum instance size. 

        Returns:
        ----------
        bool
            Returns True if the solution is valid for the given instance.
        """
        raise NotImplementedError

    @abstractmethod
    def verify_solution_quality(self, generator_solution, solver_solution):
        """ Check if the solvers solution achieves the wanted quality over the generators solution.

        Parameters:
        ----------
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