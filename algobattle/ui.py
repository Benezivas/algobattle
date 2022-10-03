"""UI class, responsible for printing nicely formatted output to STDOUT."""
from __future__ import annotations
import curses
import logging
from sys import stdout
from typing import Callable, ParamSpec, TypeVar
from importlib.metadata import version as pkg_version
from algobattle.battle_wrapper import BattleWrapper

from algobattle.observer import Observer, Subject
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
        self.battle_info: BattleWrapper.Result | None = None
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
        if isinstance(subject, MatchResult):
            self.match_result = subject
        elif isinstance(subject, BattleWrapper.Result):
            self.battle_info = subject
        else:
            return

        out = [
            r"              _    _             _           _   _   _       ",
            r"             / \  | | __ _  ___ | |__   __ _| |_| |_| | ___  ",
            r"            / _ \ | |/ _` |/ _ \| |_ \ / _` | __| __| |/ _ \ ",
            r"           / ___ \| | (_| | (_) | |_) | (_| | |_| |_| |  __/ ",
            r"          /_/   \_\_|\__, |\___/|_.__/ \__,_|\__|\__|_|\___| ",
            r"                      |___/                                  ",
            f"Algobattle version {pkg_version(__package__)}",
            format(self.match_result) if self.match_result is not None else "",
            "",
            format(self.battle_info) if self.battle_info is not None else "",
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
