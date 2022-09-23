"""Observer class for an Observable pattern."""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any
from algobattle.util import inherit_docs


class Observer(ABC):
    """The Observer interface declares the methods to receive updates from running matches."""

    def cleanup(self):
        """Frees any resources allocated during the observer's construction."""
        pass

    def __enter__(self):
        return self

    def __exit__(self, _type, _value_, _traceback):
        self.cleanup()

    @abstractmethod
    def update(self, event: str, data: Any):
        """Notify an update of `event` with `data`."""
        raise NotImplementedError


class Subject(ABC):
    """The Subject interface declares an easy way to update observers."""

    def __init__(self) -> None:
        super().__init__()
        self.observers: set[Observer] = set()

    def attach(self, observer: Observer):
        """Subscribes an observer to the updates of this subject."""
        self.observers.add(observer)

    def detach(self, observer: Observer):
        """Unsubscribes an observer from the updates of this object."""
        self.observers.discard(observer)

    def notify(self, event: str, data: Any):
        """Updates all subscribed observers."""
        for observer in self.observers:
            observer.update(event, data)

    def __enter__(self):
        return self

    def __exit__(self):
        for observer in self.observers.copy():
            self.detach(observer)
            observer.cleanup()


class Passthrough(Subject, Observer, ABC):
    """A class that is an observer and a subject and just passes notifications through."""

    @inherit_docs
    def update(self, event: str, data: Any):
        self.notify(event, data)

    @inherit_docs
    def cleanup(self):
        for observer in self.observers:
            observer.cleanup()
