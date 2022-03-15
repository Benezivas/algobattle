"""Tests for all util functions."""
from dataclasses import dataclass
from unittest import TestCase, main
import logging
from algobattle.battle_style import BattleStyle

from algobattle.battle_styles.averaged import Averaged
from algobattle.battle_styles.iterated import Iterated
from algobattle.team import Team, BattleMatchups, Matchup
from algobattle.match import MatchResult

logging.disable(logging.CRITICAL)


@dataclass(frozen=True)
class TestTeam(Team):
    """Team class that doesn't build containers to make tests that don't need them run faster."""

    name: str


def team(name: str) -> Team:
    """Aliasing function to deal with invariance issues."""
    return TestTeam(name)

def _iter_res(*args, **kwargs) -> BattleStyle.Result:
    return Iterated.Result(*args, **kwargs)

def _avg_res(*args, **kwargs) -> BattleStyle.Result:
    return Averaged.Result(*args, **kwargs)

class PointsCalculationTests(TestCase):
    """Tests for the points calculation functions."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.teams = [team("0"), team("1")]
        cls.matchups = BattleMatchups(cls.teams)

    def test_calculate_points_iterated_zero_rounds(self):
        self.assertEqual(MatchResult(self.matchups, rounds=0).calculate_points(100), {})

    def test_calculate_points_iterated_no_successful_round(self):
        results = MatchResult(self.matchups, rounds=2)
        for m in self.matchups:
            results[m] = [_iter_res(solved=0), _iter_res(solved=0)]
        self.assertEqual(results.calculate_points(100), {self.teams[0]: 50, self.teams[1]: 50})

    def test_calculate_points_iterated_draw(self):
        results = MatchResult(self.matchups, rounds=2)
        results[self.matchups[0]] = [_iter_res(solved=20), _iter_res(solved=10)]
        results[self.matchups[1]] = [_iter_res(solved=10), _iter_res(solved=20)]
        self.assertEqual(results.calculate_points(100), {self.teams[0]: 50, self.teams[1]: 50})

    def test_calculate_points_iterated_domination(self):
        results = MatchResult(self.matchups, rounds=2)
        results[self.matchups[0]] = [_iter_res(solved=10), _iter_res(solved=10)]
        results[self.matchups[1]] = [_iter_res(solved=0), _iter_res(solved=0)]
        self.assertEqual(results.calculate_points(100), {self.teams[0]: 0, self.teams[1]: 100})

    def test_calculate_points_averaged_zero_rounds(self):
        self.assertEqual(MatchResult(self.matchups, rounds=0).calculate_points(100), {})

    def test_calculate_points_averaged_draw(self):
        results = MatchResult(self.matchups, rounds=2)
        results[self.matchups[0]] = [_avg_res([1.5, 1.5, 1.5]), _avg_res([1.5, 1.5, 1.5])]
        results[self.matchups[1]] = [_avg_res([1.5, 1.5, 1.5]), _avg_res([1.5, 1.5, 1.5])]
        self.assertEqual(results.calculate_points(100), {self.teams[0]: 50, self.teams[1]: 50})

    def test_calculate_points_averaged_domination(self):
        results = MatchResult(self.matchups, rounds=2)
        results[self.matchups[0]] = [_avg_res([1.5, 1.5, 1.5]), _avg_res([1.5, 1.5, 1.5])]
        results[self.matchups[1]] = [_avg_res([1.0, 1.0, 1.0]), _avg_res([1.0, 1.0, 1.0])]
        self.assertEqual(results.calculate_points(100), {self.teams[0]: 60, self.teams[1]: 40})

    def test_calculate_points_averaged_no_successful_round(self):
        results = MatchResult(self.matchups, rounds=2)
        results[self.matchups[0]] = [_avg_res([0, 0, 0]), _avg_res([0, 0, 0])]
        results[self.matchups[1]] = [_avg_res([0, 0, 0]), _avg_res([0, 0, 0])]
        self.assertEqual(results.calculate_points(100), {self.teams[0]: 50, self.teams[1]: 50})


class MatchupsTests(TestCase):
    """Tests for the matchup generators."""

    def test_all_battle_pairs(self):
        team0 = team("0")
        team1 = team("1")
        teams = [team0, team1]
        self.assertEqual(list(BattleMatchups(teams)), [Matchup(team0, team1), Matchup(team1, team0)])

    def test_all_battle_pairs_solo_battle(self):
        team0 = team("0")
        self.assertEqual(list(BattleMatchups([team0])), [Matchup(team0, team0)])


if __name__ == '__main__':
    main()
