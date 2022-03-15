"""Collection of utility functions."""
from __future__ import annotations
import logging
import importlib.util
from pathlib import Path
from sys import modules
from typing import Any, Mapping, TypeVar
from inspect import getmembers, isclass
from argparse import Action, SUPPRESS

from algobattle.problem import Problem

logger = logging.getLogger("algobattle.util")


def get_matching_file(path: Path, *files: str) -> Path:
    """Searches the file structure for the first file found in the targeted directory.

    Parameters
    ----------
    path : Path
        Path to a directory or file, if it's a file the path will be returned unaltered.

    Returns
    -------
    Path
        Path to the first found file or the parent directory if it contains no matching files.

    Raises
    ------
    RuntimeError
        If the path doesn't exist in the file system.
    ValueError
        If the targeted directory contains no matching files.
    """
    if not path.exists():
        raise RuntimeError
    elif path.is_dir():
        for ending in files:
            if (path / ending).is_file():
                return path / ending
        raise ValueError
    else:
        return path


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
    try:
        path = get_matching_file(path.resolve(), "__init__.py", "problem.py")
    except RuntimeError:
        logger.warning(f"Problem path '{path}' does not exist in the file system!")
        raise ValueError
    except ValueError:
        logger.warning(f"Problem path '{path}' points to a directory that doesn't contain a Problem.")
        raise ValueError

    try:
        spec = importlib.util.spec_from_file_location("problem", path)
        assert spec is not None
        assert spec.loader is not None
        problem_module = importlib.util.module_from_spec(spec)
        modules[spec.name] = problem_module
        spec.loader.exec_module(problem_module)

    except Exception as e:
        logger.critical(f'Importing the given problem failed with the following exception: "{e}"')
        raise RuntimeError

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


def format_table(table: list[list[Any]], column_spacing: Mapping[int, int] = {}) -> str:
    """Formats a table of data nicely.

    Parameters
    ----------
    table : list[list[Any]]
        The table to format, inner lists are rows and all assumed to have equal length.
    column_spacing : Mapping[int, int]
        Mapping of row numbers to a minimum character width, by default {}

    Returns
    -------
    str
        The formatted table.
    """
    if len(table) == 0:
        return "\n"

    table = [[str(element) for element in row] for row in table]
    col_sizes = [len(max((row[i] for row in table), key=len)) for i in range(len(table[0]))]
    for i, k in column_spacing.items():
        if col_sizes[i] < k:
            col_sizes[i] = k

    horizontal_sep_fmt = "{start}" + "{middle}".join("{sep}" * (width + 2) for width in col_sizes) + "{end}\n"
    top = horizontal_sep_fmt.format(start="╔", middle="╦", end="╗", sep="═")
    middle = horizontal_sep_fmt.format(start="╟", middle="╫", end="╢", sep="─")
    bottom = horizontal_sep_fmt.format(start="╚", middle="╩", end="╝", sep="═")[:-1]

    content_fmt = "║ " + " ║ ".join(f"{{: ^{width}}}" for width in col_sizes) + " ║\n"

    res = top + middle.join(content_fmt.format(*row) for row in table) + bottom

    return res


# this should probably be done with a library
# (well really this should probably not be done at all but its cute)
def parse_doc_for_param(doc: str, name: str) -> str:
    """Parses a docstring to find the documentation of a single parameter.

    Parameters
    ----------
    doc : str
        The docstring that will be parsed.
    name
        The name of the parameter.

    Returns
    -------
    str
        The documentation of that parameter.

    Raises
    ------
    ValueError
        If the parameter doesn't exist.
    """
    lines = doc.split("\n")
    try:
        start = next(i for i, line in enumerate(lines) if line.find(name) == 0)
    except StopIteration:
        raise ValueError

    param_doc = []
    for line in lines[start + 1 :]:
        if not line.startswith(" "):
            break
        param_doc.append(line.strip())

    return " ".join(param_doc)


class NestedHelp(Action):
    """Argparse action to generate nested help messages."""

    def __init__(self, option_strings, dest=SUPPRESS, default=SUPPRESS, help=None):
        super().__init__(option_strings=option_strings, dest=dest, default=default, nargs="?", help=help)

    def __call__(self, parser, namespace, values, option_string=None):
        """Prints the help message to the console and then exits the parser immedietly."""
        formatter = parser._get_formatter()

        # usage
        formatter.add_usage(parser.usage, parser._actions, parser._mutually_exclusive_groups)

        # description
        formatter.add_text(parser.description)

        # positionals, optionals and user-defined groups
        for action_group in parser._action_groups:
            formatter.start_section(action_group.title)
            formatter.add_text(action_group.description)
            formatter.add_arguments(action_group._group_actions)
            formatter.end_section()

        if isinstance(values, str):
            battle_group = next(g for g in parser._action_groups if g.title == "battle arguments")
            arg_groups = {g.title: g for g in battle_group._action_groups}
            groups = []
            if values == "all":
                groups = battle_group._action_groups
            elif values in arg_groups:
                groups = [arg_groups[values]]

            for action_group in groups:
                formatter.start_section(action_group.title)
                formatter.add_text(action_group.description)
                formatter.add_arguments(action_group._group_actions)
                formatter.end_section()

        # epilog
        formatter.add_text(parser.epilog)

        # determine help from format above
        print(formatter.format_help())
        parser.exit()


T = TypeVar("T")


def inherit_docs(obj: T) -> T:
    """Decorator to mark a method as inheriting its docstring.

    Python 3.5+ already does this, but pydocstyle needs a static hint.
    """
    return obj
