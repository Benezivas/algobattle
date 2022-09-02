"""Team class, stores necessary information about a Team, such as their associated solver and generator."""
from __future__ import annotations
from pathlib import Path
from dataclasses import dataclass
from typing import Iterator
from itertools import permutations

from algobattle.docker import DockerError, Image

_team_names: set[str] = set()


class Team:
    """Team class responsible for holding basic information of a specific team."""

    def __init__(
        self,
        team_name: str,
        generator_path: Path,
        solver_path: Path,
        timeout_build: float | None = None,
        cache_image: bool = True,
    ) -> None:
        """Creates a team object and builds the necessary docker containers.

        Parameters
        ----------
        team_name : str
            Name of the team, must be globally unique!
        generator_path : Path
            Path to a folder containing a Dockerfile that will be used for the generator.
        solver_path : Path
            Path to a folder containing a Dockerfile that will be used for the solver.
        timeout_build : float | None
            Timeout for building the containers, `None` means they will have unlimited time, by default None.
        cache_container : bool, optional
            Wether docker should cache the built images, by default True.

        Raises
        ------
        ValueError
            _description_
        """
        team_name = team_name.replace(" ", "_").lower()  # Lower case needed for docker tag created from name
        if team_name in _team_names:
            raise ValueError
        self.name = team_name
        self.generator_path = generator_path
        self.solver_path = solver_path
        self.generator = Image(generator_path, f"generator-{self}", f"generator for team {self}",
                               timeout=timeout_build, cache=cache_image)
        try:
            self.solver = Image(solver_path, f"solver-{self}", f"solver for team {self}", timeout_build, cache=cache_image)
        except DockerError:
            self.generator.remove()
            raise
        _team_names.add(team_name)

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
        """Removes the built docker images."""
        self.generator.remove()
        self.solver.remove()
        _team_names.remove(self.name)


@dataclass(frozen=True)
class Matchup:
    """Represents an individual matchup of teams."""

    generator: Team
    solver: Team

    def __iter__(self) -> Iterator[Team]:
        yield self.generator
        yield self.solver


# not incredibly useful atm, but a layer of abstraction over a list of teams will be nice
class MatchupInfo:
    """All matchups that will be fought in a match and associated information."""

    def __init__(self, teams: list[Team]) -> None:
        self.teams = teams
        if len(self.teams) == 1:
            self._list = [Matchup(self.teams[0], self.teams[0])]
        else:
            self._list = [Matchup(*x) for x in permutations(self.teams, 2)]

    def __iter__(self) -> Iterator[Matchup]:
        return iter(self._list)

    def __getitem__(self, i: int) -> Matchup:
        return self._list[i]
