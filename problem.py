from abc import ABCMeta, abstractmethod

class Problem(metaclass=ABCMeta):
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