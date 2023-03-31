"""Central managing module for an algorithmic battle."""
from dataclasses import dataclass, field
from datetime import datetime
import logging
from typing import Self

from prettytable import PrettyTable, DOUBLE_BORDER
from pydantic import BaseModel, validator
from anyio import create_task_group, CapacityLimiter, TASK_STATUS_IGNORED
from anyio.to_thread import current_default_thread_limiter
from anyio.abc import TaskStatus

from algobattle.battle import Battle, Iterated, BattleUiProxy
from algobattle.docker_util import GeneratorResult, ProgramDisplayData, ProgramUiProxy, RunParameters, SolverResult
from algobattle.team import Matchup, TeamHandler, Team
from algobattle.problem import Problem
from algobattle.util import Role, inherit_docs

logger = logging.getLogger("algobattle.match")


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


class Match:
    """The Result of a whole Match."""

    def __init__(
        self,
        config: MatchConfig,
        battle_config: Battle.Config,
        problem: type[Problem],
        teams: TeamHandler,
    ) -> None:
        self.results: dict[Matchup, Battle] = {}
        self.config = config
        self.battle_config = battle_config
        self.problem = problem
        self.teams = teams
        super().__init__()

    async def _run_battle(
        self,
        battle: Battle,
        matchup: Matchup,
        ui: "Ui",
        limiter: CapacityLimiter,
        *,
        task_status: TaskStatus = TASK_STATUS_IGNORED,
    ) -> None:
        async with limiter:
            ui.start_battle(matchup)
            task_status.started()
            try:
                await battle.run_battle(
                    matchup.generator.generator,
                    matchup.solver.solver,
                    self.battle_config,
                    self.problem.min_size,
                )
            except Exception as e:
                logger.critical(f"Unhandeled error during execution of battle!\n{e}")
            finally:
                ui.battle_completed(matchup)

    @classmethod
    async def run(
        cls,
        config: MatchConfig,
        battle_config: Battle.Config,
        problem: type[Problem],
        teams: TeamHandler,
        ui: "Ui" | None = None,
    ) -> Self:
        """Executes a match with the specified parameters."""
        result = cls(config, battle_config, problem, teams)
        if ui is None:
            ui = Ui()
        ui.match = result
        limiter = CapacityLimiter(config.parallel_battles)
        current_default_thread_limiter().total_tokens = config.parallel_battles
        async with create_task_group() as tg:
            for matchup in teams.matchups:
                battle = config.battle_type(ui.get_battle_observer(matchup))
                result.results[matchup] = battle
                await tg.start(result._run_battle, battle, matchup, ui, limiter)
            return result

    def calculate_points(self) -> dict[str, float]:
        """Calculate the number of points each team scored.

        Each pair of teams fights for the achievable points among one another.
        These achievable points are split over all rounds.
        """
        achievable_points = self.config.points
        if len(self.teams.active) == 0:
            return {}
        if len(self.teams.active) == 1:
            return {self.teams.active[0].name: achievable_points}

        points = {team.name: 0.0 for team in self.teams.active + self.teams.excluded}
        points_per_battle = round(achievable_points / (len(self.teams.active) - 1), 1)

        for home_matchup, away_matchup in self.teams.grouped_matchups:
            home_team: Team = getattr(home_matchup, self.config.battle_type.scoring_team)
            away_team: Team = getattr(away_matchup, self.config.battle_type.scoring_team)
            home_res = self.results[home_matchup]
            away_res = self.results[away_matchup]
            total_score = home_res.score() + away_res.score()
            if total_score == 0:
                # Default values for proportions, assuming no team manages to solve anything
                home_ratio = 0.5
                away_ratio = 0.5
            else:
                home_ratio = home_res.score() / total_score
                away_ratio = away_res.score() / total_score

            points[home_team.name] += round(points_per_battle * home_ratio, 1)
            points[away_team.name] += round(points_per_battle * away_ratio, 1)

        # we need to also add the points each team would have gotten fighting the excluded teams
        # each active team would have had one set of battles against each excluded team
        for team in self.teams.active:
            points[team.name] += points_per_battle * len(self.teams.excluded)

        return points

    def display(self) -> str:
        """Formats the match data into a table that can be printed to the terminal."""
        table = PrettyTable(field_names=["Generator", "Solver", "Result"], min_width=5)
        table.set_style(DOUBLE_BORDER)
        table.align["Result"] = "r"

        for matchup, result in self.results.items():
            table.add_row([str(matchup.generator), str(matchup.solver), result.format_score(result.score())])

        return f"Battle Type: {self.config.battle_type.name()}\n{table}"


@dataclass
class Ui:
    """Base class for a UI that observes a Match and displays its data."""

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

    def update_curr_fight(
        self,
        matchup: Matchup,
        role: Role | None = None,
        data: ProgramDisplayData | GeneratorResult | SolverResult | None = None,
    ) -> None:
        """Passes new info about the current fight to the Ui."""
        return

    @dataclass
    class BattleObserver(BattleUiProxy):
        """Tracks updates for a specific battle"""

        ui: "Ui"
        matchup: Matchup
        generator: "Ui.ProgramObserver" = field(init=False)
        solver: "Ui.ProgramObserver" = field(init=False)

        def __post_init__(self) -> None:
            self.generator = Ui.ProgramObserver(self, "generator")
            self.solver = Ui.ProgramObserver(self, "solver")

        @inherit_docs
        def update_fights(self) -> None:
            self.ui.update_fights(self.matchup)

        @inherit_docs
        def update_data(self, data: Battle.UiData) -> None:
            self.ui.update_battle_data(self.matchup, data)

        @inherit_docs
        def update_curr_fight(
            self,
            role: Role | None = None,
            data: ProgramDisplayData | GeneratorResult | SolverResult | None = None,
        ) -> None:
            self.ui.update_curr_fight(self.matchup, role, data)

    @dataclass
    class ProgramObserver(ProgramUiProxy):
        """Tracks state of a specific program execution."""

        battle: "Ui.BattleObserver"
        role: Role
        data: ProgramDisplayData | None = None

        @inherit_docs
        def start(self, size: int, timeout: float | None, space: int | None, cpus: int) -> None:
            self.data = ProgramDisplayData(
                datetime.now(),
                size,
                RunParameters(timeout=timeout, space=space, cpus=cpus),
            )
            self.battle.ui.update_curr_fight(self.battle.matchup, self.role, self.data)

        @inherit_docs
        def stop(self, runtime: float) -> None:
            if self.data is None:
                raise RuntimeError
            self.data.runtime = runtime
            self.battle.ui.update_curr_fight(self.battle.matchup, self.role, self.data)
