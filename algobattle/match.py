"""Central managing module for an algorithmic battle."""
from __future__ import annotations
from configparser import ConfigParser
from dataclasses import dataclass
import logging
from pathlib import Path
from prettytable import PrettyTable, DOUBLE_BORDER

from algobattle.battle_wrapper import BattleWrapper
from algobattle.fight_handler import FightHandler
from algobattle.observer import Observer, Subject
from algobattle.team import Matchup, Team, TeamHandler
from algobattle.util import import_problem_from_path

logger = logging.getLogger("algobattle.match")


@dataclass
class MatchInfo:
    """Class specifying all the parameters to run a match."""

    battle_wrapper: BattleWrapper
    teams: TeamHandler
    rounds: int = 5

    @classmethod
    def build(
        cls,
        *,
        problem_path: Path,
        config_path: Path,
        teams: TeamHandler,
        rounds: int = 5,
        battle_type: str,
    ) -> MatchInfo:
        """Builds a :cls:`MatchInfo` object from the provided data."""
        problem = import_problem_from_path(problem_path)
        config = ConfigParser()
        config.read(config_path)
        fight_handler = FightHandler(problem, config)
        battle_wrapper = BattleWrapper.initialize(battle_type, fight_handler, config)
        return MatchInfo(battle_wrapper, teams, rounds)

    def run_match(self, observer: Observer | None = None) -> MatchResult:
        """Executes the match with the specified parameters."""
        result = MatchResult(self, observer)
        for matchup in self.teams.matchups:
            for i in range(self.rounds):
                logger.info("#" * 20 + f"  Running Round {i+1}/{self.rounds}  " + "#" * 20)
                battle_result = self.battle_wrapper.run_round(matchup, observer)
                result[matchup].append(battle_result)
                result.notify()
        return result


class MatchResult(Subject, dict[Matchup, list[BattleWrapper.Result]]):
    """The Result of a whole Match."""

    def __init__(self, match: MatchInfo, observer: Observer | None = None):
        Subject.__init__(self, observer)
        dict.__init__(self, {m: [] for m in match.teams.matchups})
        self.match = match
        self.notify_vars = True

    def calculate_points(self, achievable_points: int) -> dict[Team, float]:
        """Calculate the number of points each team scored.

        Each pair of teams fights for the achievable points among one another.
        These achievable points are split over all rounds.
        """
        if len(self.match.teams) == 1:
            return {self.match.teams[0]: achievable_points}

        if any(not 0 <= len(results) <= self.match.rounds for results in self.values()):
            raise ValueError

        points = {team: 0.0 for team in self.match.teams}
        if self.match.rounds == 0:
            return points
        points_per_round = round(achievable_points / self.match.rounds, 1)

        for home_matchup, away_matchup in self.match.teams.grouped_matchups:
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
        table = PrettyTable(field_names=["GEN", "SOL", *range(1, self.match.rounds + 1), "AVG"], min_width=5)
        table.set_style(DOUBLE_BORDER)
        table.align["AVG"] = "r"
        for i in range(1, self.match.rounds + 1):
            table.align[str(i)] = "r"

        for matchup, results in self.items():
            if not 0 <= len(results) <= self.match.rounds:
                raise RuntimeError
            padding = [""] * (self.match.rounds - len(results))
            average = "" if len(results) == 0 else results[0].format_score(sum(r.score for r in results) / len(results))
            results = [str(r) for r in results]
            table.add_row([str(matchup.generator), str(matchup.solver), *results, *padding, average])

        return f"Battle Type: {self.match.battle_wrapper.type}\n{table}"
