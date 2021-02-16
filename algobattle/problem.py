from abc import ABCMeta, abstractmethod

class Problem(metaclass=ABCMeta):
    """ Problem Class, bundling together the verifier and parser of a problem.
    Enforces the necessary attribute n_start which is the smallest iteration
    size for a problem.
    """
    @property
    @abstractmethod
    def n_start(self):
        raise NotImplementedError

    @property
    @abstractmethod
    def parser(self):
        raise NotImplementedError

    @property
    @abstractmethod
    def verifier(self):
        raise NotImplementedError