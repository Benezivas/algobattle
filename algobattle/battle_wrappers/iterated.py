"""Wrapper that repeats a battle on an instance size a number of times and averages the competitive ratio over all runs."""

import logging

from algobattle.battle_wrapper import BattleWrapper

logger = logging.getLogger('algobattle.battle_wrappers.iterated')


class Iterated(BattleWrapper):
    """Class of an iterated battle Wrapper."""

    def wrapper(self, match, options: dict = {'exponent': 2}) -> None:
        """Execute one iterative battle between a generating and a solving team.

        Incrementally try to search for the highest n for which the solver is
        still able to solve instances.  The base increment value is multiplied
        with the power of iterations since the last unsolvable instance to the
        given exponent.
        Only once the solver fails after the multiplier is reset, it counts as
        failed. Since this would heavily favour probabilistic algorithms (That
        may have only failed by chance and are able to solve a certain instance
        size on a second try), we cap the maximum solution size by the first
        value that an algorithm has failed on.

        The wrapper automatically ends the battle and declares the solver as the
        winner once the iteration cap is reached.

        During execution, this function updates the match_data of the match
        object which is passed to it by
        calls to the match.update_match_data function.

        Parameters
        ----------
        match: Match
            The Match object on which the battle wrapper is to be executed on.
        options: dict
            A dict that contains an 'exponent' key with an int value of at least 1,
            which determines the step size increase.
        """
        curr_pair = match.match_data['curr_pair']
        curr_round = match.match_data[curr_pair]['curr_round']

        n = match.problem.n_start
        maximum_reached_n = 0
        i = 0
        exponent = options['exponent']
        n_cap = match.match_data[curr_pair][curr_round]['cap']
        alive = True

        logger.info(f'==================== Iterative Battle, Instanze Size Cap: {n_cap} ====================')
        while alive:
            logger.info(f'=============== Instance Size: {n}/{n_cap} ===============')
            approx_ratio = match._one_fight(instance_size=n)
            if approx_ratio == 0.0:
                alive = False
            elif approx_ratio > match.approximation_ratio:
                logger.info('Solver {} does not meet the required solution quality at instance size {}. ({}/{})'
                            .format(match.solving_team, n, approx_ratio, match.approximation_ratio))
                alive = False

            if not alive and i > 1:
                # The step size increase was too aggressive, take it back and reset the increment multiplier
                logger.info(f'Setting the solution cap to {n}...')
                n_cap = n
                n -= i ** exponent
                i = 0
                alive = True
            elif n > maximum_reached_n and alive:
                # We solved an instance of bigger size than before
                maximum_reached_n = n

            if n + 1 > n_cap:
                alive = False
            else:
                i += 1
                n += i ** exponent

                if n >= n_cap:
                    # We have failed at this value of n already, reset the step size!
                    n -= i ** exponent - 1
                    i = 1

            match.update_match_data({curr_pair: {curr_round: {'cap': n_cap, 'solved': maximum_reached_n, 'attempting': n}}})

    def calculate_points(self, match_data: dict, achievable_points: int) -> dict:
        """Calculate the number of achieved points, given results.

        Each pair of teams fights for the achievable points among one another.
        These achievable points are split over all matches, as one run reaching
        the iteration cap poisons the average number of points.

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

                solved1 = match_data[pair][i]['solved']  # pair[1] was solver
                solved0 = match_data[(pair[1], pair[0])][i]['solved']  # pair[0] was solver

                # Default values for proportions, assuming no team manages to solve anything
                points_proportion0 = 0.5
                points_proportion1 = 0.5

                if solved0 + solved1 > 0:
                    points_proportion0 = (solved0 / (solved0 + solved1))
                    points_proportion1 = (solved1 / (solved0 + solved1))

                points[pair[0]] += round(points_per_iteration * points_proportion0, 1) / 2
                points[pair[1]] += round(points_per_iteration * points_proportion1, 1) / 2

        return points

    def format_as_utf8(self, match_data: dict) -> str:
        """Format the provided match_data for iterated battles.

        Parameters
        ----------
        match_data : dict
            dict containing match data generated by match.run().

        Returns
        -------
        str
            A formatted string on the basis of the match_data.
        """
        formatted_output_string = ""
        formatted_output_string += 'Battle Type: Iterated Battle\n\r'
        formatted_output_string += '╔═════════╦═════════╦' \
                                   + ''.join(['══════╦' for i in range(match_data['rounds'])]) \
                                   + '══════╦══════╗' + '\n\r' \
                                   + '║   GEN   ║   SOL   ' \
                                   + ''.join([f'║{"R" + str(i + 1):^6s}' for i in range(match_data['rounds'])]) \
                                   + '║  CAP ║  AVG ║' + '\n\r' \
                                   + '╟─────────╫─────────╫' \
                                   + ''.join(['──────╫' for i in range(match_data['rounds'])]) \
                                   + '──────╫──────╢' + '\n\r'

        for pair in match_data.keys():
            if isinstance(pair, tuple):
                curr_round = match_data[pair]['curr_round']
                avg = sum(match_data[pair][i]['solved'] for i in range(match_data['rounds'])) // match_data['rounds']

                formatted_output_string += f'║{pair[0]:>9s}║{pair[1]:>9s}' \
                                           + ''.join([f'║{match_data[pair][1]["solved"]:>6d}'
                                                     for i in range(match_data['rounds'])]) \
                                           + f'║{match_data[pair][curr_round]["cap"]:>6d}║{avg:>6d}║' + '\r\n'
        formatted_output_string += '╚═════════╩═════════╩' \
                                   + ''.join(['══════╩' for i in range(match_data['rounds'])]) \
                                   + '══════╩══════╝' + '\n\r'

        return formatted_output_string
