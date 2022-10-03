"""Observer class for an Observable pattern."""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Callable, Generic, TypeVar


class Observer(ABC):
    """The Observer interface declares the methods to receive updates from running matches."""

    @abstractmethod
    def update(self, subject: Subject, event: str):
        """Processes an update in the info of the subject."""
        raise NotImplementedError


class Subject(ABC):
    """The Subject interface declares an easy way to update observers."""

    def __init__(self, observer: Observer | None = None) -> None:
        super().__init__()
        self.observers: list[Observer] = []
        if observer is not None:
            self.attach(observer)

    def attach(self, observer: Observer):
        """Subscribes an observer to the updates of this subject."""
        self.observers.append(observer)
        observer.update(self, "__attach__")

    def detach(self, observer: Observer):
        """Unsubscribes an observer from the updates of this object."""
        if observer in self.observers:
            self.observers.remove(observer)

    def notify(self, event: str = ""):
        """Updates all subscribed observers."""
        for observer in self.observers:
            observer.update(self, event)


T = TypeVar("T")
class Notifying(Generic[T]):
    def __init__(self, callback: Callable[[str], None] | None = None) -> None:
        super().__init__()
        self.callback = callback

    def __set_name__(self, obj: Subject, name: str) -> None:
        self.name = name
        self.private_name = "_" + name
        if self.callback is None:
            self.callback = obj.notify

    def __get__(self, obj: Subject, objtype=None) -> T:
        return getattr(obj, self.private_name)
    
    def __set__(self, obj: Subject, value: T) -> None:
        setattr(obj, self.private_name, value)
        if self.callback is not None:
            self.callback(self.name)
