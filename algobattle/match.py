import subprocess
import timeit
import logging
import configparser

import algobattle.sighandler as sigh
from algobattle.team import Team
from algobattle.problem import Problem

logger = logging.getLogger('algobattle.framework')

class Match:
    """ Match class, responsible for setting up and executing the battles
    between given teams. 
    """
    def __init__(self, problem: Problem, config_path: str, teams: list, runtime_overhead=0, approximation_ratio=1.0, approximation_instance_size=10, approximation_iterations=50, testing=False):

        config = configparser.ConfigParser()
        logger.info('Using additional configuration options from file "%s".', config_path)
        config.read(config_path)

        self.timeout_build     = int(config['run_parameters']['timeout_build']) + runtime_overhead
        self.timeout_generator = int(config['run_parameters']['timeout_generator']) + runtime_overhead
        self.timeout_solver    = int(config['run_parameters']['timeout_solver']) + runtime_overhead
        self.space_generator   = int(config['run_parameters']['space_generator']) 
        self.space_solver      = int(config['run_parameters']['space_solver'])
        self.cpus              = int(config['run_parameters']['cpus'])
        self.iteration_cap     = int(config['run_parameters']['iteration_cap'])
        self.problem = problem
        self.config = config
        self.approximation_ratio = approximation_ratio
        self.approximation_instance_size = approximation_instance_size
        self.aproximation_iterations = approximation_iterations
        self.testing = testing

        self.generating_team = None
        self.solving_team = None
        self.build_successful = self._build(teams)

        if approximation_ratio != 1.0 and not problem.approximable:
            logger.error('The given problem is not approximable and can only be run with an approximation ratio of 1.0!')

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
            if not isinstance(self.generating_team, int) or not isinstance(self.solving_team, int):
                logger.error('Generating or solving team have not been set!')
                return None
            else:
                return function(self, *args, **kwargs)
        return wrapper

    def _build(self, teams):
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
        ] + (["--no-cache"] if self.testing else []) + [
            "--network=host",
            "-t"
        ]

        if not isinstance(teams, list) or any(not isinstance(team, Team) for team in teams):
            logger.error('Teams argument is expected to be a list of Team objects!')
            return False

        self.team_numbers = [team.group_number for team in teams]
        build_commands = []
        if len(self.team_numbers) != len(list(set(self.team_numbers))):
            logger.error('At least one team number is used twice!')
            return False


        self.single_player = False
        if len(teams) == 1:
            self.single_player = True

        for team in teams:
            if not isinstance(team.group_number, int):
                logger.error('Team numbers are expected to be nonnegative ints, received "{}".'.format(team.group_number))
                return False
            elif not team.group_number >= 0:
                logger.error('Team numbers are expected to be nonnegative ints, received "{}".'.format(team.group_number))
                return False

        
            build_commands.append(docker_build_base + ["solver" +   str(team.group_number), team.solver_path])
            build_commands.append(docker_build_base + ["generator"+ str(team.group_number), team.generator_path])

        for command in build_commands:
            logger.debug('Building docker container with the following command: {}'.format(command))
            with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
                try:
                    output, _ = process.communicate(timeout=self.timeout_build)
                    logger.debug(output.decode())
                except subprocess.TimeoutExpired as e:
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
        for i in range(len(self.team_numbers)):
            for j in range(len(self.team_numbers)):
                battle_pairs.append((self.team_numbers[i], self.team_numbers[j]))

        if not self.single_player:
            battle_pairs = [pair for pair in battle_pairs if pair[0] != pair[1]]

        return battle_pairs

    @build_successful
    def run(self, battle_type='iterated', iterations=5):
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

        if battle_type == 'iterated':
            battle_wrapper = self._iterated_battle_wrapper
        elif battle_type == 'averaged':
            battle_wrapper = self._averaged_battle_wrapper
        else:
            logger.error('Unrecognized battle_type given: "{}"'.format(battle_type))
            return []

        for pair in self.all_battle_pairs():
            results[pair] = results.get(pair, [])
            pair_results = []
            for i in range(iterations):
                logger.info('{}  Running Battle {}/{}  {}'.format('#'*20, i+1,iterations, '#'*20))

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
        logger.info('==================== Averaged Battle, Instance Size: {}, Iterations: {} ===================='.format(self.approximation_instance_size, self.aproximation_iterations))
        for i in range(self.aproximation_iterations):
            logger.info('=============== Iteration: {}/{} ==============='.format(i+1,self.aproximation_iterations))
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
            logger.info('=============== Instance Size: {}/{} ==============='.format(n,n_cap))
            approx_ratio = self._one_fight(instance_size=n)
            if approx_ratio == 0.0:
                alive = False
            elif approx_ratio > self.approximation_ratio:
                logger.info('Solver {} does not meet the required solution quality at instance size {}. ({}/{})'.format(self.solving_team, n, approx_ratio, self.approximation_ratio))
                alive = False

            if not alive and i > 1:
                #The step size increase was too aggressive, take it back and reset the increment multiplier
                logger.info('Setting the solution cap to {}...'.format(n))
                n_cap = n
                n -= i * i
                i = 0
                alive = True
            elif n > maximum_reached_n and alive:
                #We solved an instance of bigger size than before
                maximum_reached_n = n

            if n+1 == n_cap:
                alive = False
                break
            
            i += 1
            n += i * i

            if n >= n_cap and n_cap != self.iteration_cap:
                #We have failed at this value of n already, reset the step size!
                n -= i * i - 1
                i = 1
            elif n >= n_cap and n_cap == self.iteration_cap:
                logger.info('Solver {} exceeded the instance size cap of {}!'.format(self.solving_team, self.iteration_cap))
                maximum_reached_n = self.iteration_cap
                alive = False
        return maximum_reached_n

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

        generator_run_command = self.base_build_command + ["generator" + str(self.generating_team)]
        solver_run_command    = self.base_build_command + ["solver"    + str(self.solving_team)]

        logger.info('Running generator of group {}...\n'.format(self.generating_team))

        sigh.latest_running_docker_image = "generator" + str(self.generating_team)
        raw_instance_with_solution, elapsed_time = self._run_subprocess(generator_run_command, str(instance_size).encode(), self.timeout_generator)
        logger.info('Approximate elapsed runtime: {}/{} seconds.'.format(elapsed_time, self.timeout_generator))
        if not raw_instance_with_solution and float(elapsed_time) > self.timeout_generator:
            logger.warning('Generator {} exceeded the given time limit at instance size {}!'.format(self.generating_team, instance_size))
            return 1.0
        elif not raw_instance_with_solution:
            logger.warning('Generator {} threw an exception at instance size {}!'.format(self.generating_team, instance_size))
            return 1.0

        logger.info('Checking generated instance and certificate...')

        raw_instance, raw_solution = self.problem.parser.split_into_instance_and_solution(raw_instance_with_solution)
        instance                   = self.problem.parser.parse_instance(raw_instance, instance_size)
        generator_solution         = self.problem.parser.parse_solution(raw_solution, instance_size)

        if not self.problem.verifier.verify_semantics_of_instance(instance, instance_size):
            logger.warning('Generator {} created a malformed instance at instance size {}!'.format(self.generating_team, instance_size))
            return 1.0

        if not self.problem.verifier.verify_semantics_of_solution(instance, generator_solution, instance_size, True):
            logger.warning('Generator {} created a malformed solution at instance size {}!'.format(self.generating_team, instance_size))
            return 1.0

        if not self.problem.verifier.verify_solution_against_instance(instance, generator_solution, instance_size, True):
            logger.warning('Generator {} failed at instance size {} due to a wrong certificate for its generated instance!'.format(self.generating_team, instance_size))
            return 1.0

        logger.info('Generated instance and certificate are valid!\n\n')



        logger.info('Running solver of group {}...\n'.format(self.solving_team))

        sigh.latest_running_docker_image = "solver" + str(self.solving_team)
        raw_solver_solution, elapsed_time = self._run_subprocess(solver_run_command, self.problem.parser.encode(instance), self.timeout_solver)
        logger.info('Approximate elapsed runtime: {}/{} seconds.'.format(elapsed_time, self.timeout_solver))
        if not raw_solver_solution and float(elapsed_time) > self.timeout_generator:
            logger.warning('Solver {} exceeded the given time limit at instance size {}!'.format(self.solving_team, instance_size))
            return 0.0
        elif not raw_solver_solution:
            logger.warning('Solver {} threw an exception at instance size {}!'.format(self.solving_team, instance_size))
            return 0.0

        logger.info('Checking validity of the solvers solution...')
        
        solver_solution = self.problem.parser.parse_solution(raw_solver_solution, instance_size)
        if not self.problem.verifier.verify_semantics_of_solution(instance, solver_solution, instance_size, True):
            logger.warning('Solver {} created a malformed solution at instance size {}!'.format(self.solving_team, instance_size))
            return 0.0
        elif not self.problem.verifier.verify_solution_against_instance(instance, solver_solution, instance_size, False):
            logger.warning('Solver {} yields a wrong solution at instance size {}!'.format(self.solving_team, instance_size))
            return 0.0
        else:
            approximation_ratio = self.problem.verifier.calculate_approximation_ratio(instance, instance_size, generator_solution, solver_solution)
            logger.info('Solver {} yields a valid solution with an approx. ratio of {} at instance size {}.'.format(self.solving_team, approximation_ratio, instance_size))
            return approximation_ratio

    @build_successful
    def _run_subprocess(self, run_command, input, timeout):
        """ Run a given command as a subprocess.

        Parameters:
        ----------
        run_command: list 
            The command that is to be executed.
        input: bytes
            Additional input for the subprocess, supplied to it via stdin.
        timeout: int
            The timeout for the subprocess in seconds.
        Returns:
        ----------
        any
            The output that the process returns, decoded by the problem parser.
        float
            Actual running time of the process.
        """
        start_time = timeit.default_timer()
        raw_output = None

        stderr = None
        if self.testing:
            stderr = subprocess.PIPE
        with subprocess.Popen(run_command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr) as p:
            try:
                raw_output, _ = p.communicate(input=input, timeout=timeout)
                raw_output = self.problem.parser.decode(raw_output)
            except:
                p.kill()
                p.wait()
                sigh._kill_spawned_docker_containers()
            
        elapsed_time = round(timeit.default_timer() - start_time, 2)

        return raw_output, elapsed_time