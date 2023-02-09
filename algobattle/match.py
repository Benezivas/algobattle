"""Central managing module for an algorithmic battle."""
from __future__ import annotations
from dataclasses import dataclass
import logging
from typing import Any, Self
from prettytable import PrettyTable, DOUBLE_BORDER

from algobattle.battle_wrapper import BattleWrapper
from algobattle.battle_wrappers.iterated import Iterated
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


class Match(Subject):
    """The Result of a whole Match."""

    def __init__(
        self,
        config: MatchConfig,
        wrapper_config: BattleWrapper.Config,
        problem: type[Problem],
        teams: TeamHandler,
        observer: Observer | None = None,
    ) -> None:
        self.results: dict[Matchup, list[BattleWrapper]] = {}
        self.config = config
        self.wrapper_config = wrapper_config
        self.problem = problem
        self.teams = teams
        super().__init__(observer)

    @classmethod
    def run(
        cls,
        config: MatchConfig,
        wrapper_config: BattleWrapper.Config,
        problem: type[Problem],
        teams: TeamHandler,
        observer: Observer | None = None,
    ) -> Self:
        """Executes the match with the specified parameters."""
        result = cls(config, wrapper_config, problem, teams, observer)
        for matchup in teams.matchups:
            result.results[matchup] = []
            for i in range(config.rounds):
                logger.info("#" * 20 + f"  Running Round {i+1}/{config.rounds}  " + "#" * 20)
                wrapper = config.battle_type(observer=observer)
                result.results[matchup].append(wrapper)
                try:
                    wrapper.run_battle(matchup.generator.generator, matchup.solver.solver, wrapper_config, problem.min_size)
                except Exception as e:
                    logger.critical(f"Unhandeled error during execution of battle wrapper!\n{e}")
                result.notify()
        return result

    def calculate_points(self, achievable_points: int) -> dict[Team, float]:
        """Calculate the number of points each team scored.

        Each pair of teams fights for the achievable points among one another.
        These achievable points are split over all rounds.
        """
        if len(self.teams) == 0:
            return {}
        if len(self.teams) == 1:
            return {self.teams[0]: achievable_points}

        if any(not 0 <= len(results) <= self.config.rounds for results in self.results.values()):
            raise ValueError

        points = {team: 0.0 for team in self.teams}
        if self.config.rounds == 0:
            return points
        points_per_round = round(achievable_points / ((len(self.teams) - 1) * self.config.rounds), 1)

        for home_matchup, away_matchup in self.teams.grouped_matchups:
            home_team = getattr(home_matchup, self.config.battle_type.scoring_team)
            away_team = getattr(away_matchup, self.config.battle_type.scoring_team)
            for home_res, away_res in zip(self.results[home_matchup], self.results[away_matchup]):
                total_score = home_res.score() + away_res.score()
                if total_score == 0:
                    # Default values for proportions, assuming no team manages to solve anything
                    home_ratio = 0.5
                    away_ratio = 0.5
                else:
                    home_ratio = home_res.score() / total_score
                    away_ratio = away_res.score() / total_score

                points[home_team] += round(points_per_round * home_ratio, 1)
                points[away_team] += round(points_per_round * away_ratio, 1)

        return points

    def display(self) -> str:
        """Formats the match data into a table that can be printed to the terminal."""
        table = PrettyTable(field_names=["GEN", "SOL", *range(1, self.config.rounds + 1), "AVG"], min_width=5)
        table.set_style(DOUBLE_BORDER)
        table.align["AVG"] = "r"
        for i in range(1, self.config.rounds + 1):
            table.align[str(i)] = "r"

        for matchup, results in self.results.items():
            if not 0 <= len(results) <= self.config.rounds:
                raise RuntimeError
            padding = [""] * (self.config.rounds - len(results))
            average = "" if len(results) == 0 else results[0].format_score(sum(r.score() for r in results) / len(results))
            results = [r.format_score(r.score()) for r in results]
            table.add_row([str(matchup.generator), str(matchup.solver), *results, *padding, average])

        return f"Battle Type: {self.config.battle_type.name()}\n{table}"
