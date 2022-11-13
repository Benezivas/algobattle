"""Team class, stores necessary information about a Team, such as their associated solver and generator."""
from __future__ import annotations
from pathlib import Path
from dataclasses import dataclass
from typing import Iterator

from algobattle.docker_util import DockerError, Image

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
        generator = Image(self.generator, f"generator-{self}", f"generator for team {self}", timeout=timeout)
        try:
            solver = Image(self.solver, f"solver-{self}", f"solver for team {self}", timeout)
        except DockerError:
            generator.remove()
            raise
        _team_names.add(name)
        return Team(name, generator, solver)



class Team:
    """Team class responsible for holding basic information of a specific team."""

    def __init__(
        self,
        team_name: str,
        generator: Path | Image,
        solver: Path | Image,
        timeout_build: float | None = None,
    ) -> None:
        """Creates a team object and builds the necessary docker containers.

        Parameters
        ----------
        team_name : str
            Name of the team, must be globally unique!
        generator_path : Path | Image
            Path to a folder containing a Dockerfile that will be used for the generator, or already built image.
        solver_path : Path | Image
            Path to a folder containing a Dockerfile that will be used for the solver, or already built image.
        timeout_build : float | None
            Timeout for building the containers, `None` means they will have unlimited time, by default None.

        Raises
        ------
        ValueError
            _description_
        """
        super().__init__()
        team_name = team_name.replace(" ", "_").lower()  # Lower case needed for docker tag created from name
        if team_name in _team_names:
            raise ValueError
        self.name = team_name
        built_generator = None
        try:
            self._built_generator = isinstance(generator, Path)
            if isinstance(generator, Path):
                self.generator = Image(generator, f"generator-{self}", f"generator for team {self}",
                                       timeout=timeout_build)
                built_generator = self.generator
            else:
                self.generator = generator
            self._built_solver = isinstance(solver, Path)
            if isinstance(solver, Path):
                self.solver = Image(solver, f"solver-{self}", f"solver for team {self}", timeout_build)
            else:
                self.solver = solver
        except DockerError:
            if built_generator is not None:
                built_generator.remove()
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
        if self._built_generator:
            self.generator.remove()
        if self._built_solver:
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
