"""Module defining how a match is run."""
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from itertools import combinations
from pathlib import Path
import tomllib
from typing import Mapping, Self, cast, overload

from pydantic import validator, Field
from anyio import create_task_group, CapacityLimiter
from anyio.to_thread import current_default_thread_limiter

from algobattle.battle import Battle, FightHandler, FightUiProxy, BattleUiProxy
from algobattle.docker_util import DockerConfig, Image, ProgramRunInfo, ProgramUiProxy
from algobattle.team import Matchup, Team, TeamHandler, TeamInfo
from algobattle.problem import Problem
from algobattle.util import Role, TimerInfo, inherit_docs, BaseModel, str_with_traceback


class MatchConfig(BaseModel):
    """Parameters determining the match execution."""

    battle_type: str = "Iterated"
    points: int = 100
    parallel_battles: int = 1
    teams: list[TeamInfo] = []
    docker: DockerConfig = DockerConfig()
    battle: dict[str, Battle.BattleConfig] = {n: b.BattleConfig() for n, b in Battle.all().items()}

    @validator("battle_type", pre=True)
    def validate_battle_type(cls, value):
        """Validates that the given battle type is a correct name of a battle class."""
        if value in Battle.all():
            return value
        else:
            raise ValueError

    @validator("battle", pre=True)
    def val_battle_configs(cls, vals):
        """Parses the dict of battle configs into their corresponding config objects."""
        battle_types = Battle.all()
        if not isinstance(vals, Mapping):
            raise TypeError
        out = {}
        for name, battle_cls in battle_types.items():
            data = vals.get(name, {})
            out[name] = battle_cls.BattleConfig.parse_obj(data)
        return out

    @validator("docker")
    def val_set_cpus(cls, v: DockerConfig, values) -> DockerConfig:
        """Validates that each battle that is being executed is assigned some cpu cores."""
        if isinstance(v.set_cpus, list) and values["parallel_battles"] > len(v.set_cpus):
            raise ValueError("Number of parallel battles exceeds the number of set_cpu specifier strings.")
        else:
            return v

    @classmethod
    def from_file(cls, file: Path) -> Self:
        """Parses a config object from a toml file."""
        if not file.is_file():
            raise ValueError("Path doesn't point to a file.")
        with open(file, "rb") as f:
            try:
                config_dict = tomllib.load(f)
            except tomllib.TOMLDecodeError as e:
                raise ValueError(f"The config file at {file} is not a properly formatted TOML file!\n{e}")
        return cls.parse_obj(config_dict)


