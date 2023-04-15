"""Team class, stores necessary information about a Team, such as their associated solver and generator."""
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Iterable, Iterator, Self

from algobattle.docker_util import DockerConfig, DockerError, ArchivedImage, Generator, Solver
from algobattle.problem import Problem
from algobattle.util import TempDir


_team_names: set[str] = set()


@dataclass
class TeamInfo:
    """The config parameters defining a team."""

    name: str
    generator: Path
    solver: Path

    def build(self, problem: type[Problem], config: DockerConfig) -> "Team":
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
        generator = Generator.build(self.generator, self.name, problem, config.generator, config.build_timeout)
        try:
            solver = Solver.build(self.solver, self.name, problem, config.solver, config.build_timeout)
        except Exception:
            generator.remove()
            raise
        return Team(name, generator, solver)


@dataclass
class Team:
    """Team class responsible for holding basic information of a specific team."""

    name: str
    generator: Generator
    solver: Solver

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
        self.generator.remove()
        self.solver.remove()
        _team_names.remove(self.name)

    def archive(self, dir: Path) -> "_ArchivedTeam":
        """Archives the images this team uses."""
        gen = self.generator.image.archive(dir)
        sol = self.solver.image.archive(dir)
        return _ArchivedTeam(gen, sol, self)


@dataclass
class _ArchivedTeam:
    """A team whose images have been archived."""

    generator: ArchivedImage
    solver: ArchivedImage
    team: Team

    def restore(self) -> Team:
        """Restores the archived docker images."""
        self.generator.restore()
        self.solver.restore()
        return self.team


@dataclass(frozen=True)
class Matchup:
    """Represents an individual matchup of teams."""

    generator: Team
    solver: Team

    def __iter__(self) -> Iterator[Team]:
        yield self.generator
        yield self.solver

    def __repr__(self) -> str:
        return f"Matchup({self.generator.name}, {self.solver.name})"


class TeamHandler:
    """Handles building teams and cleaning them up."""

    def __init__(self, teams: Iterable[Team] | None = None, excluded: Iterable[TeamInfo] | None = None) -> None:
        if teams is not None:
            self.active = list(teams)
        else:
            self.active = []
        if excluded is not None:
            self.excluded = list(excluded)
        else:
            self.excluded = []
        super().__init__()

    @classmethod
    def build(
        cls, infos: list[TeamInfo], problem: type[Problem], config: DockerConfig, safe_build: bool = False
    ) -> Self:
        """Builds the specified team objects."""
        excluded: list[TeamInfo] = []
        if safe_build:
            with TempDir() as folder:
                archives: list[_ArchivedTeam] = []
                for info in infos:
                    try:
                        team = info.build(problem, config)
                        team = team.archive(folder)
                        archives.append(team)
                    except Exception:
                        excluded.append(info)

                return cls([team.restore() for team in archives], excluded)
        else:
            teams: list[Team] = []
            for info in infos:
                try:
                    team = info.build(problem, config)
                    teams.append(team)
                except (ValueError, DockerError):
                    excluded.append(info)
            return cls(teams, excluded)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, _type, _value_, _traceback):
        for team in self.active:
            team.cleanup()

    @property
    def grouped_matchups(self) -> list[tuple[Matchup, Matchup]]:
        """All matchups, grouped by the involved teams.

        Each tuple's first matchup has the first team in the group generating, the second has it solving.
        """
        return [(Matchup(*g), Matchup(*g[::-1])) for g in combinations(self.active, 2)]

    @property
    def matchups(self) -> list[Matchup]:
        """All matchups that will be fought."""
        if len(self.active) == 1:
            return [Matchup(self.active[0], self.active[0])]
        else:
            return [m for pair in self.grouped_matchups for m in pair]
