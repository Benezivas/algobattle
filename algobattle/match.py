"""Central managing module for an algorithmic battle."""
from __future__ import annotations
from dataclasses import dataclass
from itertools import combinations
import logging
from prettytable import PrettyTable, DOUBLE_BORDER

from algobattle.battle_wrapper import BattleWrapper
from algobattle.team import Matchup, Team
from algobattle.fight_handler import FightHandler
from algobattle.observer import Passthrough

logger = logging.getLogger('algobattle.match')


@dataclass
class Match(Passthrough):
    """Central managing class for an algorithmic battle."""

    fight_handler: FightHandler
    battle_wrapper: BattleWrapper
    teams: list[Team]
    rounds: int = 5

    def __post_init__(self):
        super().__init__()
        self.battle_wrapper.attach(self)

    @property
    def grouped_matchups(self) -> list[tuple[Matchup, Matchup]]:
        """All `Matchup`s, grouped by the involved teams.

        Each tuple's first matchup has the first team in the group generating, the second has it solving.
        """
        return [(Matchup(*g), Matchup(*g[::-1])) for g in combinations(self.teams, 2)]

    @property
    def matchups(self) -> list[Matchup]:
        """All 'Matchups` that will be fought."""
        if len(self.teams) == 1:
            return [Matchup(self.teams[0], self.teams[0])]
        else:
            return [m for pair in self.grouped_matchups for m in pair]

    def run(self) -> MatchResult:
        """Match entry point, executes fights between all teams."""
        result = MatchResult(self)
        self.notify("match_result", result)
        for matchup in self.matchups:
            for i in range(self.rounds):
                logger.info("#" * 20 + f"  Running Round {i+1}/{self.rounds}  " + "#" * 20)
                battle_result = self.battle_wrapper.run_round(self.fight_handler, matchup)
                result[matchup].append(battle_result)
                self.notify("match_result", result)
        return result


class MatchResult(dict[Matchup, list[BattleWrapper.Result]]):
    """The Result of a `Match`."""

    def __init__(self, match: Match):
        self.match = match
        super().__init__({m: [] for m in match.matchups})

    def calculate_points(self, achievable_points: int) -> dict[Team, float]:
        """Calculate the number of points each team scored.

        Each pair of teams fights for the achievable points among one another.
        These achievable points are split over all rounds.
        """
        if len(self.match.teams) == 1:
            return {self.match.teams[0]: achievable_points}

        if any(not 0 <= len(results) <= self.match.rounds for results in self.values()):
            raise ValueError

        points = {team: 0. for team in self.match.teams}
        points_per_round = round(achievable_points / self.match.rounds, 1)

        for home_matchup, away_matchup in self.match.grouped_matchups:
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
        table = PrettyTable(field_names=["GEN", "SOL", *range(self.match.rounds), "AVG"], min_width=5)
        table.set_style(DOUBLE_BORDER)
        table.align["AVG"] = "r"
        for i in range(self.match.rounds):
            table.align[str(i)] = "r"

        for matchup, results in self.items():
            if not 0 <= len(results) <= self.match.rounds:
                raise RuntimeError
            padding = [""] * (self.match.rounds - len(results))
            average = "" if len(results) == 0 else results[1].format_score(sum(r.score for r in results) / len(results))
            table.add_row([matchup.generator, matchup.solver, *results, *padding, average])

        return f"Battle Type: {self.match.battle_wrapper}\n{table}"
