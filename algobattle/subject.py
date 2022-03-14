"""Subject class for an Observable pattern."""
from abc import ABCMeta, abstractmethod
from algobattle.observer import Observer


class Subject(metaclass=ABCMeta):
    """The Subject interface declares a set of methods for managing subscribers."""

    @abstractmethod
    def attach(self, observer: Observer) -> None:
        """Attach an observer to the subject."""
        pass

    @abstractmethod
    def detach(self, observer: Observer) -> None:
        """Detach an observer from the subject."""
        pass

    @abstractmethod
    def notify(self) -> None:
        """Notify all observers about an event."""
        pass
