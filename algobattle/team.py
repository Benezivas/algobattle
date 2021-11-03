"""Team class, stores necessary information about a Team, such as their associated solver and generator."""


class Team:
    """Team class responsible for holding basic information of a specific team."""

    def __init__(self, team_name: str, generator_path: str, solver_path: str) -> None:
        self.name = str(team_name).replace(' ', '_')
        self.generator_path = generator_path
        self.solver_path = solver_path

    def __str__(self) -> str:
        return self.name
