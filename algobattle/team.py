"""Team class, stores necessary information about a Team, such as their associated solver and generator."""
import logging

logger = logging.getLogger('algobattle.team')


class Team:
    """Team class responsible for holding basic information of a specific team."""

    def __init__(self, team_name: str, generator_docker_tag: str, solver_docker_tag: str) -> None:
        self.name = str(team_name).replace(' ', '_').lower()  # Lower case needed for docker tag created from name
        self.generator_docker_tag = generator_docker_tag
        self.solver_docker_tag = solver_docker_tag

    def __str__(self) -> str:
        return self.name
