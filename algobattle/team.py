"""Team class, stores necessary information about a Team, such as their associated solver and generator."""
import logging
import subprocess
import os

from algobattle.util import docker_running

logger = logging.getLogger('algobattle.team')


class Team:
    """Team class responsible for holding basic information of a specific team."""

    def __init__(self, team_name: str, generator_path: str, solver_path: str, cache_docker_containers=True) -> None:
        self.name = str(team_name).replace(' ', '_').lower()  # Lower case needed for docker tag created from name
        self.generator_path = generator_path
        self.solver_path = solver_path

        self.build_containers(cache_docker_containers)

    def __str__(self) -> str:
        return self.name

    @docker_running
    def build_containers(self, cache_docker_containers=True) -> bool:
        """Build docker containers for the given generators and solvers of a team.

        Parameters
        ----------
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

        build_commands = []
        build_commands.append(base_build_command + ["solver-" + self.name, self.solver_path])
        build_commands.append(base_build_command + ["generator-" + self.name, self.generator_path])

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

        return build_successful
