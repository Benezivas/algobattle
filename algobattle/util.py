"""Collection of utility functions."""
from __future__ import annotations
import logging
import importlib.util
from pathlib import Path
import sys
from typing import Any

from algobattle.problem import Problem


logger = logging.getLogger('algobattle.util')


def import_problem_from_path(problem_path: Path) -> Problem | None:
    """Try to import and initialize a Problem object from a given path.

    Parameters
    ----------
    problem_path : Path
        Path in the file system to a problem folder.

    Returns
    -------
    Problem
        Returns an object of the problem if successful, None otherwise.
    """
    try:
        spec = importlib.util.spec_from_file_location("problem", problem_path / "__init__.py")
        assert spec is not None
        assert spec.loader is not None
        Problem = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = Problem
        spec.loader.exec_module(Problem)

        return Problem.Problem()
    except Exception as e:
        logger.critical(f'Importing the given problem failed with the following exception: "{e}"')
        return None

def format_table(table: list[list[Any]], column_spacing: dict[int, int] = {}) -> str:
    if len(table) == 0:
        return "\n"

    table = [[str(element) for element in row] for row in table]
    col_sizes = [len(max((row[i] for row in table), key=len)) for i in range(len(table[0]))]
    for (i, k) in column_spacing.items():
        col_sizes[i] = k

    horizontal_sep_fmt = "{start}" + "{middle}".join("{sep}" * (width + 2) for width in col_sizes) + "{end}\n"
    top = horizontal_sep_fmt.format(start="╔", middle="╦", end="╗", sep="═")
    middle = horizontal_sep_fmt.format(start="╟", middle="╫", end="╢", sep="─")
    bottom = horizontal_sep_fmt.format(start="╚", middle="╩", end="╝", sep="═")

    content_fmt = "║ " + " ║ ".join(f"{{: ^{width}}}" for width in col_sizes) + " ║\n"

    res = top + middle.join(content_fmt.format(*row) for row in table) + bottom

    return res

t = [["test", "yes", "no"], [1, 2, 3], ["blep", "aaaaaaaaaaaaa", ""],[10, 20, 30]]

print(format_table(t))