"""Module defining how a match is run."""
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from itertools import combinations
from pathlib import Path
import tomllib
from typing import Annotated, Self, cast, overload

from pydantic import Field
from anyio import create_task_group, CapacityLimiter
from anyio.to_thread import current_default_thread_limiter

from algobattle.battle import Battle, FightHandler, FightUi, BattleUi, Iterated
from algobattle.config import AlgobattleConfigBase
from algobattle.program import ProgramUi
from algobattle.team import BuildUi, Matchup, Team, TeamHandler
from algobattle.problem import InstanceT, Problem, SolutionT
from algobattle.util import (
    ExceptionInfo,
    Role,
    RunningTimer,
    BaseModel,
    str_with_traceback,
)


# need to define this here so we don't cause import cycles
class AlgobattleConfig(AlgobattleConfigBase):   # noqa: D101

    battle: Battle.Config = Iterated.Config()

    @classmethod
    def from_file(cls, file: Path) -> Self:
        """Parses a config object from a toml file.

        If the file doesn't exist it returns a default instance instead of raising an error.
        """
        if not file.is_file():
            config_dict = {}
        else:
            with open(file, "rb") as f:
                try:
                    config_dict = tomllib.load(f)
                except tomllib.TOMLDecodeError as e:
                    raise ValueError(f"The config file at {file} is not a properly formatted TOML file!\n{e}")
        Battle.load_entrypoints()
        return cls.model_validate(config_dict, context={"base_path": file.parent})


class Match(BaseModel):
    """The Result of a whole Match."""

    active_teams: list[str]
    excluded_teams: dict[str, ExceptionInfo]
    results: defaultdict[str, Annotated[dict[str, Battle], Field(default_factory=dict)]] = Field(
        default_factory=lambda: defaultdict(dict)
    )

    async def _run_battle(
        self,
        battle: Battle,
        matchup: Matchup,
        config: AlgobattleConfig,
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

    @classmethod
    async def run(
        cls,
        config: AlgobattleConfig,
        problem: Problem[InstanceT, SolutionT],
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
            A :class:`Match` object with its fields populated to reflect the result of the match.
        """
        if ui is None:
            ui = Ui()

        with await TeamHandler.build(
            config.teams, problem, config.execution.mode, config.match, config.docker, ui
        ) as teams:
            result = cls(
                active_teams=[t.name for t in teams.active],
                excluded_teams=teams.excluded,
            )
            ui.match = result
            battle_cls = Battle.all()[config.battle.type]
            limiter = CapacityLimiter(config.execution.parallel_battles)
            current_default_thread_limiter().total_tokens = config.execution.parallel_battles
            set_cpus = config.execution.set_cpus
            if isinstance(set_cpus, list):
                match_cpus = cast(list[str | None], set_cpus[: config.execution.parallel_battles])
            else:
                match_cpus = [set_cpus] * config.execution.parallel_battles
            async with create_task_group() as tg:
                for matchup in teams.matchups:
                    battle = battle_cls()
                    result.results[matchup.generator.name][matchup.solver.name] = battle
                    tg.start_soon(result._run_battle, battle, matchup, config, problem, match_cpus, ui, limiter)
                return result

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


@dataclass
class Ui(BuildUi):
    """Base class for a UI that observes a Match and displays its data.

    The Ui object both observes the match object as it's being built and receives additional updates through
    method calls. To do this, it provides several objects whose methods are essentially curried versions of
    its own methods. These observer classes should generally not be subclassed, all Ui functionality can be implemented
    by just subclassing :class:`Ui` and implementing its methods.
    """

    match: Match | None = field(default=None, init=False)
    active_battles: list[Matchup] = field(default_factory=list, init=False)

    def start_build(self, team: str, role: Role, timeout: float | None) -> None:
        """Informs the ui that a new program is being built."""
        return

    def finish_build(self) -> None:
        """Informs the ui that the current build has been finished."""
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
class BattleObserver(BattleUi, FightUi, ProgramUi):
    """Tracks updates for a specific battle."""

    ui: Ui
    matchup: Matchup

    def update_battle_data(self, data: Battle.UiData) -> None:  # noqa: D102
        self.ui.update_battle_data(self.matchup, data)

    def start_fight(self, max_size: int) -> None:  # noqa: D102
        self.ui.start_fight(self.matchup, max_size)

    def end_fight(self) -> None:  # noqa: D102
        self.ui.update_fights(self.matchup)

    def start_program(self, role: Role, timeout: float | None) -> None:  # noqa: D102
        self.ui.start_program(self.matchup, role, RunningTimer(datetime.now(), timeout))

    def stop_program(self, role: Role, runtime: float) -> None:  # noqa: D102
        self.ui.end_program(self.matchup, role, runtime)
