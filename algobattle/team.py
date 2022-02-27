"""Team class, stores necessary information about a Team, such as their associated solver and generator."""
from __future__ import annotations
from pathlib import Path
from algobattle.docker import Image

_team_names: set[str] = set()

class Team:
    """Team class responsible for holding basic information of a specific team."""

    def __init__(self, team_name: str, generator_path: Path, solver_path: Path, timeout_build: float | None = None, cache_container: bool = True) -> None:
        if team_name in _team_names:
            raise ValueError
        _team_names.add(team_name)
        self.name = team_name.replace(' ', '_').lower()  # Lower case needed for docker tag created from name
        self.generator_path = generator_path
        self.solver_path = solver_path
        self.generator = Image(generator_path, f"generator-{self}", f"generator for team {self}", timeout=timeout_build, cache=cache_container)
        self.solver = Image(solver_path, f"solver-{self}", f"solver for team {self}", timeout_build, cache=cache_container)

    def __str__(self) -> str:
        return self.name
    
    def __eq__(self, o: object) -> bool:
        if isinstance(o, Team):
            return self.name == o.name
        else:
            return False
    
    def __hash__(self) -> int:
        return hash(self.name)
    
    def cleanup(self) -> None:
        self.generator.remove()
        self.solver.remove()
        _team_names.remove(self.name)