class Match(BaseModel):
    """The Result of a whole Match."""

    active_teams: list[str]
    excluded_teams: list[str]
    results: defaultdict[str, dict[str, Battle]] = Field(default_factory=lambda: defaultdict(dict), init=False)

    async def _run_battle(
        self,
        battle: Battle,
        matchup: Matchup,
        config: Battle.BattleConfig,
        problem: type[Problem],
        cpus: list[str | None],
        ui: "Ui",
        limiter: CapacityLimiter,
    ) -> None:
        async with limiter:
            set_cpus = cpus.pop()
            ui.start_battle(matchup)
            battle_ui = ui.BattleObserver(ui, matchup)
            handler = FightHandler(
                matchup.generator.generator, matchup.solver.solver, battle, battle_ui.fight_ui, set_cpus
            )
            try:
                await battle.run_battle(
                    handler,
                    config,
                    problem.min_size,
                    battle_ui,
                )
            except Exception as e:
                battle.run_exception = str_with_traceback(e)
            cpus.append(set_cpus)
            ui.battle_completed(matchup)

    @classmethod
    async def run(
        cls,
        config: MatchConfig,
        problem: type[Problem],
        ui: "Ui | None" = None,
    ) -> Self:
        """Runs a match with the given config settings and problem type.

        The first step is building the docker images for each team in `config.teams`. Any teams where this process fails
        are excluded from the match and will receive zero points. Then each pair of teams will fight two battles against
        each other, one where the first is generating and the second is solving, and one where the roles are swapped.
        Since all of these battles are completely independent, you can set `config.parallel_battles` to have some number
        of them run in parallel. This will speed up the exection of the match, but can also make the match unfair if the
        hardware running it does not have the resources to adequately execute that many containers in parallel.

        Returns:
            A :cls:`Match` object with its fields populated to reflect the result of the match.
        """
        if ui is None:
            ui = Ui()
        if config.docker.advanced_run_params is not None:
            Image.run_kwargs = config.docker.advanced_run_params.to_docker_args()
        if config.docker.advanced_build_params is not None:
            Image.run_kwargs = config.docker.advanced_build_params.to_docker_args()

        with await TeamHandler.build(config.teams, problem, config.docker, ui) as teams:
            result = cls(
                active_teams=[t.name for t in teams.active],
                excluded_teams=[t for t in teams.excluded],
            )
            ui.match = result
            battle_cls = Battle.all()[config.battle_type]
            battle_config = config.battle[config.battle_type]
            limiter = CapacityLimiter(config.parallel_battles)
            current_default_thread_limiter().total_tokens = config.parallel_battles
            set_cpus = config.docker.set_cpus
            if isinstance(set_cpus, list):
                match_cpus = cast(list[str | None], set_cpus[: config.parallel_battles])
            else:
                match_cpus = [set_cpus] * config.parallel_battles
            async with create_task_group() as tg:
                for matchup in teams.matchups:
                    battle = battle_cls()
                    result.results[matchup.generator.name][matchup.solver.name] = battle
                    tg.start_soon(result._run_battle, battle, matchup, battle_config, problem, match_cpus, ui, limiter)
                return result

    @overload
    def battle(self, matchup: Matchup) -> Battle | None:
        ...

    @overload
    def battle(self, *, generating: Team, solving: Team) -> Battle | None:
        ...

    def battle(
        self, matchup: Matchup | None = None, *, generating: Team | None = None, solving: Team | None = None
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
        points = {team: 0.0 for team in self.active_teams + self.excluded_teams}
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


@dataclass
class Ui:
    """Base class for a UI that observes a Match and displays its data.

    The Ui object both observes the match object as it's being built and receives additional updates through
    method calls. To do this, it provides several objects whose methods are essentially curried versions of
    its own methods. These observer classes should generally not be subclassed, all Ui functionality can be implemented
    by just subclassing :cls:`Ui` and implementing its methods.
    """

    match: Match | None = field(default=None, init=False)
    active_battles: list[Matchup] = field(default_factory=list, init=False)

    def start_build(self, team: str, role: Role, timeout: float | None) -> None:
        """Informs the ui that a new program is being built."""
        return

    def finish_build(self) -> None:
        """Informs the ui that the current build has been finished."""
        return

    def initialize_programs(self) -> None:
        """Informs the ui that the programs are being initialized."""
        return

    def start_battle(self, matchup: Matchup) -> None:
        """Notifies the Ui that a battle has been started."""
        self.active_battles.append(matchup)

    def battle_completed(self, matchup: Matchup) -> None:
        """Notifies the Ui that a specific battle has been completed."""
        self.active_battles.remove(matchup)

    def update_fights(self, matchup: Matchup) -> None:
        """Notifies the Ui to update the display of fight results for a specific battle."""
        return

    def update_battle_data(self, matchup: Matchup, data: Battle.UiData) -> None:
        """Passes new custom battle data to the Ui."""
        return

    def start_fight(self, matchup: Matchup, size: int) -> None:
        """Informs the Ui of a newly started fight."""
        return

    def update_curr_fight(
        self,
        matchup: Matchup,
        role: Role | None = None,
        data: TimerInfo | float | ProgramRunInfo | None = None,
    ) -> None:
        """Passes new info about the current fight to the Ui."""
        return

    @dataclass
    class BattleObserver(BattleUiProxy):
        """Tracks updates for a specific battle."""

        ui: "Ui"
        matchup: Matchup
        fight_ui: "Ui.FightObserver" = field(init=False)

        def __post_init__(self) -> None:
            self.fight_ui = Ui.FightObserver(self)

        @inherit_docs
        def update_data(self, data: Battle.UiData) -> None:
            self.ui.update_battle_data(self.matchup, data)

    @dataclass
    class FightObserver(FightUiProxy):
        """Tracks updates for the currently executed fight of a battle."""

        battle_ui: "Ui.BattleObserver"
        generator: "Ui.ProgramObserver" = field(init=False)
        solver: "Ui.ProgramObserver" = field(init=False)

        def __post_init__(self) -> None:
            self.generator = Ui.ProgramObserver(self.battle_ui, "generator")
            self.solver = Ui.ProgramObserver(self.battle_ui, "solver")

        @inherit_docs
        def start(self, size: int) -> None:
            self.battle_ui.ui.start_fight(self.battle_ui.matchup, size)

        @inherit_docs
        def update(
            self,
            role: Role | None = None,
            data: TimerInfo | float | ProgramRunInfo | None = None,
        ) -> None:
            self.battle_ui.ui.update_curr_fight(self.battle_ui.matchup, role, data)

        @inherit_docs
        def end(self) -> None:
            self.battle_ui.ui.update_fights(self.battle_ui.matchup)

    @dataclass
    class ProgramObserver(ProgramUiProxy):
        """Tracks state of a specific program execution."""

        battle: "Ui.BattleObserver"
        role: Role

        @inherit_docs
        def start(self, timeout: float | None) -> None:
            self.battle.ui.update_curr_fight(self.battle.matchup, self.role, TimerInfo(datetime.now(), timeout))

        @inherit_docs
        def stop(self, runtime: float) -> None:
            self.battle.ui.update_curr_fight(self.battle.matchup, self.role, runtime)
