"""Module defining how a match is run."""
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from itertools import combinations
from pathlib import Path
import tomllib
from typing import Annotated, Any, Iterable, Protocol, Self, cast, overload
from typing_extensions import override

from pydantic import Field
from anyio import create_task_group, CapacityLimiter
from anyio.to_thread import current_default_thread_limiter

from algobattle.battle import Battle, FightHandler, FightUi, BattleUi
from algobattle.program import DockerConfig, ProgramUi
from algobattle.team import BuildUi, Matchup, Team, TeamHandler, TeamInfos
from algobattle.problem import InstanceT, Problem, SolutionT
from algobattle.util import (
    ExceptionInfo,
    ExecutionConfig,
    MatchConfig,
    Role,
    RunningTimer,
    BaseModel,
    str_with_traceback,
)


class BaseConfig(BaseModel):
    """Base that contains all config options and can be parsed from config files."""

    # funky defaults to force their validation with context info present
    teams: TeamInfos = Field(default={"team_0": {"generator": Path("generator"), "solver": Path("solver")}})
    execution: ExecutionConfig = Field(default_factory=dict, validate_default=True)
    match: MatchConfig = Field(default_factory=dict, validate_default=True)
    battle: Battle.Config = Field(default={"type": "Iterated"}, validate_default=True)
    docker: DockerConfig = Field(default_factory=dict, validate_default=True)

    @classmethod
    def from_file(cls, source: Path) -> Self:
        """Parses a config object from a toml file."""
        if not source.exists():
            raise ValueError
        if source.is_dir():
            source /= "config.toml"
        if not source.is_file():
            config_dict = {}
        else:
            with open(source, "rb") as f:
                try:
                    config_dict = tomllib.load(f)
                except tomllib.TOMLDecodeError as e:
                    raise ValueError(f"The config file at {source} is not a properly formatted TOML file!\n{e}")
        Battle.load_entrypoints()
        return cls.model_validate(config_dict, context={"base_path": source.parent, "check_problem": True})


class Match(BaseModel):
    """The Result of a whole Match."""

    active_teams: list[str] = field(default_factory=list)
    excluded_teams: dict[str, ExceptionInfo] = field(default_factory=dict)
    results: defaultdict[str, Annotated[dict[str, Battle], Field(default_factory=dict)]] = Field(
        default_factory=lambda: defaultdict(dict)
    )

    async def _run_battle(
        self,
        battle: Battle,
        matchup: Matchup,
        config: BaseConfig,
        problem: Problem[InstanceT, SolutionT],
        cpus: list[str | None],
        ui: "Ui",
        limiter: CapacityLimiter,
    ) -> None:
        async with limiter:
            set_cpus = cpus.pop()
            ui.start_battle(matchup)
            battle_ui = BattleObserver(ui, matchup)
            handler = FightHandler(
                problem=problem,
                generator=matchup.generator.generator,
                solver=matchup.solver.solver,
                battle=battle,
                ui=battle_ui,
                set_cpus=set_cpus,
            )
            try:
                await battle.run_battle(
                    handler,
                    config.battle,
                    problem.min_size,
                    battle_ui,
                )
            except Exception as e:
                battle.run_exception = str_with_traceback(e)
            cpus.append(set_cpus)
            ui.battle_completed(matchup)

    async def run(
        self,
        config: BaseConfig,
        problem: Problem[InstanceT, SolutionT],
        ui: "Ui | None" = None,
    ) -> None:
        """Runs a match with the given config settings and problem type.

        The first step is building the docker images for each team in `config.teams`. Any teams where this process fails
        are excluded from the match and will receive zero points. Then each pair of teams will fight two battles against
        each other, one where the first is generating and the second is solving, and one where the roles are swapped.
        Since all of these battles are completely independent, you can set `config.parallel_battles` to have some number
        of them run in parallel. This will speed up the exection of the match, but can also make the match unfair if the
        hardware running it does not have the resources to adequately execute that many containers in parallel.
        """
        if ui is None:
            ui = EmptyUi()
        ui.match = self

        with await TeamHandler.build(
            config.teams, problem, config.execution.mode, config.match, config.docker, ui
        ) as teams:
            self.active_teams = [t.name for t in teams.active]
            self.excluded_teams = teams.excluded
            battle_cls = Battle.all()[config.battle.type]
            limiter = CapacityLimiter(config.execution.parallel_battles)
            current_default_thread_limiter().total_tokens = config.execution.parallel_battles
            set_cpus = config.execution.set_cpus
            if isinstance(set_cpus, list):
                match_cpus = cast(list[str | None], set_cpus[: config.execution.parallel_battles])
            else:
                match_cpus = [set_cpus] * config.execution.parallel_battles
            ui.start_battles()
            async with create_task_group() as tg:
                for matchup in teams.matchups:
                    battle = battle_cls()
                    self.results[matchup.generator.name][matchup.solver.name] = battle
                    tg.start_soon(self._run_battle, battle, matchup, config, problem, match_cpus, ui, limiter)

    @overload
    def battle(self, matchup: Matchup) -> Battle | None:
        ...

    @overload
    def battle(self, *, generating: Team, solving: Team) -> Battle | None:
        ...

    def battle(
        self,
        matchup: Matchup | None = None,
        *,
        generating: Team | None = None,
        solving: Team | None = None,
    ) -> Battle | None:
        """Helper method to look up the battle between a specific matchup.

        Returns:
            The battle if it has started already, otherwise `None`.
        """
        try:
            if matchup is not None:
                return self.results[matchup.generator.name][matchup.solver.name]
            if generating is not None and solving is not None:
                return self.results[generating.name][solving.name]
            raise TypeError
        except KeyError:
            return None

    @overload
    def insert_battle(self, battle: Battle, matchup: Matchup) -> None:
        ...

    @overload
    def insert_battle(self, battle: Battle, *, generating: Team, solving: Team) -> None:
        ...

    def insert_battle(
        self,
        battle: Battle,
        matchup: Matchup | None = None,
        *,
        generating: Team | None = None,
        solving: Team | None = None,
    ) -> None:
        """Helper method to insert a new battle for a specific matchup."""
        if matchup is not None:
            self.results[matchup.generator.name][matchup.solver.name] = battle
        elif generating is not None and solving is not None:
            self.results[generating.name][solving.name] = battle
        else:
            raise TypeError

    def calculate_points(self, total_points_per_team: int) -> dict[str, float]:
        """Calculate the number of points each team scored.

        Every team scores between 0 and `total_points_per_team` points.
        Excluded teams are considered to have lost all their battles and thus receive 0 points.
        The other teams each get points based on how well they did against each other team compared to how well that
        other team did against them.
        """
        points = {team: 0.0 for team in self.active_teams + list(self.excluded_teams)}
        if len(self.active_teams) == 0:
            return points
        if len(self.active_teams) == 1:
            points[self.active_teams[0]] = total_points_per_team
            return points

        points_per_matchup = round(total_points_per_team / (len(self.active_teams) - 1), 1)

        for first, second in combinations(self.active_teams, 2):
            try:
                first_res = self.results[second][first]
                second_res = self.results[first][second]
            except KeyError:
                continue
            total_score = max(0, first_res.score()) + max(0, second_res.score())
            if total_score == 0:
                # Default values for proportions, assuming no team manages to solve anything
                first_ratio = 0.5
                second_ratio = 0.5
            else:
                first_ratio = first_res.score() / total_score
                second_ratio = second_res.score() / total_score

            points[first] += round(points_per_matchup * first_ratio, 1)
            points[second] += round(points_per_matchup * second_ratio, 1)

        # we need to also add the points each team would have gotten fighting the excluded teams
        # each active team would have had one set of battles against each excluded team
        for team in self.active_teams:
            points[team] += points_per_matchup * len(self.excluded_teams)

        return points


