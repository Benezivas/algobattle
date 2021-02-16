import sys
import subprocess
import signal
import timeit
import logging

logger = logging.getLogger('algobattle.framework')

class Match:
    """ Match class, responsible for setting up and executing the battles
    between two given teams. 
    """
    def __init__(self, problem, config, generator1_path, generator2_path, solver1_path, solver2_path, group_nr_one, group_nr_two, runtime_overhead=0, approximation_ratio=1.0, approximation_instance_size=10, approximation_iterations=50):
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

        self.latest_running_docker_image = ""

        def signal_handler(sig, frame):
                print('You pressed Ctrl+C!')
                self._kill_spawned_docker_containers()
                logger.info('Received SIGINT.')
                sys.exit(0)
        signal.signal(signal.SIGINT, signal_handler)

        self.build_successful = self._build(generator1_path, generator2_path, solver1_path, solver2_path, group_nr_one, group_nr_two)

        self.base_build_command = [
            "docker",
            "run",
            "--rm",
            "--network", "none",
            "-i",
            "--memory=" + str(self.space_solver) + "mb",
            "--cpus=" + str(self.cpus)
        ]

    def _build(self, generator1_path, generator2_path, solver1_path, solver2_path, group_nr_one, group_nr_two):
        """Builds docker containers for the given generators and solvers.
        
        Parameters:
        ----------
        generator1_path: str
            Path to the generator of the first team.
        generator1_path: str
            Path to the generator of the second team.
        solver1_path: str
            Path to the solver of the first team.
        solver2_path: str
            Path to the solver of the second team.
        group_nr_one: int
            Group number of the first team.
        group_nr_two: int
            Group number of the second team.
        Returns:
        ----------
        Bool:
            Boolean indicating whether the build process succeeded.
        """
        docker_build_base = [
            "docker",
            "build",
            "--network=host",
            "-t"
        ]
        self.teamA = group_nr_one
        self.teamB = group_nr_two

        build_commands = []
        build_commands.append(docker_build_base + ["solver"+str(group_nr_one), solver1_path])
        build_commands.append(docker_build_base + ["solver"+str(group_nr_two), solver2_path])
        build_commands.append(docker_build_base + ["generator"+str(group_nr_one), generator1_path])
        build_commands.append(docker_build_base + ["generator"+str(group_nr_two), generator2_path])

        success = True
        for command in build_commands:
            logger.debug('Building docker container with the following command: {}'.format(command))
            process = subprocess.Popen(command, stdout=subprocess.PIPE)
            try:
                output, _ = process.communicate(timeout=self.timeout_build)
                logger.debug(output.decode())
            except subprocess.TimeoutExpired as e:
                process.kill()
                success = False
                logger.error('Build process for {} ran into a timeout!'.format(command[5]))
            if process.returncode != 0:
                process.kill()
                success = False
                logger.error('Build process for {} failed!'.format(command[5]))

        return success

    def _kill_spawned_docker_containers(self):
        """Terminates all running docker containers spawned by this program."""
        if self.latest_running_docker_image:
            subprocess.run('docker ps -a -q --filter ancestor={} | xargs -r docker kill > /dev/null 2>&1'.format(self.latest_running_docker_image), shell=True)

    def run(self, battle_type='iterated', iterations=5):
        """ Match entry point. Executes iterations fights between two teams and
        returns the results of the battles.

        Parameters:
        ----------
        battle_type: str
            Type of battle that is to be run.
        iterations: int
            Number of Battles between teamA and teamB.
        Returns:
        ----------
        (list, list) 
            The lists contain the results of the battles for each team.
        """
        results_A = []
        results_B = []

        battle_wrapper = None

        if battle_type == 'iterated':
            battle_wrapper = self._iterated_battle_wrapper
        elif battle_type == 'averaged':
            battle_wrapper = self._averaged_battle_wrapper
        else:
            logger.critical('Unrecognized battle_type given: "{}"'.format(battle_type))
            return [], [], [], []

        for i in range(iterations):
            logger.info('{}  Running Battle {}/{}  {}'.format('#'*20, i+1,iterations, '#'*20))

            result = battle_wrapper(self.teamB, self.teamA)
            results_A.append(result)

            result = battle_wrapper(self.teamA, self.teamB)
            results_B.append(result)

        return results_A, results_B


    def _averaged_battle_wrapper(self, generating_team, solving_team):
        """ Wrapper to execute one averaged battle between a generating
        and a solving team.

        Execute several fights between two teams on a fixed instance size
        and determine the average solution quality. 
        
        Parameters:
        ----------
        generating_team: int
            Group number of the generating team, expected to be a positive int.
        solving_team: int
            Group number of the solving team, expected to be a positive int.
        Returns:
        ----------
        list
            Returns a list of the computed approximation ratios.
        """
        approximation_ratios = []
        logger.info('==================== Averaged Battle, Instance Size: {}, Iterations: {} ===================='.format(self.approximation_instance_size, self.aproximation_iterations))
        for i in range(self.aproximation_iterations):
            logger.info('=============== Iteration: {}/{} ==============='.format(i+1,self.aproximation_iterations))
            approx_ratio = self._one_fight(self.approximation_instance_size, generating_team, solving_team)
            approximation_ratios.append(approx_ratio)

        return approximation_ratios

    def _iterated_battle_wrapper(self, generating_team, solving_team):
        """ Wrapper to execute one iterative battle between a generating 
        and a solving team.

        Incrementally try to search for the highest n for which the solver
        is still able to solve instances.  The base increment value is
        multiplied with the square of the iterations since the last
        unsolvable instance.  Only once the solver fails after the
        multiplier is reset, it counts as failed. Since this would heavily
        favour probabilistic algorithms (That may have only failed by chance
        and are able to solve a certain instance size on a second try), we
        cap the maximum solution size by the first value that an algorithm
        has failed on.

        The wrapper automatically ends the battle and declares the solver
        as the winner once the iteration cap is reached, which is set
        in the config.ini.

        Parameters:
        ----------
        generating_team: int
            Group number of the generating team, expected to be a positive int.
        solving_team: int
            Group number of the solving team, expected to be a positive int.
        Returns:
        ----------
        int
            Returns the biggest instance size for which the solving team still found a solution.
        """
        n = self.problem.n_start
        maximum_reached_n = 0
        i = 0
        n_cap = 50000
        alive = True

        logger.info('==================== Iterative Battle, Instanze Size Cap: {} ===================='.format(n_cap))
        while alive:
            logger.info('=============== Instance Size: {}/{} ==============='.format(n,n_cap))
            approx_ratio = self._one_fight(n, generating_team, solving_team)
            if approx_ratio == 0.0:
                alive = False
            elif approx_ratio > self.approximation_ratio:
                logger.info('Solver {} does not meet the required solution quality at instance size {}. ({}/{})'.format(solving_team, n, approx_ratio, self.approximation_ratio))
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
                logger.info('Solver {} exceeded the instance size cap of {}!'.format(solving_team, self.iteration_cap))
                maximum_reached_n = self.iteration_cap
                alive = False
        return maximum_reached_n


    def _one_fight(self, size, generating_team, solving_team):
        """Executes a single fight of a battle between a given generator and
        solver for a given instance size.

        Parameters:
        ----------
        size: int 
            The instance size.
        generating_team: int
            The group number of the generating team, expected to be nonnegative ints.  
        solving_team: int
            The group number of the solving team, expected to be nonnegative ints.
        Returns:
        ----------
        float
            Returns the approximation ratio of the solver against 
            the generator (1 if optimal, 0 if failed, >1 if the 
            generator solution is optimal). 
        """
        if not str(generating_team).isdigit() or not str(solving_team).isdigit():
            logger.error('Solving and generating team are expected to be nonnegative ints, received "{}" and "{}".'.format(generating_team, solving_team))
            raise Exception('Solving and generating team are expected to be nonnegative ints!')
        elif not generating_team >= 0 or not solving_team >= 0:
            logger.error('Solving and generating team are expected to be nonnegative ints, received "{}" and "{}".'.format(generating_team, solving_team))
            raise Exception('Solving and generating team are expected to be nonnegative ints!')
        
        generator_run_command = self.base_build_command + ["generator" + str(generating_team)]
        solver_run_command    = self.base_build_command + ["solver"    + str(solving_team)]

        logger.info('Running generator of group {}...\n'.format(generating_team))

        self.latest_running_docker_image = "generator" + str(generating_team)
        raw_instance_with_solution, elapsed_time = self._run_subprocess(generator_run_command, str(size).encode(), self.timeout_generator)
        logger.info('Approximate elapsed runtime: {}/{} seconds.'.format(elapsed_time, self.timeout_generator))
        if not raw_instance_with_solution and elapsed_time > self.timeout_generator:
            logger.warning('Generator {} exceeded the given time limit at instance size {}!'.format(generating_team, size))
            return 1.0
        elif not raw_instance_with_solution:
            logger.warning('Generator {} threw an exception at instance size {}!'.format(generating_team, size))
            return 1.0

        logger.info('Checking generated instance and certificate...')

        raw_instance, raw_solution = self.problem.parser.split_into_instance_and_solution(raw_instance_with_solution)
        instance                   = self.problem.parser.parse_instance(raw_instance, size)
        generator_solution         = self.problem.parser.parse_solution(raw_solution, size)

        if not self.problem.verifier.verify_semantics_of_instance(instance, size):
            logger.warning('Generator {} created a malformed instance at instance size {}!'.format(generating_team, size))
            return 1.0

        if not self.problem.verifier.verify_semantics_of_solution(instance, generator_solution, size, True):
            logger.warning('Generator {} created a malformed solution at instance size {}!'.format(generating_team, size))
            return 1.0

        if not self.problem.verifier.verify_solution_against_instance(instance, generator_solution, size, True):
            logger.warning('Generator {} failed at instance size {} due to a wrong certificate for its generated instance!'.format(generating_team, size))
            return 1.0

        logger.info('Generated instance and certificate are valid!\n\n')



        logger.info('Running solver of group {}...\n'.format(solving_team))

        self.latest_running_docker_image = "solver" + str(solving_team)
        raw_solver_solution, elapsed_time = self._run_subprocess(solver_run_command, self.problem.parser.encode(instance), self.timeout_solver)
        logger.info('Approximate elapsed runtime: {}/{} seconds.'.format(elapsed_time, self.timeout_solver))
        if not raw_solver_solution and elapsed_time > self.timeout_generator:
            logger.warning('Solver {} exceeded the given time limit at instance size {}!'.format(solving_team, size))
            return 0.0
        elif not raw_instance_with_solution:
            logger.warning('Solver {} threw an exception at instance size {}!'.format(solving_team, size))
            return 0.0

        logger.info('Checking validity of the solvers solution...')
        
        solver_solution = self.problem.parser.parse_solution(raw_solver_solution, size)
        if not self.problem.verifier.verify_semantics_of_solution(instance, generator_solution, size, True):
            logger.warning('Solver {} created a malformed solution at instance size {}!'.format(generating_team, size))
            return 0.0
        elif not self.problem.verifier.verify_solution_against_instance(instance, solver_solution, size, False):
            logger.warning('Solver {} yields a wrong solution at instance size {}!'.format(solving_team, size))
            return 0.0
        else:
            approximation_ratio = self.problem.verifier.calculate_approximation_ratio(instance, size, generator_solution, solver_solution)
            logger.info('Solver {} yields a valid solution with an approx. ratio of {} at instance size {}.'.format(solving_team, approximation_ratio, size))
            return approximation_ratio

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
            The decoded output that the process returns.
        float
            Running time of the process.
        """

        p = subprocess.Popen(run_command, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        start_time = timeit.default_timer()
        raw_output = None
        try:
            raw_output, _ = p.communicate(input=input, timeout=timeout)
            raw_output = self.problem.parser.decode(raw_output)
        except:
            p.kill()
            self._kill_spawned_docker_containers()
        
        elapsed_time = '{:.2f}'.format(timeit.default_timer() - start_time)

        return raw_output, elapsed_time