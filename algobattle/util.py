"""Collection of utility functions."""
import logging
import importlib.util
import sys
import collections

from configparser import ConfigParser
from pathlib import Path

from algobattle.problem import Problem

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
