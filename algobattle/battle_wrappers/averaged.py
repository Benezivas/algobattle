"""Wrapper that iterates the instance size up to a point where the solving team is no longer able to solve an instance."""

import logging

from algobattle.battle_wrapper import BattleWrapper

logger = logging.getLogger('algobattle.battle_wrappers.averaged')


class Averaged(BattleWrapper):
    """Class of an adveraged battle Wrapper."""

    def wrapper(self, match, options: dict = {}) -> None:
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

    def calculate_points(match_data: dict, achievable_points: int) -> dict:
        """Calculate the number of achieved points, given results.

        The valuation of an averaged battle is the number of successfully
        executed battles divided by the average competitive ratio of successful
        battles, to account for failures on execution.

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
            The format is {(team_x_name, team_y_name): points [...]} for each
            pair (x,y) for which there is an entry in match_data and points is a
            float value. Returns an empty dict if no battle was fought.
        """
        points = dict()

        team_pairs = [key for key in match_data.keys() if isinstance(key, tuple)]
        team_names = set()
        for pair in team_pairs:
            team_names = team_names.union(set((pair[0], pair[1])))

        if len(team_names) == 1:
            return {team_names.pop(): achievable_points}

        if match_data['rounds'] <= 0:
            return {}
        points_per_iteration = round(achievable_points / match_data['rounds'], 1)
        for pair in team_pairs:
            for i in range(match_data['rounds']):
                points[pair[0]] = points.get(pair[0], 0)
                points[pair[1]] = points.get(pair[1], 0)

                ratios1 = match_data[pair][i]['approx_ratios']  # pair[1] was solver
                ratios0 = match_data[(pair[1], pair[0])][i]['approx_ratios']  # pair[0] was solver

                valuation0 = (len(ratios0) / sum(ratios0)) / len(ratios0)
                valuation1 = (len(ratios1) / sum(ratios1)) / len(ratios1)

                # Default values for proportions, assuming no team manages to solve anything
                points_proportion0 = 0.5
                points_proportion1 = 0.5

                # Normalize valuations
                if valuation0 + valuation1 > 0:
                    points_proportion0 = (valuation0 / (valuation0 + valuation1))
                    points_proportion1 = (valuation1 / (valuation0 + valuation1))

                points[pair[0]] += round(points_per_iteration * points_proportion1, 1)
                points[pair[1]] += round(points_per_iteration * points_proportion0, 1)

        return points
