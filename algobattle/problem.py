"""Abstract base class for problem classes used in concrete problem implementations."""
from abc import ABCMeta, abstractmethod


class Problem(metaclass=ABCMeta):
    """Problem Class, bundling together the verifier and parser of a problem.

    Enforces the necessary attribute n_start which is the smallest iteration
    size for a problem as well as a flag indicating whether a problem is
    usable in an approximation setting.
    """

    @property
    @abstractmethod
    def name(self):
        """Name of a Problem."""
        raise NotImplementedError

    @property
    @abstractmethod
    def n_start(self):
        """Lowest value on which a battle should be executed."""
        raise NotImplementedError

    @property
    @abstractmethod
    def parser(self):
        """Parser object for the corresponding problem."""
        raise NotImplementedError

    @property
    @abstractmethod
    def verifier(self):
        """Verifier object for the corresponding problem."""
        raise NotImplementedError

    @property
    @abstractmethod
    def approximable(self):
        """Boolean flag indicating whether a problem can have an approximate solution."""
        raise NotImplementedError

    def __str__(self) -> str:
        return self.name
