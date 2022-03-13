"""UI class, responsible for printing nicely formatted output to STDOUT."""
from __future__ import annotations
import curses
import logging
from logging.handlers import MemoryHandler
from sys import stdout
from typing import Callable, TypeVar
from collections import deque

from algobattle import __version__ as version


logger = logging.getLogger('algobattle.ui')

F = TypeVar("F", bound=Callable)
def check_for_terminal(function: F) -> F:
    """Ensure that we are attached to a terminal."""
    def wrapper(self, *args, **kwargs):
        if not stdout.isatty():
            logger.error('Not attached to a terminal.')
            return None
        else:
            return function(self, *args, **kwargs)
    return wrapper # type: ignore

class Ui:
    """The UI Class declares methods to output information to STDOUT."""

    @check_for_terminal
    def __init__(self, logger: logging.Logger, logging_level: int = logging.NOTSET, num_records: int = 10) -> None:
        if stdout.isatty():
            self.stdscr = curses.initscr()  # type: ignore
            curses.cbreak()                 # type: ignore
            curses.noecho()                 # type: ignore
            self.stdscr.keypad(True)
            self.cached_results = ""
            self.cached_logs = ""
            handler = BufferHandler(self, logging_level, num_records)
            logger.addHandler(handler)

    @check_for_terminal
    def restore(self) -> None:
        """Restore the console. This will be later moved into a proper deconstruction method."""
        if stdout.isatty():
            curses.nocbreak()               # type: ignore
            self.stdscr.keypad(False)
            curses.echo()                   # type: ignore
            curses.endwin()                 # type: ignore

    @check_for_terminal
    def update(self, results: str | None = None, logs: str | None = None) -> None:
        """Receive updates by observing the match object and prints them out formatted.

        Parameters
        ----------
        match : dict
            The observed match object.
        """
        if results is None:
            results = self.cached_results
        else:
            self.cached_results = results
        if logs is None:
            logs = self.cached_logs
        else:
            self.cached_logs = logs

        out = (
            r"              _    _             _           _   _   _       ""\n"
            r"             / \  | | __ _  ___ | |__   __ _| |_| |_| | ___  ""\n"
            r"            / _ \ | |/ _` |/ _ \| |_ \ / _` | __| __| |/ _ \ ""\n"
            r"           / ___ \| | (_| | (_) | |_) | (_| | |_| |_| |  __/ ""\n"
            r"          /_/   \_\_|\__, |\___/|_.__/ \__,_|\__|\__|_|\___| ""\n"
            r"                      |___/                                  ""\n"
             "                                                             ""\n"
            f"Algobattle version {version}"                                 "\n"
            f"{results}"                                                    "\n"
             "                                                             ""\n"
             "-------------------------------------------------------------""\n"
            f"{logs}"                                                       "\n"
             "-------------------------------------------------------------"
        )
        self.stdscr.clear()
        self.stdscr.addstr(0, 0, out)  # TODO: Refactor s.t. the output stream can be chosen by the user.
        self.stdscr.refresh()
        self.stdscr.nodelay(1)
        c = self.stdscr.getch()
        if c == 3:
            raise KeyboardInterrupt
        else:
            curses.flushinp() # type: ignore

class BufferHandler(MemoryHandler):
    
    def __init__(self, ui: Ui, level: int, num_records: int):
        self._buffer = deque(maxlen=num_records)
        self.ui = ui
        super().__init__(num_records)
    
    def emit(self, record: logging.LogRecord):
        try:
            msg = self.format(record)
            self._buffer.append(msg)
            self.ui.update(logs="\n".join(self._buffer))
            
        except Exception:
            self.handleError(record)