class Ui(BuildUi, Protocol):
    """Base class for a UI that observes a Match and displays its data.

    The Ui object both observes the match object as it's being built and receives additional updates through
    method calls. To do this, it provides several objects whose methods are essentially curried versions of
    its own methods. These observer classes should generally not be subclassed, all Ui functionality can be implemented
    by just subclassing :class:`Ui` and implementing its methods.
    """

    match: Match | None

    def start_build_step(self, teams: Iterable[str], timeout: float | None) -> None:
        """Tells the ui that the build process has started."""
        return

    def start_build(self, team: str, role: Role) -> None:
        """Informs the ui that a new program is being built."""
        return

    def finish_build(self, team: str, success: bool) -> None:
        """Informs the ui that the current build has been finished."""
        return

    def start_battles(self) -> None:
        """Tells the UI that building the programs has finished and battles will start now."""
        return

    def start_battle(self, matchup: Matchup) -> None:
        """Notifies the Ui that a battle has been started."""
        return

    def battle_completed(self, matchup: Matchup) -> None:
        """Notifies the Ui that a specific battle has been completed."""
        return

    def update_battle_data(self, matchup: Matchup, data: Battle.UiData) -> None:
        """Passes new custom battle data to the Ui."""
        return

    def start_fight(self, matchup: Matchup, max_size: int) -> None:
        """Informs the Ui of a newly started fight."""
        return

    def end_fight(self, matchup: Matchup) -> None:
        """Informs the Ui that the current fight has finished."""
        return

    def start_program(
        self,
        matchup: Matchup,
        role: Role,
        data: RunningTimer,
    ) -> None:
        """Passes new info about programs in the current fight to the Ui."""
        return

    def end_program(self, matchup: Matchup, role: Role, runtime: float) -> None:
        """Informs the Ui that the currently running programmes has finished."""
        return


@dataclass
class EmptyUi(Ui):
    """A dummy Ui."""

    match: Match | None = field(default=None, init=False)

    def __enter__(self) -> Self:
        """Starts displaying the Ui."""
        return self

    def __exit__(self, *args: Any) -> None:
        """Stops the Ui."""
        return


@dataclass
class BattleObserver(BattleUi, FightUi, ProgramUi):
    """Tracks updates for a specific battle."""

    ui: Ui
    matchup: Matchup

    @override
    def update_battle_data(self, data: Battle.UiData) -> None:  # noqa: D102
        self.ui.update_battle_data(self.matchup, data)

    @override
    def start_fight(self, max_size: int) -> None:  # noqa: D102
        self.ui.start_fight(self.matchup, max_size)

    @override
    def end_fight(self) -> None:  # noqa: D102
        self.ui.end_fight(self.matchup)

    @override
    def start_program(self, role: Role, timeout: float | None) -> None:  # noqa: D102
        self.ui.start_program(self.matchup, role, RunningTimer(datetime.now(), timeout))

    @override
    def stop_program(self, role: Role, runtime: float) -> None:  # noqa: D102
        self.ui.end_program(self.matchup, role, runtime)
