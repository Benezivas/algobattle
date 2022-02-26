"""Observer class for an Observable pattern."""
from abc import ABCMeta, abstractmethod


class Observer(metaclass=ABCMeta):
    """The Observer interface declares the update method, used by subjects."""

    @abstractmethod
    def update(self, subject) -> None:  # TODO: Subject typehint w/o circular import
        """Receive update from subject."""
        pass
