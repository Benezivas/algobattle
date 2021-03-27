""" Collection of utility functions."""
import os
import logging

import algobattle
import algobattle.problems.delaytest as DelaytestProblem
from algobattle.match import Match
from algobattle.team import Team
import algobattle.sighandler as sigh


logger = logging.getLogger('algobattle.util')


def measure_runtime_overhead() -> float:
    """ Calculate the I/O delay for starting and stopping docker on the host machine.

        Returns:
        ----------
        float:
            I/O overhead in seconds, rounded to two decimal places.
    """

    problem = DelaytestProblem.Problem()

    delaytest_path = DelaytestProblem.__file__[:-12]  # remove /__init__.py
    delaytest_team = Team(0, delaytest_path + '/generator', delaytest_path + '/solver')

    config_path = os.path.join(os.path.dirname(os.path.abspath(algobattle.__file__)), 'config', 'config.ini')
    match = Match(problem, config_path, [delaytest_team])

    if not match.build_successful:
        logger.warning('Building a match for the time tolerance calculation failed!')
        return 0
    overheads = []
    for i in range(10):
        sigh.latest_running_docker_image = "generator0"
        _, timeout = match._run_subprocess(match.base_build_command + ["generator0"],
                                           input=str(50*i).encode(), timeout=match.timeout_generator)
        overheads.append(float(timeout))

    max_overhead = round(max(overheads), 2)

    return max_overhead


def calculate_points(results: dict, achievable_points: int, team_names: list,
                     battle_iterations: int, battle_type: str) -> dict:
    """ Calculate the number of achieved points, given results.

    Parameters:
    ----------
    results: dict
        dict containing the results of match.run().
    achievable_points: int
        Number of achievable points.
    team_names: list
        List of all team names involved in the match leading to the results parameter.
    battle_iterations: int
        Number of iterations that were made in the match.
    batte_type: str
        Type of battle that was held.
    Returns:
    ----------
    dict:
        A mapping between team names and their achieved points.
    """
    points = dict()
    # We want all groups to be able to achieve the same number of total points, regardless of the number of teams
    normalizer = max(len(team_names) - 1, 1)
    for i in range(len(team_names)):
        for j in range(i+1, len(team_names)):
            points[team_names[i]] = points.get(team_names[i], 0)
            points[team_names[j]] = points.get(team_names[j], 0)
            # Points are awarded for each match individually, as one run reaching the cap poisons the average number of points
            for k in range(battle_iterations):
                results[(team_names[i], team_names[j])][i]
                if battle_type == 'iterated':
                    valuation0 = results[(team_names[i], team_names[j])][k]
                    valuation1 = results[(team_names[j], team_names[i])][k]
                elif battle_type == 'averaged':
                    # The valuation of an averaged battle
                    # is the number of successfully executed battles divided by
                    # the average competitive ratio of successful battles,
                    # to account for failures on execution. A higher number
                    # thus means a better overall result. Normalized to the number of configured points.
                    valuation0 = (len(results[(team_names[i], team_names[j])][k]) /
                                  (sum(results[(team_names[i], team_names[j])][k]) /
                                   len(results[(team_names[i], team_names[j])][k])))
                    valuation1 = (len(results[(team_names[j], team_names[i])][k]) /
                                  (sum(results[(team_names[j], team_names[i])][k]) /
                                   len(results[(team_names[j], team_names[i])][k])))
                else:
                    logger.info('Unclear how to calculate points for this type of battle.')

                if valuation0 + valuation1 > 0:
                    points[team_names[i]] += ((achievable_points/battle_iterations * valuation0) /
                                              (valuation0 + valuation1)) // normalizer
                    points[team_names[j]] += ((achievable_points/battle_iterations * valuation1) /
                                              (valuation0 + valuation1)) // normalizer
                else:
                    points[team_names[i]] += ((achievable_points/battle_iterations) // 2) // normalizer
                    points[team_names[j]] += ((achievable_points/battle_iterations) // 2) // normalizer

    return points
