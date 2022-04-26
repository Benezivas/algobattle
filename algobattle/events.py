"""basic event handling module."""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, ClassVar


class Observer(ABC):
    """Class that can handle updates from a `Subject`."""

    @abstractmethod
    def update(self, event: str, data: Any) -> None:
        """Updates the observer with the provided data."""
        raise NotImplementedError


class Subject(ABC):
    """Class that can send updates to an `Observer`."""

    default_event: ClassVar[str]
    """Event used when none is specififed for `.notify()`."""

    observers: list[Observer]
    """List of observers currently attached to this."""

    def __init__(self) -> None:
        super().__init__()
        self.observers = []

    def notify(self, data: Any, event: str | None = None) -> None:
        """Notifies all attached observers."""
        if event is None:
            event = self.default_event
        for observer in self.observers:
            observer.update(event, data)

    def attach(self, observer: Observer) -> None:
        """Attaches the observer, making it receive any future updates."""
        if observer not in self.observers:
            self.observers.append(observer)

    def detach(self, observer: Observer) -> None:
        """Detaches the observer, making it not receive any future updates."""
        try:
            self.observers.remove(observer)
        except ValueError:
            pass


class _Dispatcher(Observer, Subject):
    """Singleton class that handles the shared subject/observer objects."""

    default_event = ""

    def update(self, event: str, data: Any) -> None:
        self.notify(data, event)


_dispatcher = _Dispatcher()


class SharedObserver(Observer, ABC):
    """An `Observer` that will receive updates from any `SharedSubject`."""

    def __init__(self) -> None:
        super().__init__()
        _dispatcher.attach(self)


class SharedSubject(Subject, ABC):
    """A `Subject` that will update all `SharedObserver`s."""

    def __init__(self) -> None:
        super().__init__()
        self.attach(_dispatcher)
