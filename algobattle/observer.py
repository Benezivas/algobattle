"""Observer class for an Observable pattern."""
from abc import ABC, abstractmethod


class Observer(ABC):
    """The Observer interface declares the update method, used by subjects."""

    @abstractmethod
    def update(self, subject) -> None:  # TODO: Subject typehint w/o circular import
        """Receive update from subject."""
        pass
