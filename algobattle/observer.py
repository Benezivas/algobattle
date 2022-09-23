"""Observer class for an Observable pattern."""
from __future__ import annotations
from abc import ABC, abstractmethod
from contextlib import AbstractContextManager, ExitStack
from typing import Any


class Observer(ABC, AbstractContextManager):
    """The Observer interface declares the methods to receive updates from running matches."""

    def cleanup(self):
        """Frees any resources allocated during the observer's construction."""
        pass

    def __exit__(self, _type, _value_, _traceback):
        self.cleanup()

    @abstractmethod
    def update(self, event: str, data: Any):
        """Notify an update of `event` with `data`."""
        raise NotImplementedError

class ObserverGroup(Observer):
    """A group of observers that will be updated together."""

    def __init__(self) -> None:
        super().__init__()
        self.observers = set()
        self._context = ExitStack()

    def add(self, observer: Observer):
        """Adds an observer to the group."""
        self.observers.add(observer)

    def remove(self, observer: Observer):
        """Removes an observer from the group."""
        self.observers.remove(observer)

    def update(self, event: str, data: Any):
        """Updates the `MatchResult` of all `Observer`s."""
        for observer in self.observers:
            observer.update(event, data)

    def __enter__(self):
        for observer in self.observers:
            self._context.enter_context(observer)
        return self

    def __exit__(self, _type, _value_, _traceback):
        self._context.close()
