"""Central managing module for an algorithmic battle."""
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from itertools import combinations
from typing import Self, overload

from pydantic import validator, Field
from anyio import create_task_group, CapacityLimiter, TASK_STATUS_IGNORED
from anyio.to_thread import current_default_thread_limiter
from anyio.abc import TaskStatus

from algobattle.battle import Battle, FightHandler, FightUiProxy, Iterated, BattleUiProxy
from algobattle.docker_util import ProgramRunInfo, ProgramUiProxy
from algobattle.team import Matchup, Team, TeamHandler
from algobattle.problem import Problem
from algobattle.util import Role, TimerInfo, inherit_docs, BaseModel, str_with_traceback


class MatchConfig(BaseModel):
    """Parameters determining the match execution."""

    battle_type: type[Battle] = Iterated
    points: int = 100
    parallel_battles: int = 1

    @validator("battle_type", pre=True)
    def parse_battle_type(cls, value):
        """Parses the battle type class object from its name."""
        if isinstance(value, str):
            all = Battle.all()
            if value in all:
                return all[value]
            else:
                raise ValueError
        elif issubclass(value, Battle):
            return value
        else:
            raise TypeError

    class Config(BaseModel.Config):

        json_encoders = {
            type[Battle]: lambda b: b.name().lower(),
        }


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
        ui: "Ui",
        limiter: CapacityLimiter,
        *,
        task_status: TaskStatus = TASK_STATUS_IGNORED,
    ) -> None:
        async with limiter:
            ui.start_battle(matchup)
            task_status.started()
            battle_ui = ui.get_battle_observer(matchup)
            handler = FightHandler(matchup.generator.generator, matchup.solver.solver, battle, battle_ui)
            try:
                await battle.run_battle(
                    handler,
                    config,
                    problem.min_size,
                    battle_ui,
                )
            except Exception as e:
                battle.run_exception = str_with_traceback(e)
            finally:
                ui.battle_completed(matchup)

    @classmethod
    async def run(
        cls,
        config: MatchConfig,
        battle_config: Battle.BattleConfig,
        problem: type[Problem],
        teams: TeamHandler,
        ui: "Ui | None" = None,
    ) -> Self:
        """Executes a match with the specified parameters."""
        result = cls(
            active_teams=[t.name for t in teams.active], excluded_teams=[t.name for t in teams.excluded],
        )
        if ui is None:
            ui = Ui()
        ui.match = result
        limiter = CapacityLimiter(config.parallel_battles)
        current_default_thread_limiter().total_tokens = config.parallel_battles
        async with create_task_group() as tg:
            for matchup in teams.matchups:
                battle = config.battle_type()
                result.results[matchup.generator.name][matchup.solver.name] = battle
                await tg.start(result._run_battle, battle, matchup, battle_config, problem, ui, limiter)
            return result

    @overload
    def battle(self, matchup: Matchup) -> Battle | None: ...

    @overload
    def battle(self, *, generating: Team, solving: Team) -> Battle | None: ...

    def battle(self, matchup: Matchup | None = None, *, generating: Team | None = None, solving: Team | None = None) -> Battle | None:
        """Returns the battle for the given matchup."""
        try:
            if matchup is not None:
                return self.results[matchup.generator.name][matchup.solver.name]
            if generating is not None and solving is not None:
                return self.results[generating.name][solving.name]
            raise TypeError
        except KeyError:
            return None

    def calculate_points(self, points_per_matchup: int) -> dict[str, float]:
        """Calculate the number of points each team scored.

        Each pair of teams fights for the achievable points among one another.
        These achievable points are split over all rounds.
        """
        if len(self.active_teams) == 0:
            return {}
        if len(self.active_teams) == 1:
            return {self.active_teams[0]: points_per_matchup}

        points = {team: 0.0 for team in self.active_teams + self.excluded_teams}
        points_per_battle = round(points_per_matchup / (len(self.active_teams) - 1), 1)

        for first, second in combinations(self.active_teams, 2):
            try:
                first_res = self.results[second][first]
                second_res = self.results[first][second]
            except KeyError:
                continue
            total_score = first_res.score() + second_res.score()
            if total_score == 0:
                # Default values for proportions, assuming no team manages to solve anything
                first_ratio = 0.5
                second_ratio = 0.5
            else:
                first_ratio = first_res.score() / total_score
                second_ratio = second_res.score() / total_score

            points[first] += round(points_per_battle * first_ratio, 1)
            points[second] += round(points_per_battle * second_ratio, 1)

        # we need to also add the points each team would have gotten fighting the excluded teams
        # each active team would have had one set of battles against each excluded team
        for team in self.active_teams:
            points[team] += points_per_battle * len(self.excluded_teams)

        return points


@dataclass
class Ui:
    """Base class for a UI that observes a Match and displays its data.

    The Ui object both observes the match object as it's being built and receives additional updates through method calls.
    To do this, it provides several objects whose methods are essentially curried versions of its own methods.
    These observer classes should generally not be subclassed, all Ui functionality can be implemented by just subclassing
    :cls:`Ui` and implementing its methods.
    """

    match: Match = field(init=False)
    active_battles: list[Matchup] = field(default_factory=list, init=False)

    def get_battle_observer(self, matchup: Matchup) -> "BattleObserver":
        """Creates an observer for a specifc battle."""
        return self.BattleObserver(self, matchup)

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
        def update_fights(self) -> None:
            self.ui.update_fights(self.matchup)

        @inherit_docs
        def update_data(self, data: Battle.UiData) -> None:
            self.ui.update_battle_data(self.matchup, data)

        def start_fight(self, size: int) -> None:
            """Informs the Ui of a newly started fight."""
            self.ui.start_fight(self.matchup, size)

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
