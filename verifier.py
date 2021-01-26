from abc import ABC, abstractmethod

class Verifier(ABC):
    """ Verifier class, responsible for semantically checking parsed instances
    and solutions, for checking the validity of a solution for a given instance
    as well as for verifying that a solution is of a demanded quality, which
    usually refers to the solution size.
    """
    @abstractmethod
    def verify_solution_against_instance(self, instance, solution, instance_size: int, solution_type: bool):
        """ Check the validity of a solution against an instance.

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
    def verify_semantics_of_solution(self, instance, solution, instance_size: int, solution_type: bool):
        """ Check whether a given solution is semantically correct.

        Returns True if the solution is semantically correct enough such that
        it can be checked against an instance.

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
            Returns True if the solution is semantically correct.
        """
        raise NotImplementedError

    @abstractmethod
    def verify_semantics_of_instance(self, instance, instance_size: int):
        """ Check the semantical correctness of an instance.

        If the given instance ist semantically ill-formed in a way that
        it cannot be passed to a solver, return False.

        Parameters:
        ----------
        instance: list
            The instance, given as a list of Tuples.
        instance_size: int
            The maximum instance size.

        Returns:
        ----------
        bool
            Returns True if the instance is processable by a solver.
        """
        raise NotImplementedError

    @abstractmethod
    def verify_solution_quality(self, instance, instance_size: int, generator_solution, solver_solution):
        """ Check if the solvers solution achieves the wanted quality over the 
        generators solution.

        The default implementation assumes a maximimazation problem,
        for which the wanted quality is that the solution size of the solver is
        at least as big as that of the certificate.

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