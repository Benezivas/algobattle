"""Team class, stores necessary information about a Team, such as their associated solver and generator."""
from __future__ import annotations
from docker import Image

class Team:
    """Team class responsible for holding basic information of a specific team."""

    def __init__(self, team_name: str, generator_path: str, solver_path: str) -> None:
        self.name = str(team_name).replace(' ', '_').lower()  # Lower case needed for docker tag created from name
        self.generator_path = generator_path
        self.solver_path = solver_path
        self.generator: Image | None = None
        self.solver: Image | None = None

    def __str__(self) -> str:
        return self.name
    
    def __eq__(self, o: object) -> bool:
        if isinstance(o, Team):
            return self.name == o.name
        else:
            return False
    
    def __hash__(self) -> int:
        return hash(self.name)
