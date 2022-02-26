"""Collection of utility functions."""
from configparser import ConfigParser
import os
import logging
import timeit
import subprocess
import importlib.util
import sys
import collections
from typing import Callable

from algobattle.problem import Problem
import algobattle
import algobattle.problems.delaytest as DelaytestProblem
import algobattle.sighandler as sigh

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
        Returns an object of the problem.
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


def initialize_wrapper(wrapper_name: str, config: ConfigParser):
    """Try to import and initialize a Battle Wrapper from a given name.

    For this to work, a BattleWrapper module with the same name as the argument
    needs to be present in the algobattle/battle_wrappers folder.

    Parameters
    ----------
    wrapper : str
        Name of a battle wrapper module in algobattle/battle_wrappers.

    config : ConfigParser
        A ConfigParser object containing possible additional arguments for the battle_wrapper.

    Returns
    -------
    BattleWrapper
        A BattleWrapper object of the given wrapper_name.
    """
    try:
        wrapper_module = importlib.import_module("algobattle.battle_wrappers." + str(wrapper_name))
        return getattr(wrapper_module, wrapper_name.capitalize())(config)
    except Exception as e:
        logger.critical('Importing a wrapper from the given path failed with the following exception: "{}"'.format(e))
        return None


def measure_runtime_overhead() -> float:
    """Calculate the I/O delay for starting and stopping docker on the host machine.

    Returns
    -------
    float
        I/O overhead in seconds, rounded to two decimal places.
    """
    problem = DelaytestProblem.Problem()
    config = ConfigParser()
    config.read(os.path.join(os.path.dirname(os.path.abspath(algobattle.__file__)), 'config', 'config_delaytest.ini'))
    delaytest_path = DelaytestProblem.__file__[:-12]  # remove /__init__.py
    # TODO: We do not need a complete team here, only generator0. Move container creation out of team.
    delaytest_team = algobattle.team.Team(0,
                                          delaytest_path + '/generator',
                                          delaytest_path + '/solver',
                                          config['run_parameters']['timeout_build'])
    if not delaytest_team.build_successful:
        logger.warning('Building the generator or solver for the time tolerance calculation failed!')
        return 0
    fight_handler = algobattle.fight_handler.FightHandler(problem, config)

    overheads = []
    for i in range(5):
        sigh.latest_running_docker_image = "generator0"
        _, timeout = run_subprocess(fight_handler.base_run_command(fight_handler.space_generator) + ["generator0"],
                                    input=str(50 * i).encode(), timeout=fight_handler.timeout_generator)
        if not timeout:
            timeout = fight_handler.timeout_generator
        overheads.append(float(timeout))

    max_overhead = round(max(overheads), 2)

    return max_overhead


def run_subprocess(run_command: list, input: bytes, timeout: float, suppress_output: bool = False) -> None:
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
            logger.warning('An exception was thrown while running the subprocess:\n{}'.format(e))
            return None, None
        finally:
            p.kill()
            p.wait()
            sigh._kill_spawned_docker_containers()

    elapsed_time = round(timeit.default_timer() - start_time, 2)
    logger.debug('Approximate elapsed runtime: {}/{} seconds.'.format(elapsed_time, timeout))

    return raw_output, elapsed_time


def update_nested_dict(current_dict: dict, updates: dict) -> dict:
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


def docker_running(function: Callable) -> Callable:
    """Ensure that internal methods are only callable if docker is running."""
    def wrapper(self, *args, **kwargs):
        creationflags = 0
        if os.name != 'posix':
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
        docker_running = subprocess.Popen(['docker', 'info'], stdout=subprocess.PIPE,
                                          stderr=subprocess.PIPE, creationflags=creationflags)
        _ = docker_running.communicate()
        if docker_running.returncode:
            logger.error('Could not connect to the docker daemon. Is docker running?')
            return None
        else:
            return function(self, *args, **kwargs)
    return wrapper
