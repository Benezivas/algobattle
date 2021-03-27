import subprocess

import logging
import configparser

import algobattle.sighandler as sigh
from algobattle.team import Team
from algobattle.problem import Problem
from algobattle.util import run_subprocess

logger = logging.getLogger('algobattle.match')


class Match:
    """ Match class, provides functionality for setting up and executing battles
    between given teams.
    """
    def __init__(self, problem: Problem, config_path: str, teams: list,
                 runtime_overhead=0, approximation_ratio=1.0, cache_docker_containers=True):

        config = configparser.ConfigParser()
        logger.debug('Using additional configuration options from file "%s".', config_path)
        config.read(config_path)

        self.timeout_build           = int(config['run_parameters']['timeout_build']) + runtime_overhead
        self.timeout_generator       = int(config['run_parameters']['timeout_generator']) + runtime_overhead
        self.timeout_solver          = int(config['run_parameters']['timeout_solver']) + runtime_overhead
        self.space_generator         = int(config['run_parameters']['space_generator'])
        self.space_solver            = int(config['run_parameters']['space_solver'])
        self.cpus                    = int(config['run_parameters']['cpus'])
        self.iteration_cap           = int(config['run_parameters']['iteration_cap'])
        self.aproximation_iterations = int(config['run_parameters']['aproximation_iterations'])
        self.problem = problem
        self.config = config
        self.approximation_ratio = approximation_ratio

        self.generating_team = None
        self.solving_team = None
        self.build_successful = self._build(teams, cache_docker_containers)

        if approximation_ratio != 1.0 and not problem.approximable:
            logger.error('The given problem is not approximable and can only be run with an approximation ratio of 1.0!')
            self.build_successful = False

        self.base_build_command = [
            "docker",
            "run",
            "--rm",
            "--network", "none",
            "-i",
            "--memory=" + str(self.space_solver) + "mb",
            "--cpus=" + str(self.cpus)
        ]

    def build_successful(function):
        """ Decorator that ensures that internal methods are only callable after
            a successful build.
        """
        def wrapper(self, *args, **kwargs):
            if not self.build_successful:
                logger.error('Trying to call Match object which failed to build!')
                return None
            else:
                return function(self, *args, **kwargs)
        return wrapper

    def team_roles_set(function):
        """ Decorator that ensures that internal methods are only callable after
            the generating_team and solving_team have been set.
        """
        def wrapper(self, *args, **kwargs):
            if not self.generating_team or not self.solving_team:
                logger.error('Generating or solving team have not been set!')
                return None
            else:
                return function(self, *args, **kwargs)
        return wrapper

    def docker_running(function):
        """ Decorator that ensures that internal methods are only callable if
        docker is running.
        """
        def wrapper(self, *args, **kwargs):
            docker_running = subprocess.Popen(['docker', 'info'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            _ = docker_running.communicate()
            if docker_running.returncode:
                logger.error('Could not connect to the docker daemon. Is docker running?')
                return None
            else:
                return function(self, *args, **kwargs)
        return wrapper

    @docker_running
    def _build(self, teams, cache_docker_containers):
        """ Builds docker containers for the given generators and solvers of each
            team.

        Parameters:
        ----------
        teams: list
            List of Team objects.
        Returns:
        ----------
        Bool:
            Boolean indicating whether the build process succeeded.
        """
        docker_build_base = [
            "docker",
            "build",
        ] + (["--no-cache"] if not cache_docker_containers else []) + [
            "--network=host",
            "-t"
        ]

        if not isinstance(teams, list) or any(not isinstance(team, Team) for team in teams):
            logger.error('Teams argument is expected to be a list of Team objects!')
            return False

        self.team_names = [team.name for team in teams]
        build_commands = []
        if len(self.team_names) != len(list(set(self.team_names))):
            logger.error('At least one team name is used twice!')
            return False

        self.single_player = False
        if len(teams) == 1:
            self.single_player = True

        for team in teams:
            build_commands.append(docker_build_base + ["solver-" + str(team.name), team.solver_path])
            build_commands.append(docker_build_base + ["generator-" + str(team.name), team.generator_path])

        for command in build_commands:
            logger.debug('Building docker container with the following command: {}'.format(command))
            with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
                try:
                    output, _ = process.communicate(timeout=self.timeout_build)
                    logger.debug(output.decode())
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                    logger.error('Build process for {} ran into a timeout!'.format(command[5]))
                    return False
                if process.returncode != 0:
                    process.kill()
                    process.wait()
                    logger.error('Build process for {} failed!'.format(command[5]))
                    return False

        return True

    @build_successful
    def all_battle_pairs(self):
        """ Returns a list of all team pairings for battles.
        """
        battle_pairs = []
        for i in range(len(self.team_names)):
            for j in range(len(self.team_names)):
                battle_pairs.append((self.team_names[i], self.team_names[j]))

        if not self.single_player:
            battle_pairs = [pair for pair in battle_pairs if pair[0] != pair[1]]

        return battle_pairs

    @build_successful
    def run(self, battle_type='iterated', iterations=5, approximation_instance_size=10):
        """ Match entry point. Executes iterations fights between all teams and
        returns the results of the battles.

        Parameters:
        ----------
        battle_type: str
            Type of battle that is to be run.
        iterations: int
            Number of Battles between each pair of teams (used for averaging results).
        Returns:
        ----------
        dict
            A dictionary containing the results of the battles for each team with
            the team number as a key.
        """
        results = dict()
        battle_wrapper = None
        self.approximation_instance_size = approximation_instance_size

        if battle_type == 'iterated':
            battle_wrapper = self._iterated_battle_wrapper
        elif battle_type == 'averaged':
            battle_wrapper = self._averaged_battle_wrapper
        else:
            logger.error('Unrecognized battle_type given: "{}"'.format(battle_type))
            return {'Error': 'Unrecognized battle type'}

        for pair in self.all_battle_pairs():
            results[pair] = results.get(pair, [])
            pair_results = []
            for i in range(iterations):
                logger.info('{}  Running Battle {}/{}  {}'.format('#'*20, i+1, iterations, '#'*20))

                self.generating_team = pair[0]
                self.solving_team = pair[1]
                pair_results.append(battle_wrapper())
            results[pair] = pair_results

        return results

    @build_successful
    @team_roles_set
    def _averaged_battle_wrapper(self):
        """ Wrapper to execute one averaged battle between a generating
        and a solving team.

        Execute several fights between two teams on a fixed instance size
        and determine the average solution quality.

        Returns:
        ----------
        list
            Returns a list of the computed approximation ratios.
        """
        approximation_ratios = []
        logger.info('==================== Averaged Battle, Instance Size: {}, Iterations: {} ===================='
                    .format(self.approximation_instance_size, self.aproximation_iterations))
        for i in range(self.aproximation_iterations):
            logger.info('=============== Iteration: {}/{} ==============='.format(i+1, self.aproximation_iterations))
            approx_ratio = self._one_fight(instance_size=self.approximation_instance_size)
            approximation_ratios.append(approx_ratio)

        return approximation_ratios

    @build_successful
    @team_roles_set
    def _iterated_battle_wrapper(self):
        """ Wrapper to execute one iterative battle between a generating and a
        solving team.

        Incrementally try to search for the highest n for which the solver is
        still able to solve instances.  The base increment value is multiplied
        with the square of the iterations since the last unsolvable instance.
        Only once the solver fails after the multiplier is reset, it counts as
        failed. Since this would heavily favour probabilistic algorithms (That
        may have only failed by chance and are able to solve a certain instance
        size on a second try), we cap the maximum solution size by the first
        value that an algorithm has failed on.

        The wrapper automatically ends the battle and declares the solver as the
        winner once the iteration cap is reached, which is set in the
        config.ini.

        Returns:
        ----------
        int
            Returns the biggest instance size for which the solving team still
            found a solution.
        """
        n = self.problem.n_start
        maximum_reached_n = 0
        i = 0
        n_cap = self.iteration_cap
        alive = True

        logger.info('==================== Iterative Battle, Instanze Size Cap: {} ===================='.format(n_cap))
        while alive:
            logger.info('=============== Instance Size: {}/{} ==============='.format(n, n_cap))
            approx_ratio = self._one_fight(instance_size=n)
            if approx_ratio == 0.0:
                alive = False
            elif approx_ratio > self.approximation_ratio:
                logger.info('Solver {} does not meet the required solution quality at instance size {}. ({}/{})'
                            .format(self.solving_team, n, approx_ratio, self.approximation_ratio))
                alive = False

            if not alive and i > 1:
                # The step size increase was too aggressive, take it back and reset the increment multiplier
                logger.info('Setting the solution cap to {}...'.format(n))
                n_cap = n
                n -= i * i
                i = 0
                alive = True
            elif n > maximum_reached_n and alive:
                # We solved an instance of bigger size than before
                maximum_reached_n = n

            if n+1 == n_cap:
                alive = False
                break

            i += 1
            n += i * i

            if n >= n_cap and n_cap != self.iteration_cap:
                # We have failed at this value of n already, reset the step size!
                n -= i * i - 1
                i = 1
            elif n >= n_cap and n_cap == self.iteration_cap:
                logger.info('Solver {} exceeded the instance size cap of {}!'.format(self.solving_team, self.iteration_cap))
                maximum_reached_n = self.iteration_cap
                alive = False
        return maximum_reached_n

    @docker_running
    @build_successful
    @team_roles_set
    def _one_fight(self, instance_size):
        """Executes a single fight of a battle between a given generator and
        solver for a given instance size.

        Parameters:
        ----------
        instance_size: int
            The instance size, expected to be a positive int.
        Returns:
        ----------
        float
            Returns the approximation ratio of the solver against
            the generator (1 if optimal, 0 if failed, >=1 if the
            generator solution is optimal).
        """
        if not isinstance(instance_size, int) or not instance_size > 0:
            logger.error('Expected an instance size to be an int of size at least 1, received: {}'.format(instance_size))
            raise Exception('Expected the instance size to be a positive integer.')

        generator_run_command = self.base_build_command + ["generator-" + str(self.generating_team)]
        solver_run_command    = self.base_build_command + ["solver-"    + str(self.solving_team)]

        logger.info('Running generator of group {}...\n'.format(self.generating_team))

        sigh.latest_running_docker_image = "generator-" + str(self.generating_team)
        encoded_output, _ = run_subprocess(generator_run_command, str(instance_size).encode(),
                                                             self.timeout_generator)
        if not encoded_output:
            return 1.0

        raw_instance_with_solution = self.problem.parser.decode(encoded_output)

        logger.info('Checking generated instance and certificate...')

        raw_instance, raw_solution = self.problem.parser.split_into_instance_and_solution(raw_instance_with_solution)
        instance                   = self.problem.parser.parse_instance(raw_instance, instance_size)
        generator_solution         = self.problem.parser.parse_solution(raw_solution, instance_size)

        if not self.problem.verifier.verify_semantics_of_instance(instance, instance_size):
            logger.warning('Generator {} created a malformed instance at instance size {}!'
                           .format(self.generating_team, instance_size))
            return 1.0

        if not self.problem.verifier.verify_semantics_of_solution(generator_solution, instance_size, True):
            logger.warning('Generator {} created a malformed solution at instance size {}!'
                           .format(self.generating_team, instance_size))
            return 1.0

        if not self.problem.verifier.verify_solution_against_instance(instance, generator_solution, instance_size, True):
            logger.warning('Generator {} failed at instance size {} due to a wrong certificate for its generated instance!'
                           .format(self.generating_team, instance_size))
            return 1.0

        logger.info('Generated instance and certificate are valid!\n\n')

        logger.info('Running solver of group {}...\n'.format(self.solving_team))

        sigh.latest_running_docker_image = "solver-" + str(self.solving_team)
        encoded_output, _ = run_subprocess(solver_run_command, self.problem.parser.encode(instance),
                                                      self.timeout_solver)
        if not encoded_output:
            return 0.0

        raw_solver_solution = self.problem.parser.decode(encoded_output)

        logger.info('Checking validity of the solvers solution...')

        solver_solution = self.problem.parser.parse_solution(raw_solver_solution, instance_size)
        if not self.problem.verifier.verify_semantics_of_solution(solver_solution, instance_size, True):
            logger.warning('Solver {} created a malformed solution at instance size {}!'
                           .format(self.solving_team, instance_size))
            return 0.0
        elif not self.problem.verifier.verify_solution_against_instance(instance, solver_solution, instance_size, False):
            logger.warning('Solver {} yields a wrong solution at instance size {}!'
                           .format(self.solving_team, instance_size))
            return 0.0
        else:
            approximation_ratio = self.problem.verifier.calculate_approximation_ratio(instance, instance_size,
                                                                                      generator_solution, solver_solution)
            logger.info('Solver {} yields a valid solution with an approx. ratio of {} at instance size {}.'
                        .format(self.solving_team, approximation_ratio, instance_size))
            return approximation_ratio
