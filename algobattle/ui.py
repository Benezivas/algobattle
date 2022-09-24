"""UI class, responsible for printing nicely formatted output to STDOUT."""
from __future__ import annotations
import curses
import logging
from sys import stdout
from typing import Any, Callable, Mapping, ParamSpec, TypeVar
from importlib.metadata import version as pkg_version

from algobattle.observer import Observer
from algobattle.match import MatchResult

logger = logging.getLogger("algobattle.ui")


P = ParamSpec("P")
R = TypeVar("R")


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
        self.match_result: MatchResult | None = None
        self.battle_info: dict[str, Any] = {}
        self.stdscr = curses.initscr()
        curses.cbreak()
        curses.noecho()
        self.stdscr.keypad(True)

    @check_for_terminal
    def cleanup(self) -> None:
        """Restore the console."""
        curses.nocbreak()
        self.stdscr.keypad(False)
        curses.echo()
        curses.endwin()

    @check_for_terminal
    def update(self, event: str, data: Any):
        """Receive updates to the match data and displays them."""
        match event:
            case "match_data":
                if not isinstance(data, MatchResult):
                    raise TypeError
                self.match_result = data
            case "battle_info":
                if not isinstance(data, Mapping):
                    raise TypeError
                self.battle_info |= data

        self.stdscr.refresh()
        self.stdscr.clear()
        out = [
            r"              _    _             _           _   _   _       ",
            r"             / \  | | __ _  ___ | |__   __ _| |_| |_| | ___  ",
            r"            / _ \ | |/ _` |/ _ \| |_ \ / _` | __| __| |/ _ \ ",
            r"           / ___ \| | (_| | (_) | |_) | (_| | |_| |_| |  __/ ",
            r"          /_/   \_\_|\__, |\___/|_.__/ \__,_|\__|\__|_|\___| ",
            r"                      |___/                                  ",
            f"Algobattle version {pkg_version(__package__)}",
            format(self.match_result) if self.match_result is not None else "",
            ""
        ]
        out.extend(f"{k}: {v}" for k, v in self.battle_info.items())

        print(out)
