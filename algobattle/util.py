"""Collection of utility functions."""
from __future__ import annotations
import os
import logging
import timeit
import subprocess
import importlib.util
import sys
from typing import Callable

import algobattle
import algobattle.problems.delaytest as DelaytestProblem
import algobattle.sighandler as sigh
from algobattle.problem import Problem
from algobattle.team import Team
import algobattle.match


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


def run_subprocess(run_command: list[str], input: bytes, timeout: float, suppress_output: bool=False):
    """Run a given command as a subprocess.

    Parameters
    ----------
    run_command : list
        The command that is to be executed.
    input : bytes
        Additional input for the subprocess, supplied to it via stdin.
    timeout : float
        The timeout for the subprocess in seconds.
    suppress_output : bool
        Indicate whether to suppress output to stderr.

    Returns
    -------
    any
        The output that the process returns.
    float
        Actual running time of the process.
    """
    start_time = timeit.default_timer()
    raw_output = None

    stderr = subprocess.PIPE
    if suppress_output:
        stderr = None

    creationflags = 0
    if os.name != 'posix':
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
    with subprocess.Popen(run_command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          stderr=stderr, creationflags=creationflags) as p:
        try:
            raw_output, _ = p.communicate(input=input, timeout=timeout)
        except subprocess.TimeoutExpired:
            logger.warning('Time limit exceeded!')
            return None, None
        except Exception as e:
            logger.warning(f'An exception was thrown while running the subprocess:\n{e}')
            return None, None
        finally:
            p.kill()
            p.wait()
            sigh._kill_spawned_docker_containers()

    elapsed_time = round(timeit.default_timer() - start_time, 2)
    logger.debug(f'Approximate elapsed runtime: {elapsed_time}/{timeout} seconds.')

    return raw_output, elapsed_time

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