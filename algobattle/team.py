"""Team class, stores necessary information about a Team, such as their associated solver and generator."""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Iterator
import logging

from algobattle.docker_util import DockerError, Image, ArchivedImage

logger = logging.getLogger("algobattle.team")


_team_names: set[str] = set()


@dataclass
class TeamInfo:
    """Object containing all the info needed to build a team."""

    name: str
    generator: Path
    solver: Path

    def build(self, timeout: float | None = None, *, auto_cleanup=True) -> Team:
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
            raise ValueError
        generator = Image.build(self.generator, f"generator-{name}", f"generator for team {self}", timeout=timeout)
        try:
            solver = Image.build(self.solver, f"solver-{name}", f"solver for team {self}", timeout)
        except DockerError:
            generator.remove()
            raise
        return Team(name, generator, solver, _cleanup_generator=auto_cleanup, _cleanup_solver=auto_cleanup)


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

    def __enter__(self):
        return self

    def __exit__(self, _type, _value_, _traceback):
        self.cleanup()

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
        return ArchivedTeam(self.name, gen, sol, _cleanup_generator=self._cleanup_generator,
                            _cleanup_solver=self._cleanup_solver)


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
        """Restores the archived docker images."""
        gen = self.generator.restore()
        sol = self.solver.restore()
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


class TeamHandler(list[Team]):
    """Handles building teams and cleaning them up."""

    @staticmethod
    def build(infos: list[TeamInfo], timeout: float | None = None, safe_build: bool = False) -> TeamHandler:
        """Builds the specified team objects."""
        teams: list[Team | ArchivedTeam] = []
        for info in infos:
            try:
                team = info.build(timeout, auto_cleanup=safe_build)
                if safe_build:
                    team = team.archive()
                teams.append(team)
            except (ValueError, DockerError):
                logger.warning(f"Building generators and solvers for team {info.name} failed, they will be excluded!")
        restored_teams = [team.restore() if isinstance(team, ArchivedTeam) else team for team in teams]
        return TeamHandler(restored_teams)

    def __enter__(self):
        return self

    def __exit__(self, _type, _value_, _traceback):
        for team in self:
            team.cleanup()

    @property
    def grouped_matchups(self) -> list[tuple[Matchup, Matchup]]:
        """All matchups, grouped by the involved teams.

        Each tuple's first matchup has the first team in the group generating, the second has it solving.
        """
        return [(Matchup(*g), Matchup(*g[::-1])) for g in combinations(self, 2)]

    @property
    def matchups(self) -> list[Matchup]:
        """All matchups that will be fought."""
        if len(self) == 1:
            return [Matchup(self[0], self[0])]
        else:
            return [m for pair in self.grouped_matchups for m in pair]
