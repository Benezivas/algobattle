"""Module containing helper classes related to teams."""
from abc import abstractmethod
from dataclasses import dataclass, field
from itertools import combinations
from typing import Annotated, Any, Iterable, Iterator, Protocol, Self, TypeAlias

from pydantic import BaseModel, Field

from algobattle.program import DockerConfig, Generator, Solver
from algobattle.problem import AnyProblem
from algobattle.util import ExceptionInfo, MatchConfigBase, MatchMode, RelativePath, Role


_team_names: set[str] = set()


class BuildUi(Protocol):
    """Provides and interface for the build process to update the ui."""

    @abstractmethod
    def start_build_step(self, teams: Iterable[str], timeout: float | None) -> None:
        """Tells the ui that the build process has started."""

    @abstractmethod
    def start_build(self, team: str, role: Role) -> None:
        """Informs the ui that a new program is being built."""

    @abstractmethod
    def finish_build(self, team: str, success: bool) -> None:
        """Informs the ui that the current build has been finished."""


class TeamInfo(BaseModel):
    """The config parameters defining a team."""

    generator: RelativePath
    solver: RelativePath

    async def build(
        self,
        name: str,
        problem: AnyProblem,
        match_config: MatchConfigBase,
        docker_config: DockerConfig,
        name_programs: bool,
        ui: BuildUi,
    ) -> "Team":
        """Builds the specified docker files into images and return the corresponding team.

        Args:
            name: Name of the team.
            problem: The problem class the current match is fought over.
            match_config: Config for the current match.
            docker_config: Advanced docker settings for the current match.
            name_programs: Whether the programs should be given deterministic names.

        Returns:
            The built team.

        Raises:
            ValueError: If the team name is already in use.
            DockerError: If the docker build fails for some reason
        """
        if name in _team_names:
            raise ValueError
        tag_name = name.lower().replace(" ", "_") if name_programs else None
        ui.start_build(name, Role.generator)
        generator = await Generator.build(
            path=self.generator,
            problem=problem,
            docker_config=docker_config,
            timeout=match_config.build_timeout,
            strict_timeouts=match_config.strict_timeouts,
            config=match_config.generator,
            max_size=match_config.image_size,
            team_name=tag_name,
        )
        try:
            ui.start_build(name, Role.solver)
            solver = await Solver.build(
                path=self.solver,
                problem=problem,
                docker_config=docker_config,
                timeout=match_config.build_timeout,
                strict_timeouts=match_config.strict_timeouts,
                config=match_config.solver,
                max_size=match_config.image_size,
                team_name=tag_name,
            )
        except Exception:
            generator.remove()
            raise
        return Team(name, generator, solver)


TeamInfos: TypeAlias = Annotated[dict[str, TeamInfo], Field(validate_default=True)]


@dataclass
class Team:
    """Team class responsible for holding basic information of a specific team."""

    name: str
    generator: Generator
    solver: Solver

    def __post_init__(self) -> None:
        """Creates a team object.

        Raises:
            ValueError: If the team name is already in use.
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

    def __exit__(self, _type: Any, _value: Any, _traceback: Any):
        self.cleanup()

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

    def __repr__(self) -> str:
        return f"Matchup({self.generator.name}, {self.solver.name})"

    def __str__(self) -> str:
        return f"{self.generator.name} vs {self.solver.name}"


@dataclass
class TeamHandler:
    """Handles building teams and cleaning them up."""

    active: list[Team] = field(default_factory=list)
    excluded: dict[str, ExceptionInfo] = field(default_factory=dict)
    cleanup: bool = True

    @classmethod
    async def build(
        cls,
        infos: TeamInfos,
        problem: AnyProblem,
        mode: MatchMode,
        match_config: MatchConfigBase,
        docker_config: DockerConfig,
        ui: BuildUi,
    ) -> Self:
        """Builds the programs of every team.

        Attempts to build the programs of every team. If any build fails, that team will be excluded and all its
        programs cleaned up.

        Args:
            infos: Teams that participate in the match.
            problem: Problem class that the match will be fought with.
            mode: Mode of the current match.
            config: Config options.

        Returns:
            :class:`TeamHandler` containing the info about the participating teams.
        """
        handler = cls(cleanup=mode == "tournament")
        ui.start_build_step(infos.keys(), match_config.build_timeout)
        for name, info in infos.items():
            try:
                team = await info.build(name, problem, match_config, docker_config, mode == "testing", ui)
                handler.active.append(team)
            except Exception as e:
                handler.excluded[name] = ExceptionInfo.from_exception(e)
                ui.finish_build(name, False)
            else:
                ui.finish_build(name, True)
        return handler

    def __enter__(self) -> Self:
        return self

    def __exit__(self, _type: Any, _value: Any, _traceback: Any):
        if self.cleanup:
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
