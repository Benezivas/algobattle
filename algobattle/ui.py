"""UI class, responsible for printing nicely formatted output to STDOUT."""
import curses
import logging
import sys
from typing import Callable, TypeVar
from algobattle.sighandler import signal_handler

from algobattle import __version__ as version


logger = logging.getLogger('algobattle.ui')

F = TypeVar("F", bound=Callable)
def check_for_terminal(function: F) -> F:
    """Ensure that we are attached to a terminal."""
    def wrapper(self, *args, **kwargs):
        if not sys.stdout.isatty():
            logger.error('Not attached to a terminal.')
            return None
        else:
            return function(self, *args, **kwargs)
    return wrapper # type: ignore

class Ui:
    """The UI Class declares methods to output information to STDOUT."""

    @check_for_terminal
    def __init__(self) -> None:
        if sys.stdout.isatty():
            self.stdscr = curses.initscr()  # type: ignore
            curses.cbreak()                 # type: ignore
            curses.noecho()                 # type: ignore
            self.stdscr.keypad(True)

    @check_for_terminal
    def restore(self) -> None:
        """Restore the console. This will be later moved into a proper deconstruction method."""
        if sys.stdout.isatty():
            curses.nocbreak()               # type: ignore
            self.stdscr.keypad(False)
            curses.echo()                   # type: ignore
            curses.endwin()                 # type: ignore

    @check_for_terminal
    def update(self, results: str) -> None:
        """Receive updates by observing the match object and prints them out formatted.

        Parameters
        ----------
        match : dict
            The observed match object.
        """
        out = (
            r"              _    _             _           _   _   _       ""\n"
            r"             / \  | | __ _  ___ | |__   __ _| |_| |_| | ___  ""\n"
            r"            / _ \ | |/ _` |/ _ \| |_ \ / _` | __| __| |/ _ \ ""\n"
            r"           / ___ \| | (_| | (_) | |_) | (_| | |_| |_| |  __/ ""\n"
            r"          /_/   \_\_|\__, |\___/|_.__/ \__,_|\__|\__|_|\___| ""\n"
            r"                      |___/                                  ""\n"
            r"                                                             ""\n"
            f"Algobattle version {version}                                 ""\n"
            f"{results}                                                    "
        )
        self.stdscr.addstr(0, 0, out)  # TODO: Refactor s.t. the output stream can be chosen by the user.
        self.stdscr.refresh()
        self.stdscr.nodelay(1)
        c = self.stdscr.getch()
        if c == 3:
            signal_handler(None, None)
        else:
            curses.flushinp() # type: ignore

