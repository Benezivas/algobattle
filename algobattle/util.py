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
        dict containing the results of match.run().

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


def calculate_points(match_data: dict, achievable_points: int) -> dict:
    """Calculate the number of achieved points, given results.

    Parameters
    ----------
    match_data : dict
        dict containing the results of match.run().
    achievable_points : int
        Number of achievable points.

    Returns
    -------
    dict
        A mapping between team names and their achieved points.
    """
    points = dict()

    team_pairs = [key for key in match_data.keys() if isinstance(key, tuple)]
    team_names = set()
    for pair in team_pairs:
        team_names = team_names.union(set((pair[0], pair[1])))

    if len(team_names) == 1:
        return {team_names.pop(): achievable_points}

    # We want all groups to be able to achieve the same number of total points, regardless of the number of teams
    normalizer = len(team_names)
    if match_data['rounds'] <= 0:
        return {}
    points_per_iteration = round(achievable_points / match_data['rounds'], 1)
    for pair in team_pairs:
        # Points are awarded for each match individually, as one run reaching the cap poisons the average number of points
        for i in range(match_data['rounds']):
            points[pair[0]] = points.get(pair[0], 0)
            points[pair[1]] = points.get(pair[1], 0)

            if match_data['type'] == 'iterated':
                valuation0 = match_data[pair][i]['solved']
                valuation1 = match_data[(pair[1], pair[0])][i]['solved']
            elif match_data['type'] == 'averaged':
                # The valuation of an averaged battle
                # is the number of successfully executed battles divided by
                # the average competitive ratio of successful battles,
                # to account for failures on execution. A higher number
                # thus means a better overall result. Normalized to the number of configured points.

                ratios0 = match_data[pair][i]['approx_ratios']
                ratios1 = match_data[(pair[1], pair[0])][i]['approx_ratios']
                valuation0 = (len(ratios0) / (sum(ratios0) / len(ratios0)))
                valuation1 = (len(ratios1) / (sum(ratios1) / len(ratios1)))
            else:
                logger.info('Unclear how to calculate points for this type of battle.')

            if valuation0 + valuation1 > 0:
                points_proportion0 = (valuation0 / (valuation0 + valuation1))
                points_proportion1 = (valuation1 / (valuation0 + valuation1))
                points[pair[0]] += round((points_per_iteration * points_proportion1) / normalizer, 1)
                points[pair[1]] += round((points_per_iteration * points_proportion0) / normalizer, 1)
            else:
                points[pair[0]] += round((points_per_iteration // 2) / normalizer, 1)
                points[pair[1]] += round((points_per_iteration // 2) / normalizer, 1)

    return points


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
