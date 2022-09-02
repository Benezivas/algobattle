"""Class managing the execution of generators and solvers."""
import logging
from configparser import ConfigParser
from typing import Callable, Tuple
from algobattle.docker import DockerError

from algobattle.team import Team
from algobattle.problem import Problem

logger = logging.getLogger('algobattle.fight_handler')


class FightHandler():
    """Class managing the execution of generators and solvers."""

    generating_team = None
    solving_team = None

    def __init__(self, problem: Problem, config: ConfigParser, runtime_overhead: float = 0) -> None:
        self.timeout_generator = int(config['run_parameters']['timeout_generator']) + runtime_overhead
        self.timeout_solver    = int(config['run_parameters']['timeout_solver']) + runtime_overhead
        self.space_generator   = int(config['run_parameters']['space_generator'])
        self.space_solver      = int(config['run_parameters']['space_solver'])
        self.cpus              = int(config['run_parameters']['cpus'])

        self.problem = problem

        self.base_run_command = lambda a: [
            "docker",
            "run",
            "--rm",
            "--network", "none",
            "-i",
            "--memory=" + str(a) + "mb",
            "--cpus=" + str(self.cpus)
        ]

    def set_roles(self, generating: Team, solving: Team) -> None:
        """Update the roles for a fight.

        Parameters
        ----------
        generating : Team
            Team running its generator.
        solving : Team
            Team running its solver.
        """
        self.generating_team = generating
        self.solving_team = solving

    def team_roles_set(function: Callable) -> Callable:
        """Ensure that internal methods are only callable after the team roles have been set."""
        def wrapper(self, *args, **kwargs):
            if not self.generating_team or not self.solving_team:
                logger.error('Generating or solving team have not been set!')
                return None
            else:
                return function(self, *args, **kwargs)
        return wrapper

    @team_roles_set
    def fight(self, instance_size: int) -> float:
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

        logger.debug('Running generator of group {}...\n'.format(self.generating_team))

        try:
            assert(self.generating_team is not None)
            encoded_output = self.generating_team.generator.run(str(instance_size), self.timeout_generator, scaled_memory, self.cpus)
        except DockerError:
            logger.warning(f"No output was generated when running the generator group {self.generating_team}!")
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
        try:
            assert(self.solving_team is not None)
            encoded_output = self.solving_team.solver.run(self.problem.parser.encode(instance), self.timeout_solver, scaled_memory, self.cpus)
        except DockerError:
            logger.warning(f"No output was generated when running the solver of group {self.solving_team}!")
            return None

        raw_solver_solution = self.problem.parser.decode(encoded_output)

        logger.debug('Checking validity of the solvers solution...')

        solver_solution = self.problem.parser.parse_solution(raw_solver_solution, instance_size)
        if not self.problem.verifier.verify_semantics_of_solution(solver_solution, instance_size, True):
            logger.warning('Solver of group {} created a malformed solution at instance size {}!'
                           .format(self.solving_team, instance_size))
            return None
        elif not self.problem.verifier.verify_solution_against_instance(instance, solver_solution, instance_size, False):
            logger.warning('Solver of group {} yields an incorrect solution at instance size {}!'
                           .format(self.solving_team, instance_size))
            return None

        return solver_solution
