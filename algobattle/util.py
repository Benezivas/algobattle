"""Collection of utility functions."""
import os
import logging
import timeit
import subprocess
import importlib.util
import sys
import collections

import algobattle
import algobattle.problems.delaytest as DelaytestProblem
import algobattle.sighandler as sigh
from algobattle.problem import Problem


logger = logging.getLogger('algobattle.util')


def import_problem_from_path(problem_path: str) -> Problem:
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
        Problem = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = Problem
        spec.loader.exec_module(Problem)

        return Problem.Problem()
    except Exception as e:
        logger.critical('Importing the given problem failed with the following exception: "{}"'.format(e))
        return None


def measure_runtime_overhead() -> float:
    """Calculate the I/O delay for starting and stopping docker on the host machine.

    Returns
    -------
    float
        I/O overhead in seconds, rounded to two decimal places.
    """
    problem = DelaytestProblem.Problem()
    config_path = os.path.join(os.path.dirname(os.path.abspath(algobattle.__file__)), 'config', 'config_delaytest.ini')
    delaytest_path = DelaytestProblem.__file__[:-12]  # remove /__init__.py
    delaytest_team = algobattle.team.Team(0, delaytest_path + '/generator', delaytest_path + '/solver')

    match = algobattle.match.Match(problem, config_path, [delaytest_team])

    if not match.build_successful:
        logger.warning('Building a match for the time tolerance calculation failed!')
        return 0

    overheads = []
    for i in range(5):
        sigh.latest_running_docker_image = "generator0"
        _, timeout = run_subprocess(match.base_run_command + ["generator0"],
                                    input=str(50 * i).encode(), timeout=match.timeout_generator)
        if not timeout:
            timeout = match.timeout_generator
        overheads.append(float(timeout))

    max_overhead = round(max(overheads), 2)

    return max_overhead


def run_subprocess(run_command: list, input: bytes, timeout: float, suppress_output=False):
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

    with subprocess.Popen(run_command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr) as p:
        try:
            raw_output, _ = p.communicate(input=input, timeout=timeout)
        except subprocess.TimeoutExpired:
            logger.warning('Time limit exceeded!')
            return None, None
        except Exception as e:
            logger.warning('An exception was thrown while running the subprocess:\n{}'.format(e))
            return None, None
        finally:
            p.kill()
            p.wait()
            sigh._kill_spawned_docker_containers()

    elapsed_time = round(timeit.default_timer() - start_time, 2)
    logger.debug('Approximate elapsed runtime: {}/{} seconds.'.format(elapsed_time, timeout))

    return raw_output, elapsed_time


def update_nested_dict(current_dict, updates):
    """Update a nested dictionary with new data recursively.

    Parameters
    ----------
    current_dict : dict
        The dict to be updated.
    updates : dict
        The dict containing the updates

    Returns
    -------
    dict
        The updated dict.
    """
    for key, value in updates.items():
        if isinstance(value, collections.abc.Mapping):
            current_dict[key] = update_nested_dict(current_dict.get(key, {}), value)
        else:
            current_dict[key] = value
    return current_dict
