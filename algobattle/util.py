"""Collection of utility functions."""
from __future__ import annotations
import logging
import importlib.util
import sys
from typing import Callable

from algobattle.problem import Problem


logger = logging.getLogger('algobattle.util')


def import_problem_from_path(problem_path: str) -> Problem | None:
    """Try to import and initialize a Problem object from a given path.

    Parameters
    ----------
    problem_path : str
        Path in the file system to a problem folder.

    Returns
    -------
    Problem
        Returns an object of the problem if successful, None otherwise.
    """
    try:
        spec = importlib.util.spec_from_file_location("problem", problem_path + "/__init__.py")
        assert spec is not None
        assert spec.loader is not None
        Problem = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = Problem
        spec.loader.exec_module(Problem)

        return Problem.Problem()
    except Exception as e:
        logger.critical(f'Importing the given problem failed with the following exception: "{e}"')
        return None


def team_roles_set(function: Callable) -> Callable:
    """Ensure that internal methods are only callable after the team roles have been set."""
    def wrapper(self, *args, **kwargs):
        if not self.generating_team or not self.solving_team:
            logger.error('Generating or solving team have not been set!')
            return None
        else:
            return function(self, *args, **kwargs)
    return wrapper

def check_for_terminal(function: Callable) -> Callable:
    """Ensure that we are attached to a terminal."""
    def wrapper(self, *args, **kwargs):
        if not sys.stdout.isatty():
            logger.error('Not attached to a terminal.')
            return None
        else:
            return function(self, *args, **kwargs)
    return wrapper