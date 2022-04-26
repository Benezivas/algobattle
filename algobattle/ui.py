"""UI class, responsible for printing nicely formatted output to STDOUT."""
from __future__ import annotations
import curses
import logging
from logging.handlers import MemoryHandler
from sys import stdout
from typing import Any, Callable, TypeVar
from collections import deque

from algobattle import __version__ as version
from algobattle.events import SharedObserver, Subject
from algobattle.util import inherit_docs


logger = logging.getLogger("algobattle.ui")

F = TypeVar("F", bound=Callable)


def check_for_terminal(function: F) -> F:
    """Ensure that we are attached to a terminal."""

    def wrapper(self, *args, **kwargs):
        if not stdout.isatty():
            logger.error("Not attached to a terminal.")
            return None
        else:
            return function(self, *args, **kwargs)

    return wrapper  # type: ignore


class Ui(SharedObserver):
    """The UI Class declares methods to output information to STDOUT."""

    titles = {
        "match": "",
        "battle": "Current battle info:\n",
    }

    @check_for_terminal
    def __init__(self, logger: logging.Logger, logging_level: int = logging.NOTSET, num_records: int = 10) -> None:
        super().__init__()
        if stdout.isatty():
            self.stdscr = curses.initscr()  # type: ignore
            curses.cbreak()  # type: ignore
            curses.noecho()  # type: ignore
            self.stdscr.keypad(True)
            handler = BufferHandler(self, logging_level, num_records)
            logger.addHandler(handler)
            self.sections: dict[str, Any] = {
                "match": None,
                "battle": None,
                "logs": None,
            }

    @check_for_terminal
    def restore(self) -> None:
        """Restore the console. This will be later moved into a proper deconstruction method."""
        if stdout.isatty():
            curses.nocbreak()  # type: ignore
            self.stdscr.keypad(False)
            curses.echo()  # type: ignore
            curses.endwin()  # type: ignore

    @check_for_terminal
    def update(self, section: str, data: Any) -> None:
        """Updates the specified section of the UI."""
        if section not in self.sections:
            return

        self.sections[section] = data
        results = "\n\n".join(self.titles[s] + str(d) for s, d in self.sections.items() if d is not None and s != "logs")

        out = "\n".join([
            r"              _    _             _           _   _   _       ",
            r"             / \  | | __ _  ___ | |__   __ _| |_| |_| | ___  ",
            r"            / _ \ | |/ _` |/ _ \| |_ \ / _` | __| __| |/ _ \ ",
            r"           / ___ \| | (_| | (_) | |_) | (_| | |_| |_| |  __/ ",
            r"          /_/   \_\_|\__, |\___/|_.__/ \__,_|\__|\__|_|\___| ",
            r"                      |___/                                  ",
            "",
            f"Algobattle version {version}",
            f"{results}",
            "",
            "-------------------------------------------------------------",
            f"{self.sections['logs']}",
            "-------------------------------------------------------------",
        ])
        self.stdscr.clear()
        self.stdscr.addstr(0, 0, out)
        self.stdscr.refresh()
        self.stdscr.nodelay(1)
        c = self.stdscr.getch()
        if c == 3:
            raise KeyboardInterrupt
        else:
            curses.flushinp()  # type: ignore


class BufferHandler(MemoryHandler, Subject):
    """Logging handler that buffers the last few messages."""

    default_event = "logs"

    def __init__(self, ui: Ui, level: int, num_records: int):
        super().__init__(num_records)
        Subject.__init__(self)
        self._buffer = deque(maxlen=num_records)
        self.attach(ui)

    @inherit_docs
    def emit(self, record: logging.LogRecord):
        try:
            msg = self.format(record)
            self._buffer.append(msg)
            self.notify("\n".join(self._buffer))

        except Exception:
            self.handleError(record)
