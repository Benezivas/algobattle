"""Match class, provides functionality for setting up and executing battles between given teams."""
from pathlib import Path
import subprocess
import os

import logging
import configparser
from typing import Callable, List, Tuple

import algobattle.sighandler as sigh
from algobattle.team import Team
from algobattle.problem import Problem
from algobattle.util import run_subprocess, update_nested_dict
from algobattle.subject import Subject
from algobattle.observer import Observer
from algobattle.battle_wrappers.averaged import Averaged
from algobattle.battle_wrappers.iterated import Iterated

logger = logging.getLogger('algobattle.match')


class Match(Subject):
    """Match class, provides functionality for setting up and executing battles between given teams."""

    _observers: List[Observer] = []
    generating_team = None
    solving_team = None
    battle_wrapper = None

    def __init__(self, problem: Problem, config_path: str, teams: list,
                 runtime_overhead=0, approximation_ratio=1.0, cache_docker_containers=True) -> None:

        config = configparser.ConfigParser()
        logger.debug('Using additional configuration options from file "%s".', config_path)
        config.read(config_path)

        self.timeout_build           = int(config['run_parameters']['timeout_build']) + runtime_overhead
        self.timeout_generator       = int(config['run_parameters']['timeout_generator']) + runtime_overhead
        self.timeout_solver          = int(config['run_parameters']['timeout_solver']) + runtime_overhead
        self.space_generator         = int(config['run_parameters']['space_generator'])
        self.space_solver            = int(config['run_parameters']['space_solver'])
        self.cpus                    = int(config['run_parameters']['cpus'])
        self.problem = problem
        self.config = config
        self.approximation_ratio = approximation_ratio

        self.build_successful = self._build(teams, cache_docker_containers)

        if approximation_ratio != 1.0 and not problem.approximable:
            logger.error('The given problem is not approximable and can only be run with an approximation ratio of 1.0!')
            self.build_successful = False

        self.generator_base_run_command = lambda a: [
            "docker",
            "run",
            "--rm",
            "--network", "none",
            "-i",
            "--memory=" + str(a) + "mb",
            "--cpus=" + str(self.cpus)
        ]

        self.solver_base_run_command = lambda a: [
            "docker",
            "run",
            "--rm",
            "--network", "none",
            "-i",
            "--memory=" + str(a) + "mb",
            "--cpus=" + str(self.cpus)
        ]

    def build_successful(function: Callable) -> Callable:
        """Ensure that internal methods are only callable after a successful build."""
        def wrapper(self, *args, **kwargs):
            if not self.build_successful:
                logger.error('Trying to call Match object which failed to build!')
                return None
            else:
                return function(self, *args, **kwargs)
        return wrapper

    def team_roles_set(function: Callable) -> Callable:
        """Ensure that internal methods are only callable after the team roles have been set."""
        def wrapper(self, *args, **kwargs):
            if not self.generating_team or not self.solving_team:
                logger.error('Generating or solving team have not been set!')
                return None
            else:
                return function(self, *args, **kwargs)
        return wrapper

    def docker_running(function: Callable) -> Callable:
        """Ensure that internal methods are only callable if docker is running."""
        def wrapper(self, *args, **kwargs):
            creationflags = 0
            if os.name != 'posix':
                creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
            docker_running = subprocess.Popen(['docker', 'info'], stdout=subprocess.PIPE,
                                              stderr=subprocess.PIPE, creationflags=creationflags)
            _ = docker_running.communicate()
            if docker_running.returncode:
                logger.error('Could not connect to the docker daemon. Is docker running?')
                return None
            else:
                return function(self, *args, **kwargs)
        return wrapper

    def attach(self, observer: Observer) -> None:
        """Subscribe a new Observer by adding them to the list of observers."""
        self._observers.append(observer)

    def detach(self, observer: Observer) -> None:
        """Unsubscribe an Observer by removing them from the list of observers."""
        self._observers.remove(observer)

    def notify(self) -> None:
        """Notify all subscribed Observers by calling their update() functions."""
        for observer in self._observers:
            observer.update(self)

    @build_successful
    def update_match_data(self, new_data: dict) -> bool:
        """Update the internal match dict with new (partial) information.

        Parameters
        ----------
        new_data : dict
            A dict in the same format as match_data that contains new information.
        """
        self.match_data = update_nested_dict(self.match_data, new_data)
        self.notify()
        return True

    @docker_running
    def _build(self, teams: list, cache_docker_containers=True) -> bool:
        """Build docker containers for the given generators and solvers of each team.

        Any team for which either the generator or solver does not build successfully
        will be removed from the match.

        Parameters
        ----------
        teams : list
            List of Team objects.
        cache_docker_containers : bool
            Flag indicating whether to cache built docker containers.

        Returns
        -------
        Bool
            Boolean indicating whether the build process succeeded.
        """
        base_build_command = [
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
        if len(self.team_names) != len(list(set(self.team_names))):
            logger.error('At least one team name is used twice!')
            return False

        self.single_player = (len(teams) == 1)

        image_archives: list[Path] = []
        for team in teams:
            build_commands = []
            build_commands.append(base_build_command + ["solver-" + str(team.name), team.solver_path])
            build_commands.append(base_build_command + ["generator-" + str(team.name), team.generator_path])

            build_successful = True
            for command in build_commands:
                logger.debug('Building docker container with the following command: {}'.format(command))
                creationflags = 0
                if os.name != 'posix':
                    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
                with subprocess.Popen(command, stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE, creationflags=creationflags) as process:
                    try:
                        output, _ = process.communicate(timeout=self.timeout_build)
                        logger.debug(output.decode())
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                        logger.error('Build process for {} ran into a timeout!'.format(command[5]))
                        build_successful = False
                    if process.returncode != 0:
                        process.kill()
                        process.wait()
                        logger.error('Build process for {} failed!'.format(command[5]))
                        build_successful = False
                if not build_successful:
                    logger.error("Removing team {} as their containers did not build successfully.".format(team.name))
                    self.team_names.remove(team.name)
                    if command[-2].startswith("generator"):
                        image_archives.pop().unlink()
                    break
                else:
                    path = command[-1].parent / f"{command[-2]}-archive.tar"
                    subprocess.Popen(["docker", "save", command[-2], "-o", path], stdout=subprocess.PIPE)
                    image_archives.append(path)
                    subprocess.Popen(["docker", "image", "rm", "-f", command[-2]])

        for path in image_archives:
            subprocess.Popen(["docker", "load", "-q", "-i", str(path)])
        return len(self.team_names) > 0

    @build_successful
    def all_battle_pairs(self) -> list:
        """Generate and return a list of all team pairings for battles."""
        battle_pairs = []
        for i in range(len(self.team_names)):
            for j in range(len(self.team_names)):
                battle_pairs.append((self.team_names[i], self.team_names[j]))

        if not self.single_player:
            battle_pairs = [pair for pair in battle_pairs if pair[0] != pair[1]]

        return battle_pairs

    @build_successful
    def run(self, battle_type: str = 'iterated', rounds: int = 5, iterated_cap: int = 50000, iterated_exponent: int = 2,
            approximation_instance_size: int = 10, approximation_iterations: int = 25) -> dict:
        """Match entry point, executes rounds fights between all teams and returns the results of the battles.

        Parameters
        ----------
        battle_type : str
            Type of battle that is to be run.
        rounds : int
            Number of Battles between each pair of teams (used for averaging results).
        iterated_cap : int
            Iteration cutoff after which an iterated battle is automatically stopped, declaring the solver as the winner.
        iterated_exponent : int
            Exponent used for increasing the step size in an iterated battle.
        approximation_instance_size : int
            Instance size on which to run an averaged battle.
        approximation_iterations : int
            Number of iterations for an averaged battle between two teams.

        Returns
        -------
        dict
            A dictionary contains the current data of a match. You can subscribe
            to this data using the observable pattern implemented in the match object.
            If the 'error' key is set to something other than None, do not expect the
            data to be consistent.
            Contains the following keys:
            error: An error message as a str (default: None).
            problem: The name of a problem
            curr_pair: The pair of teams currently fighting.
            rounds: The number of rounds fought between each pair of teams.
            type: The battle_type, usually 'iterated' or 'averaged'.
            approx_inst_size: Assuming 'averaged' battle_type, the constant instanze size.
            approx_iters: Assuming 'averaged' battle_type, the number of iterations over which to average.
            For each pair (as 2-tuple), there is a nested dict with the following contents:
            curr_round: The current round of the battle between the two teams.
            Each round is a key itself with another nested dict with the following contents:
            cap: Assuming 'iterated' battle_type, the (updated) cap up to which to fight.
            solved: Assuming 'iterated' battle_type, the largest instance size for which a solution was found (so far).
            attempting: Assuming 'iterated' battle_type, the current instanze size for which a solution is sought.
            approx_ratios: Assuming 'averaged' battle_type, a list of the approximation ratios for each iteration.
        """
        self.match_data = dict()
        self.match_data['error'] = None
        self.match_data['problem'] = Problem.name
        self.match_data['curr_pair'] = None
        self.match_data['rounds'] = rounds
        self.match_data['type'] = battle_type
        self.match_data['approx_inst_size'] = approximation_instance_size
        self.match_data['approx_iters'] = approximation_iterations
        for pair in self.all_battle_pairs():
            self.match_data[pair] = dict()
            self.match_data[pair]['curr_round'] = 0
            for i in range(rounds):
                self.match_data[pair][i] = dict()
                self.match_data[pair][i]['cap'] = iterated_cap
                self.match_data[pair][i]['solved'] = 0
                self.match_data[pair][i]['attempting'] = 0
                self.match_data[pair][i]['approx_ratios'] = []

        options = dict()
        if battle_type == 'iterated':
            self.battle_wrapper = Iterated()
            options['exponent'] = iterated_exponent
        elif battle_type == 'averaged':
            self.battle_wrapper = Averaged()
        else:
            self.match_data['error'] = 'Unrecognized battle_type given: "{}"'.format(battle_type)
            logger.error(self.match_data['error'])
            return self.match_data

        for pair in self.all_battle_pairs():
            self.update_match_data({'curr_pair': pair})
            for i in range(rounds):
                logger.info('{}  Running Battle {}/{}  {}'.format('#' * 20, i + 1, rounds, '#' * 20))
                self.update_match_data({pair: {'curr_round': i}})

                self.generating_team = pair[0]
                self.solving_team = pair[1]
                self.battle_wrapper.wrapper(self, options)

        return self.match_data

    @docker_running
    @build_successful
    @team_roles_set
    def _one_fight(self, instance_size: int) -> float:
        """Execute a single fight of a battle between a given generator and solver for a given instance size.

        Parameters
        ----------
        instance_size : int
            The instance size, expected to be a positive int.

        Returns
        -------
        float
            Returns the approximation ratio of the solver against
            the generator (1 if optimal, 0 if failed, >=1 if the
            generator solution is optimal).
        """
        instance, generator_solution = self._run_generator(instance_size)

        if not instance and not generator_solution:
            return 1.0

        solver_solution = self._run_solver(instance_size, instance)

        if not solver_solution:
            return 0.0

        approximation_ratio = self.problem.verifier.calculate_approximation_ratio(instance, instance_size,
                                                                                  generator_solution, solver_solution)
        logger.info('Solver of group {} yields a valid solution with an approx. ratio of {}.'
                    .format(self.solving_team, approximation_ratio))
        return approximation_ratio

    @docker_running
    @build_successful
    @team_roles_set
    def _run_generator(self, instance_size: int) -> Tuple[any, any]:
        """Execute the generator of match.generating_team and check the validity of the generated output.

        If the validity checks pass, return the instance and the certificate solution.

        Parameters
        ----------
        instance_size : int
            The instance size, expected to be a positive int.

        Returns
        -------
        any, any
            If the validity checks pass, the (instance, solution) in whatever
            format that is specified, else (None, None).
        """
        scaled_memory = self.problem.generator_memory_scaler(self.space_generator, instance_size)
        generator_run_command = self.generator_base_run_command(scaled_memory) + ["generator-" + str(self.generating_team)]

        logger.debug('Running generator of group {}...\n'.format(self.generating_team))

        sigh.latest_running_docker_image = "generator-" + str(self.generating_team)
        encoded_output, _ = run_subprocess(generator_run_command, str(instance_size).encode(),
                                           self.timeout_generator)
        if not encoded_output:
            logger.warning('No output was generated when running the generator group {}!'.format(self.generating_team))
            return None, None

        raw_instance_with_solution = self.problem.parser.decode(encoded_output)

        logger.debug('Checking generated instance and certificate...')

        raw_instance, raw_solution = self.problem.parser.split_into_instance_and_solution(raw_instance_with_solution)
        instance                   = self.problem.parser.parse_instance(raw_instance, instance_size)
        generator_solution         = self.problem.parser.parse_solution(raw_solution, instance_size)

        if not self.problem.verifier.verify_semantics_of_instance(instance, instance_size):
            logger.warning('Generator {} created a malformed instance!'.format(self.generating_team))
            return None, None

        if not self.problem.verifier.verify_semantics_of_solution(generator_solution, instance_size, True):
            logger.warning('Generator {} created a malformed solution at instance size!'.format(self.generating_team))
            return None, None

        if not self.problem.verifier.verify_solution_against_instance(instance, generator_solution, instance_size, True):
            logger.warning('Generator {} failed due to a wrong certificate for its generated instance!'
                           .format(self.generating_team))
            return None, None

        self.problem.parser.postprocess_instance(instance, instance_size)

        logger.info('Generated instance and certificate by group {} are valid!\n'.format(self.generating_team))

        return instance, generator_solution

    @docker_running
    @build_successful
    @team_roles_set
    def _run_solver(self, instance_size: int, instance: any) -> any:
        """Execute the solver of match.solving_team and check the validity of the generated output.

        If the validity checks pass, return the solver solution.

        Parameters
        ----------
        instance_size : int
            The instance size, expected to be a positive int.

        Returns
        -------
        any
            If the validity checks pass, solution in whatever
            format that is specified, else None.
        """
        scaled_memory = self.problem.solver_memory_scaler(self.space_solver, instance_size)
        solver_run_command = self.solver_base_run_command(scaled_memory) + ["solver-" + str(self.solving_team)]
        logger.debug('Running solver of group {}...\n'.format(self.solving_team))

        sigh.latest_running_docker_image = "solver-" + str(self.solving_team)
        encoded_output, _ = run_subprocess(solver_run_command, self.problem.parser.encode(instance),
                                           self.timeout_solver)
        if not encoded_output:
            logger.warning('No output was generated when running the solver of group {}!'.format(self.solving_team))
            return None

        raw_solver_solution = self.problem.parser.decode(encoded_output)

        logger.debug('Checking validity of the solvers solution...')

        solver_solution = self.problem.parser.parse_solution(raw_solver_solution, instance_size)
        if not self.problem.verifier.verify_semantics_of_solution(solver_solution, instance_size, True):
            logger.warning('Solver of group {} created a malformed solution at instance size {}!'
                           .format(self.solving_team, instance_size))
            return None
        elif not self.problem.verifier.verify_solution_against_instance(instance, solver_solution, instance_size, False):
            logger.warning('Solver of group {} yields a wrong solution at instance size {}!'
                           .format(self.solving_team, instance_size))
            return None

        return solver_solution
