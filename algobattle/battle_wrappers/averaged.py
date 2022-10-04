"""Wrapper that iterates the instance size up to a point where the solving team is no longer able to solve an instance."""

from configparser import ConfigParser
import logging
from typing import Tuple

from algobattle.battle_wrapper import BattleWrapper
from algobattle.fight_handler import FightHandler
from algobattle.team import Matchup
from algobattle.util import update_nested_dict

logger = logging.getLogger('algobattle.battle_wrappers.averaged')


class Averaged(BattleWrapper):
    """Class of an adveraged battle Wrapper."""

    def __init__(self, config: ConfigParser) -> None:
        super().__init__()
        if 'averaged' in config:
            self.approximation_instance_size = int(config['averaged'].get('approximation_instance_size', "10"))
            self.approximation_iterations = int(config['averaged'].get('approximation_iterations', "10"))
        else:
            self.approximation_instance_size = 10
            self.approximation_iterations = 10
        self.reset_round_data()

    def __str__(self) -> str:
        return "Averaged"

    def reset_round_data(self) -> None:
        """Resets the round_data dict to default values."""
        self.round_data = {'type': str(self),
                           'approx_inst_size': self.approximation_instance_size,
                           'approx_iters': self.approximation_iterations,
                           'approx_ratios': []}

    @BattleWrapper.reset_state
    def run_round(self, fight_handler: FightHandler, matchup: Matchup) -> None:
        """Execute one averaged battle between a generating and a solving team.

        Execute several fights between two teams on a fixed instance size
        and determine the average solution quality.

        During execution, this function updates the match_data of the match
        object which is passed to it by
        calls to the match.update_match_data function.

        Parameters
        ----------
        fight_handler: FightHandler
            Fight handler that manages the execution of a concrete fight.
        """
        logger.info('==================== Averaged Battle, Instance Size: {}, Rounds: {} ===================='
                    .format(self.round_data['approx_inst_size'], self.round_data['approx_iters']))
        for i in range(self.round_data['approx_iters']):
            logger.info('=============== Iteration: {}/{} ==============='.format(i + 1, self.round_data['approx_iters']))
            approx_ratio = fight_handler.fight(matchup, self.round_data['approx_inst_size'])

            update_nested_dict(self.round_data, {'approx_ratios': self.round_data['approx_ratios'] + [approx_ratio]})

    def calculate_valuations(self, round_data0, round_data1) -> Tuple:
        """Returns a valuation based on the average competitive ratios.

        The valuation of an averaged battle is calculated by summing up
        the reciprocals of each solved fight. This sum is then divided by
        the total number of ratios to account for unsuccessful battles.

        round_data0: dict
            round_data in which the 0th team solved instances.
        round_data1: dict
            round_data in which the 1st team solved instances.

        Returns
        -------
        Tuple
            A 2-tuple with the calculated valuations for each team.
        """
        ratios0 = round_data0['approx_ratios']
        ratios1 = round_data1['approx_ratios']

        valuation0 = 0
        valuation1 = 0
        if ratios0 and sum(ratios0) != 0:
            valuation0 = sum(1 / x if x != 0 else 0 for x in ratios0) / len(ratios0)
        if ratios1 and sum(ratios1) != 0:
            valuation1 = sum(1 / x if x != 0 else 0 for x in ratios1) / len(ratios1)

        return (valuation0, valuation1)

    def format_round_contents(self, round_data: dict) -> str:
        """Format the provided round_data for averaged battles.

        The returned tuple is supposed to be used for formatted live outputs.

        Parameters
        ----------
        round_data : dict
            dict containing round data.

        Returns
        -------
        str
            A string of the current average competitive ratio.
        """
        avg = 0.0

        executed_iters = len(round_data['approx_ratios'])
        n_dead_iters = len([i for i in round_data['approx_ratios'] if i == 0.0])

        if executed_iters - n_dead_iters > 0:
            avg = round(sum(round_data['approx_ratios']) // (executed_iters - n_dead_iters), 1)

        return '{:6.2f}'.format(avg)

    def format_misc_headers(self) -> Tuple:
        """Return which strings are to be used as headers a formatted output.

        Make sure that the number of elements of the returned tuple match
        up with the number of elements returned by format_misc_contents.

        Returns
        -------
        Tuple
            A 3-tuple of strings containing header names for:
            - the latest achieved approximation ratio
            - the size of the instance that is being solved
            - (current iteration / total iterations)
        """
        return ('LAST', 'SIZE', 'ITER')

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
            A 3-tuple of strings containing:
            - the latest achieved approximation ratio
            - the size of the instance that is being solved
            - (current iteration / total iterations)
        """
        curr_iter = len(round_data['approx_ratios'])
        latest_approx_ratio = 0.0
        if round_data['approx_ratios']:
            latest_approx_ratio = round_data['approx_ratios'][-1]

        return ('{:6.2f}'.format(latest_approx_ratio),
                '{:>9d}'.format(round_data['approx_inst_size']),
                '{:>4d}/{:>4d}'.format(curr_iter, round_data['approx_iters']))
