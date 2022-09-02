"""Abstract base class for parsers used in concrete problem implementations."""
from abc import ABC, abstractmethod
from typing import Any, Tuple


class Parser(ABC):
    """Parser class, responsible for decoding and encoding of output sent from and to generators and solvers.

    Implements methods for syntactical checks of instances and solutions.
    """

    @abstractmethod
    def split_into_instance_and_solution(self, raw_input: Any) -> Tuple[Any, Any]:
        """Split an input into instance and solution, discard anything else.

        The validity is only checked by grouping together lines with the same
        first element as an identifier. No checks are made that test whether
        they are otherwise well formatted or semantically correct.

        Parameters
        ----------
        raw_input : Any
            The raw input.

        Returns
        -------
        Any, Any
            Returns a tuple containing the instance and the solution.
            The lines may still be syntactially and semantically incorrect.
        """
        raise NotImplementedError

    @abstractmethod
    def parse_instance(self, raw_instance: Any, instance_size: int) -> Any:
        """Remove all syntactially wrong elements from the raw instance.

        Parameters
        ----------
        raw_instance : Any
            The raw instance.
        instance_size : int
            The size of the instance.

        Returns
        -------
        Any
            Returns what is syntactically valid of the instance.
        """
        raise NotImplementedError

    @abstractmethod
    def parse_solution(self, raw_solution: Any, instance_size: int) -> Any:
        """Remove all syntactially wrong lines from the raw solution.

        Parameters
        ----------
        raw_solution : Any
            The raw solution.
        instance_size : int
            The size of the instance.

        Returns
        -------
        Any
            Returns what is syntactically valid of the solution.
        """
        raise NotImplementedError

    def postprocess_instance(self, instance: Any, instance_size: int) -> Any:
        """Postprocess an instance, e.g. when the verifier has passed its checks on the instance.

        Some problems may require postprocessing, which should be done by
        overwriting this method. An example could be a problem parameterized by
        some measure, e.g. the size of the vertex cover of a graph, which
        should not be communicated to the solver of another group.

        This way, one can quickly verify using the verifier that some measure
        holds for the given instance without revealing this sub-certificate
        of the instance to another team.

        Parameters
        ----------
        instance : Any
            The parsed instance.
        instance_size : int
            The size of the instance.

        Returns
        -------
        Any
            A postprocessed instance.
        """
        return instance

    @abstractmethod
    def encode(self, input: Any) -> str:
        """Encode an input and return it.

        This method is responsible for turning the output of parse_instance back
        into a string that can be passed to a solver.

        Parameters
        ----------
        raw_input : Any
            The input that is to be encoded.

        Returns
        -------
        bytes
            Returns the input as a byte object.
        """
        return "\n".join(str(" ".join(str(element) for element in line)) for line in input)

    @abstractmethod
    def decode(self, raw_input: str) -> Any:
        """Decode an input and return it.

        This method is responsible for taking the output of a generator or
        solver and to transform it in a way that is readable by the
        split_into_instance_and_solution or parse_solution methods.

        Parameters
        ----------
        raw_input : bytes
            The raw input as byte code.

        Returns
        -------
        Any
            Returns the decoded input.
        """
        return [tuple(line.split()) for line in raw_input.splitlines() if line.split()]
