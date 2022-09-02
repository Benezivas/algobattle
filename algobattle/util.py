"""Collection of utility functions."""
import os
import logging
import timeit
import subprocess
import importlib.util
import sys
import collections

from configparser import ConfigParser
from pathlib import Path
from typing import Callable, Tuple

from algobattle.problem import Problem
import algobattle
import algobattle.problems.delaytest as DelaytestProblem
import algobattle.sighandler as sigh

logger = logging.getLogger('algobattle.util')


def import_problem_from_path(problem_path: Path) -> Problem:
    """Try to import and initialize a Problem object from a given path.

    Parameters
    ----------
    problem_path : Path
        Path in the file system to a problem folder.

    Returns
    -------
    Problem
        Returns an object of the problem.
    """
    try:
        spec = importlib.util.spec_from_file_location("problem", Path(problem_path, "__init__.py"))
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


@docker_running
def build_docker_container(container_path: Path, docker_tag: str,
                           timeout_build: int = 600, cache_docker_container: bool = True) -> bool:
    """Build docker containers for the given container_path.

    The container can later be referenced by its docker_tag.

    Parameters
    ----------
    container_path : Path
        Path to folder containing a Dockerfile in the file system.
    docker_tag : str
        The tag by which the built container can be referenced by.
    timeout_build : int
        Maximum time for building the docker container, in seconds.
    cache_docker_containers : bool
        Flag indicating whether to cache built docker container.

    Returns
    -------
    Bool
        Boolean indicating whether the build process succeeded.
    """
    build_command = [
        "docker",
        "build",
    ] + (["--no-cache"] if not cache_docker_container else []) + [
        "--network=host",
        "-t",
        docker_tag,
        str(container_path)
    ]

    build_successful = True
    logger.debug('Building docker container with the following command: {}'.format(build_command))
    creationflags = 0
    if os.name != 'posix':
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
    with subprocess.Popen(build_command, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, creationflags=creationflags) as process:
        try:
            output, _ = process.communicate(timeout=timeout_build)
            logger.debug(output.decode())
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            logger.error('Build process for {} ran into a timeout!'.format(docker_tag))
            build_successful = False
        if process.returncode != 0:
            logger.error('Build process for {} failed!'.format(docker_tag))
            build_successful = False

    return build_successful
