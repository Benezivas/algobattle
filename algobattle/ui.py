"""UI class, responsible for printing nicely formatted output to STDOUT."""
from __future__ import annotations
import curses
import logging
from sys import stdout
from typing import Any, Callable, ParamSpec, TypeVar
from importlib.metadata import version as pkg_version

from algobattle.observer import Observer
from algobattle.match import MatchResult

logger = logging.getLogger('algobattle.ui')


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
        """Receive updates by observing the match object and prints them out formatted.

        Parameters
        ----------
        match : dict
            The observed match object.
        """
        if event != "match_data" or not isinstance(data, MatchResult):
            return

        self.stdscr.refresh()
        self.stdscr.clear()
        out = r'              _    _             _           _   _   _       ' + '\n\r' \
              + r'             / \  | | __ _  ___ | |__   __ _| |_| |_| | ___  ' + '\n\r' \
              + r'            / _ \ | |/ _` |/ _ \| |_ \ / _` | __| __| |/ _ \ ' + '\n\r' \
              + r'           / ___ \| | (_| | (_) | |_) | (_| | |_| |_| |  __/ ' + '\n\r' \
              + r'          /_/   \_\_|\__, |\___/|_.__/ \__,_|\__|\__|_|\___| ' + '\n\r' \
              + r'                      |___/                                  ' + '\n\r'

        out += '\nAlgobattle version {}\n\r'.format(pkg_version(__package__))
        out += format(data)

        print(out)
