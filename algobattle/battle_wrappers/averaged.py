import logging

from algobattle.battle_wrapper import BattleWrapper

logger = logging.getLogger('algobattle.battle_wrappers.averaged')


class Averaged(BattleWrapper):
    """Class of an adveraged battle Wrapper."""

    def _averaged_battle_wrapper(self, match, options: dict = {}) -> None:
        """Execute one averaged battle between a generating and a solving team.

        Execute several fights between two teams on a fixed instance size
        and determine the average solution quality.

        During execution, this function updates the match_data of the match
        object which is passed to it by
        calls to the match.update_match_data function.

        Parameters
        ----------
        match: Match
            The Match object on which the battle wrapper is to be executed on.
        options: dict
            No additional options are used for this wrapper.
        """
        approximation_ratios = []
        logger.info('==================== Averaged Battle, Instance Size: {}, Rounds: {} ===================='
                    .format(match.match_data['approx_inst_size'], match.match_data['approx_iters']))
        for i in range(match.match_data['approx_iters']):
            logger.info('=============== Iteration: {}/{} ==============='.format(i + 1, match.match_data['approx_iters']))
            approx_ratio = match._one_fight(instance_size=match.match_data['approx_inst_size'])
            approximation_ratios.append(approx_ratio)

            curr_pair = match.match_data['curr_pair']
            curr_round = match.match_data[curr_pair]['curr_round']
            match.update_match_data({curr_pair: {curr_round: {'approx_ratios':
                                    match.match_data[curr_pair][curr_round]['approx_ratios'] + [approx_ratio]}}})
