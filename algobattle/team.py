"""Team class, stores necessary information about a Team, such as their associated solver and generator."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from algobattle.docker_util import DockerError, Image, ArchivedImage

_team_names: set[str] = set()


@dataclass
class TeamInfo:
    """Object containing all the info needed to build a team."""

    name: str
    generator: Path
    solver: Path

    def build(self, timeout: float | None = None) -> Team:
        """Builds the specified docker files into images and return the corresponding team.

        Raises
        ------
        ValueError
            If the team name is already in use.
        DockerError
            If the docker build fails for some reason
        """

        name = self.name.replace(" ", "_").lower()  # Lower case needed for docker tag created from name
        if name in _team_names:
            raise
        generator = Image.build(self.generator, f"generator-{self}", f"generator for team {self}", timeout=timeout)
        try:
            solver = Image.build(self.solver, f"solver-{self}", f"solver for team {self}", timeout)
        except DockerError:
            generator.remove()
            raise
        _team_names.add(name)
        return Team(name, generator, solver, _cleanup_generator=True, _cleanup_solver=True)


@dataclass
class Team:
    """Team class responsible for holding basic information of a specific team."""

    name: str
    generator: Image
    solver: Image
    _cleanup_generator: bool = False
    _cleanup_solver: bool = False

    def __post_init__(self) -> None:
        """Creates a team object.

        Raises
        ------
        ValueError
            If the team name is already in use.
        """
        super().__init__()
        self.name = self.name.replace(" ", "_").lower()  # Lower case needed for docker tag created from name
        if self.name in _team_names:
            raise ValueError
        _team_names.add(self.name)

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
        if self._cleanup_generator:
            self.generator.remove()
        if self._cleanup_solver:
            self.solver.remove()
        _team_names.remove(self.name)

    def archive(self) -> ArchivedTeam:
        """Archives the images this team uses."""
        gen = self.generator.archive()
        sol = self.solver.archive()
        _team_names.discard(self.name)
        return ArchivedTeam(self.name, gen, sol, _cleanup_generator=self._cleanup_generator, _cleanup_solver=self._cleanup_solver)


@dataclass
class ArchivedTeam:
    """A team whose images have been archived."""
    name: str
    generator: ArchivedImage
    solver: ArchivedImage
    _cleanup_generator: bool = False
    _cleanup_solver: bool = False

    def __post_init__(self) -> None:
        """Creates a team object.

        Raises
        ------
        ValueError
            If the team name is already in use.
        """
        super().__init__()
        self.name = self.name.replace(" ", "_").lower()  # Lower case needed for docker tag created from name
        if self.name in _team_names:
            raise ValueError
        _team_names.add(self.name)

    def restore(self) -> Team:
        gen = self.generator.restore()
        sol = self.generator.restore()
        _team_names.discard(self.name)
        return Team(self.name, gen, sol, _cleanup_generator=self._cleanup_generator, _cleanup_solver=self._cleanup_solver)


@dataclass(frozen=True)
class Matchup:
    """Represents an individual matchup of teams."""

    generator: Team
    solver: Team

    def __iter__(self) -> Iterator[Team]:
        yield self.generator
        yield self.solver
