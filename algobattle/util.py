"""Collection of utility functions."""
from __future__ import annotations
import logging
import importlib.util
from pathlib import Path
import sys
from typing import Any
from inspect import getmembers, isclass

from algobattle.problem import Problem


logger = logging.getLogger('algobattle.util')


def import_problem_from_path(path: Path) -> Problem:
    """Try to import and initialize a Problem object from a given path.

    Parameters
    ----------
    path : Path
        Path in the file system to a problem folder.

    Returns
    -------
    Problem
        Returns an object of the problem.
    
    Raises
    ------
    ValueError
        If the given path does not point to a valid Problem.
    RuntimeError
        If some unexpected error occurs while importing the Problem.
    """
    path = path.resolve()
    if not path.exists():
        logger.warning(f"Problem path '{path}' does not exist in the file system!")
        raise ValueError
    
    if path.is_dir:
        if (path / "__init__.py").is_file():
            path /= "__init__.py"
        elif (path / "problem.py").is_file():
            path /= "problem.py"
        else:
            logger.warning(f"Problem path '{path}' points to a directory that doesn't contain a Problem.")
            raise ValueError
    
    try:
        spec = importlib.util.spec_from_file_location("problem", path)
        assert spec is not None
        assert spec.loader is not None
        problem_module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = problem_module
        spec.loader.exec_module(problem_module)

        potential_problems = []
        for _, obj in getmembers(problem_module):
            # issubclass won't work here til 3.11
            if isclass(obj) and Problem in obj.__bases__:
                potential_problems.append(obj)
        
        if len(potential_problems) == 0:
            logger.warning(f"Problem path '{path}' points to a module that doesn't contain a Problem.")
            raise ValueError
        if len(potential_problems) > 1:
            formatted_list = ", ".join(f"'{p.name}'" for p in potential_problems)
            logger.warning(f"Problem path '{path}' points to a module containing more than one Problem: {formatted_list}")
            raise ValueError
        
        return potential_problems[0]()

    except Exception as e:
        logger.critical(f'Importing the given problem failed with the following exception: "{e}"')
        raise RuntimeError

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
    bottom = horizontal_sep_fmt.format(start="╚", middle="╩", end="╝", sep="═")[:-1]

    content_fmt = "║ " + " ║ ".join(f"{{: ^{width}}}" for width in col_sizes) + " ║\n"

    res = top + middle.join(content_fmt.format(*row) for row in table) + bottom

    return res
