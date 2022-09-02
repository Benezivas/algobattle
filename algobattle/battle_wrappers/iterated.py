"""Wrapper that repeats a battle on an instance size a number of times and averages the competitive ratio over all runs."""

from configparser import ConfigParser
import logging
from typing import Tuple

from algobattle.battle_wrapper import BattleWrapper
from algobattle.fight_handler import FightHandler
from algobattle.team import Matchup
from algobattle.util import update_nested_dict

logger = logging.getLogger('algobattle.battle_wrappers.iterated')


class Iterated(BattleWrapper):
    """Class of an iterated battle Wrapper."""

    def __init__(self, config: ConfigParser) -> None:
        if 'iterated' in config:
            self.iteration_cap = int(config['iterated'].get('iteration_cap', 50000))
            self.exponent = int(config['iterated'].get('exponent', 2))
            self.approximation_ratio = float(config['iterated'].get('approximation_ratio', 1.0))
        else:
            self.iteration_cap = 50000
            self.exponent = 2
            self.approximation_ratio = 1.0
        self.reset_round_data()

    def __str__(self) -> str:
        return "Iterated"

    def reset_round_data(self) -> None:
        """Resets the round_data dict to default values."""
        self.round_data = {'type': str(self),
                           'iteration_cap': self.iteration_cap,
                           'current_cap': self.iteration_cap,
                           'solved': 0,
                           'attempting': 0,
                           'exponent': self.exponent,
                           'approximation_ratio': self.approximation_ratio}

    @BattleWrapper.reset_state
    def run_round(self, fight_handler: FightHandler, matchup: Matchup) -> None:
        """Execute one iterative battle between a generating and a solving team.

        Incrementally try to search for the highest n for which the solver is
        still able to solve instances.  The base increment value is multiplied
        with the power of iterations since the last unsolvable instance to the
        given exponent.
        Only once the solver fails after the multiplier is reset, it counts as
        failed. Since this would heavily favour probabilistic algorithms (That
        may have only failed by chance and are able to solve a certain instance
        size on a second try), we cap the maximum solution size by the last
        value that an algorithm has failed on.

        The wrapper automatically ends the battle and declares the solver as the
        winner once the iteration cap is reached.

        During execution, this function updates the self.round_data dict,
        which automatically notifies all observers subscribed to this object.

        Parameters
        ----------
        fight_handler: FightHandler
            Fight handler that manages the execution of a concrete fight.
        """
        n = fight_handler.problem.n_start
        maximum_reached_n = 0
        base_increment = 0
        exponent = self.round_data['exponent']
        n_cap = self.round_data['iteration_cap']
        alive = True

        update_nested_dict(self.round_data, {'attempting': n})

        logger.info('==================== Iterative Battle, Instanze Size Cap: {} ===================='.format(n_cap))
        while alive:
            logger.info('=============== Instance Size: {}/{} ==============='.format(n, n_cap))

            approx_ratio = fight_handler.fight(matchup, n)
            if approx_ratio == 0.0 or approx_ratio > self.approximation_ratio:
                logger.info(f"Solver {matchup.solver} does not meet the required solution quality at instance size {n}. ({approx_ratio}/{self.approximation_ratio})")
                alive = False

            if not alive and base_increment > 1:
                # The step size increase was too aggressive, take it back and reset the base_increment
                logger.info('Setting the solution cap to {}...'.format(n))
                n_cap = n
                n -= base_increment ** exponent
                base_increment = 0
                alive = True
            elif n > maximum_reached_n and alive:
                # We solved an instance of bigger size than before
                maximum_reached_n = n

            if n + 1 > n_cap:
                alive = False
            else:
                base_increment += 1
                n += base_increment ** exponent

                if n >= n_cap:
                    # We have failed at this value of n already, reset the step size!
                    n -= base_increment ** exponent - 1
                    base_increment = 1

            update_nested_dict(self.round_data, {'current_cap': n_cap, 'solved': maximum_reached_n, 'attempting': n})

    def calculate_valuations(self, round_data0, round_data1) -> Tuple:
        """Returns the highest instance size for which each team was successful.

        round_data0: dict
            round_data in which the 0th team solved instances.
        round_data1: dict
            round_data in which the 1st team solved instances.

        Returns
        -------
        Tuple
            A 2-tuple with the calculated valuations for each team.
        """
        return (round_data0['solved'], round_data1['solved'])

    def format_round_contents(self, round_data: dict) -> str:
        """Format the provided round_data for iterated battles.

        The returned tuple is supposed to be used for formatted live outputs.

        Parameters
        ----------
        round_data : dict
            dict containing round data.

        Returns
        -------
        str
            A string of the size of the currently highest solved instance.
        """
        return str(round_data['solved'])

    def format_misc_headers(self) -> Tuple:
        """Return which strings are to be used as headers a formatted output.

        Make sure that the number of elements of the returned tuple match
        up with the number of elements returned by format_misc_contents.

        Returns
        -------
        Tuple
            A 2-tuple of strings containing header names for:
            - the current upper bound for instance sizes
            - The average instance size solved over all rounds
        """
        return ('CAP', 'AVG')

    def format_misc_contents(self, round_data: dict) -> Tuple:
        """Format additional data that is to be displayed.

        Make sure that the number of elements of the returned tuple match
        up with the number of elements returned by format_misc_headers.

        Parameters
        ----------
        round_data : dict
            dict containing round data.

        Returns
        -------
        Tuple
            A 2-tuple of strings containing header names for:
            - the current upper bound for instance sizes
            - The average instance size solved over all rounds
        """
        # TODO: We cannot calculate the average as we only have access to a single round.
        return (str(round_data['current_cap']), 'TODO')
