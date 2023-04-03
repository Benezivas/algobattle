"""UI class, responsible for printing nicely formatted output to STDOUT."""
from __future__ import annotations
from abc import ABC, abstractmethod
import curses
import logging
from sys import stdout
from typing import Any, Callable, ParamSpec, TypeVar
from importlib.metadata import version as pkg_version

logger = logging.getLogger("algobattle.ui")


P = ParamSpec("P")
R = TypeVar("R")


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
            cls.__setattr__ = cls.__notifying_setattr__     # type: ignore
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


def check_for_terminal(function: Callable[P, R]) -> Callable[P, R | None]:
    """Ensure that we are attached to a terminal."""

    def wrapper(*args: P.args, **kwargs: P.kwargs):
        if not stdout.isatty():
            logger.error("Not attached to a terminal.")
            return None
        else:
            return function(*args, **kwargs)

    return wrapper


class Ui(Observer):
    """The UI Class declares methods to output information to STDOUT."""

    @check_for_terminal
    def __init__(self) -> None:
        super().__init__()
        self.match_result: Any = None
        self.battle_info: Any = None
        self.stdscr = curses.initscr()
        curses.cbreak()
        curses.noecho()
        self.stdscr.keypad(True)

    def __enter__(self) -> Ui:
        return self

    def __exit__(self, _type, _value, _traceback):
        self.close()

    @check_for_terminal
    def close(self) -> None:
        """Restore the console."""
        curses.nocbreak()
        self.stdscr.keypad(False)
        curses.echo()
        curses.endwin()

    @check_for_terminal
    def update(self, subject: Subject, event: str) -> None:
        """Receive updates to the match data and displays them."""
        if event == "match":
            self.match_result = subject
        elif event == "battle":
            self.battle_info = subject
        else:
            return

        if self.match_result is not None:
            try:
                match_display = self.match_result.display()
            except Exception:
                match_display = ""
        else:
            match_display = ""
        if self.battle_info is not None:
            try:
                battle_display = self.battle_info.display()
            except Exception:
                battle_display = ""
        else:
            battle_display = ""

        out = [
            r"              _    _             _           _   _   _       ",
            r"             / \  | | __ _  ___ | |__   __ _| |_| |_| | ___  ",
            r"            / _ \ | |/ _` |/ _ \| |_ \ / _` | __| __| |/ _ \ ",
            r"           / ___ \| | (_| | (_) | |_) | (_| | |_| |_| |  __/ ",
            r"          /_/   \_\_|\__, |\___/|_.__/ \__,_|\__|\__|_|\___| ",
            r"                      |___/                                  ",
            f"Algobattle version {pkg_version(__package__)}",
            match_display,
            "",
            battle_display,
        ]

        self.stdscr.clear()
        self.stdscr.addstr(0, 0, "\n".join(out))
        self.stdscr.refresh()
        self.stdscr.nodelay(True)

        # on windows curses swallows the ctrl+C event, we need to manually check for the control sequence
        # ideally we'd be doing this from inside the docker image run wait loop too
        c = self.stdscr.getch()
        if c == 3:
            raise KeyboardInterrupt
        else:
            curses.flushinp()
