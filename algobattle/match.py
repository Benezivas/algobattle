"""Central managing module for an algorithmic battle."""
from __future__ import annotations
from dataclasses import dataclass
import logging
from typing import Any
from prettytable import PrettyTable, DOUBLE_BORDER

from algobattle.battle_wrapper import BattleWrapper
from algobattle.battle_wrappers.iterated import Iterated
from algobattle.fight_handler import FightHandler
from algobattle.observer import Observer, Subject
from algobattle.team import Matchup, Team, TeamHandler
from algobattle.problem import Problem

logger = logging.getLogger("algobattle.match")


@dataclass(kw_only=True)
class MatchConfig:
    """Parameters determining the match execution."""

    verbose: bool = False
    safe_build: bool = False
    battle_type: type[BattleWrapper] = Iterated
    rounds: int = 5
    points: int = 100
    timeout_build: float | None = 600
    timeout_generator: float | None = 30
    timeout_solver: float | None = 30
    space_generator: int | None = None
    space_solver: int | None = None
    cpus: int = 1

    @property
    def docker_params(self) -> dict[str, Any]:
        """The parameters relevant to execution of docker containers, passable to FightHandler."""
        return {
            "timeout_generator": self.timeout_generator,
            "timeout_solver": self.timeout_solver,
            "space_generator": self.space_generator,
            "space_solver": self.space_solver,
            "cpus": self.cpus,
        }

    @staticmethod
    def from_dict(info: dict[str, Any]) -> MatchConfig:
        """Parses a :cls:`MatchConfig` from a dict."""
        if "battle_type" in info:
            try:
                wrapper = BattleWrapper.all()[info["battle_type"]]
            except KeyError:
                raise ValueError(f"Attempted to use invalid battle wrapper {info['battle_type']}.")
            update = {"battle_type": wrapper}
        else:
            update = {}
        return MatchConfig(**(info | update))


def run_match(
    config: MatchConfig,
    wrapper_config: BattleWrapper.Config,
    problem: type[Problem],
    teams: TeamHandler,
    observer: Observer | None = None,
) -> MatchResult:
    """Executes the match with the specified parameters."""
    result = MatchResult(config, teams, observer)
    for matchup in teams.matchups:
        fight_handler = FightHandler(problem=problem, matchup=matchup, **config.docker_params)
        for i in range(config.rounds):
            logger.info("#" * 20 + f"  Running Round {i+1}/{config.rounds}  " + "#" * 20)
            wrapper = config.battle_type(wrapper_config, problem)
            try:
                battle_result = wrapper.run_battle(fight_handler)
            except Exception:
                logger.critical(f"Unhandeled error during execution of battle wrapper!")
                battle_result = wrapper.Result()    # type: ignore
            result[matchup].append(battle_result)
            result.notify()
    return result


class MatchResult(Subject, dict[Matchup, list[BattleWrapper.Result]]):
    """The Result of a whole Match."""

    def __init__(self, config: MatchConfig, teams: TeamHandler, observer: Observer | None = None):
        Subject.__init__(self, observer)
        dict.__init__(self, {m: [] for m in teams.matchups})
        self.config = config
        self.teams = teams
        self.notify_vars = True

    def calculate_points(self, achievable_points: int) -> dict[Team, float]:
        """Calculate the number of points each team scored.

        Each pair of teams fights for the achievable points among one another.
        These achievable points are split over all rounds.
        """
        if len(self.teams) == 1:
            return {self.teams[0]: achievable_points}

        if any(not 0 <= len(results) <= self.config.rounds for results in self.values()):
            raise ValueError

        points = {team: 0.0 for team in self.teams}
        if self.config.rounds == 0:
            return points
        points_per_round = round(achievable_points / self.config.rounds, 1)

        for home_matchup, away_matchup in self.teams.grouped_matchups:
            for home_res, away_res in zip(self[home_matchup], self[away_matchup]):
                total_score = home_res.score + away_res.score
                if total_score == 0:
                    # Default values for proportions, assuming no team manages to solve anything
                    home_ratio = 0.5
                    away_ratio = 0.5
                else:
                    home_ratio = home_res.score / total_score
                    away_ratio = away_res.score / total_score

                points[home_matchup.solver] += round(points_per_round * home_ratio, 1)
                points[away_matchup.solver] += round(points_per_round * away_ratio, 1)

        return points

    def __str__(self) -> str:
        table = PrettyTable(field_names=["GEN", "SOL", *range(1, self.config.rounds + 1), "AVG"], min_width=5)
        table.set_style(DOUBLE_BORDER)
        table.align["AVG"] = "r"
        for i in range(1, self.config.rounds + 1):
            table.align[str(i)] = "r"

        for matchup, results in self.items():
            if not 0 <= len(results) <= self.config.rounds:
                raise RuntimeError
            padding = [""] * (self.config.rounds - len(results))
            average = "" if len(results) == 0 else results[0].format_score(sum(r.score for r in results) / len(results))
            results = [str(r) for r in results]
            table.add_row([str(matchup.generator), str(matchup.solver), *results, *padding, average])

        return f"Battle Type: {self.config.battle_type.name()}\n{table}"
