"""Observer class for an Observable pattern."""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any


class Observer(ABC):
    """The Observer interface declares the methods to receive updates from running matches."""

    @abstractmethod
    def update(self, subject: Subject, event: str):
        """Processes an update in the info of the subject."""
        raise NotImplementedError


class Subject(ABC):
    """The Subject interface declares an easy way to update observers."""

    def __init_subclass__(cls, notify_var_changes: bool = False) -> None:
        if notify_var_changes:
            cls.__setattr__ = cls.__notifying_setattr__
        return super().__init_subclass__()

    def __init__(self, observer: Observer | None = None) -> None:
        super().__init__()
        self.observers: list[Observer] = []
        if observer is not None:
            self.attach(observer)

    def attach(self, observer: Observer):
        """Subscribes an observer to the updates of this subject."""
        if observer not in self.observers:
            self.observers.append(observer)

    def detach(self, observer: Observer):
        """Unsubscribes an observer from the updates of this object."""
        if observer in self.observers:
            self.observers.remove(observer)

    def notify(self, event: str = ""):
        """Updates all subscribed observers."""
        for observer in self.observers:
            observer.update(self, event)

    def __notifying_setattr__(self, name: str, value: Any) -> None:
        super().__setattr__(name, value)
        self.notify(name)

    def display(self) -> str:
        """Nicely formats the object."""
        return str(self)
