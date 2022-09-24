"""Observer class for an Observable pattern."""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any
from algobattle.util import inherit_docs


class Observer(ABC):
    """The Observer interface declares the methods to receive updates from running matches."""

    @abstractmethod
    def update(self, event: str, data: Any):
        """Receive an update regarding `event` with `data`."""
        raise NotImplementedError


class Subject(ABC):
    """The Subject interface declares an easy way to update observers."""

    def __init__(self) -> None:
        super().__init__()
        self.observers: list[Observer] = []

    def attach(self, observer: Observer):
        """Subscribes an observer to the updates of this subject."""
        self.observers.append(observer)

    def detach(self, observer: Observer):
        """Unsubscribes an observer from the updates of this object."""
        if observer in self.observers:
            self.observers.remove(observer)

    def notify(self, event: str, data: Any):
        """Updates all subscribed observers."""
        for observer in self.observers:
            observer.update(event, data)


class Passthrough(Subject, Observer, ABC):
    """A class that is an observer and a subject and just passes notifications through."""

    @inherit_docs
    def update(self, event: str, data: Any):
        self.notify(event, data)
