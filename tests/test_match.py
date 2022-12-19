"""Tests for the Match class."""
# pyright: reportMissingSuperCall=false
import unittest
import logging
from pathlib import Path

from algobattle.battle import setup_logging
from algobattle.battle_wrappers.iterated import Iterated
from algobattle.battle_wrappers.averaged import Averaged
from algobattle.fight_handler import FightHandler
from algobattle.match import MatchConfig, MatchResult, run_match
from algobattle.team import Team, Matchup, TeamHandler, TeamInfo
from algobattle.docker_util import Image, get_os_type
from . import testsproblem

logging.disable(logging.CRITICAL)


class TestImage(Image):
    """Docker image that doesn't rely on an actual docker daemon image."""

    def __init__(self, image_name: str) -> None:
        self.name = image_name
        self.id = image_name
        self.description = image_name

    def run(self, input: str = "", timeout: float | None = None, memory: int | None = None, cpus: int | None = None) -> str:
        return input

    def remove(self) -> None:
        return


class TestTeam(Team):
    """Team that doesn't rely on actual docker images."""

    def __init__(self, team_name: str) -> None:
        self.name = team_name
        self.generator = TestImage(f"TestImage-{self.name}-generator")
        self.solver = TestImage(f"TestImage-{self.name}-solver")


class Matchtests(unittest.TestCase):
    """Tests for the match object."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up a match object."""
        cls.team0 = TestTeam("0")
        cls.team1 = TestTeam("1")
        cls.matchup0 = Matchup(cls.team0, cls.team1)
        cls.matchup1 = Matchup(cls.team1, cls.team0)

        cls.fight_handler = FightHandler(testsproblem.Problem())

        cls.wrapper_iter = Iterated(cls.fight_handler, Iterated.Config())
        cls.wrapper_avg = Averaged(cls.fight_handler, Averaged.Config())
        cls.teams = TeamHandler((cls.team0, cls.team1))

    def test_all_battle_pairs_two_teams(self):
        """Two teams both generate and solve one time each."""
        self.assertEqual(self.teams.matchups, [self.matchup0, self.matchup1])

    def test_all_battle_pairs_single_player(self):
        """A team playing against itself is the only battle pair in single player."""
        teams = TeamHandler((self.team0,))
        self.assertEqual(teams.matchups, [Matchup(self.team0, self.team0)])

    def test_calculate_points_zero_rounds(self):
        """All teams get 0 points if no rounds have been fought."""
        config = MatchConfig(rounds=0)
        result = MatchResult(config, self.teams)
        self.assertEqual(result.calculate_points(100), {self.team0: 0, self.team1: 0})

    def test_calculate_points_iterated_no_successful_round(self):
        """Two teams should get an equal amount of points if nobody solved anything."""
        result = MatchResult(MatchConfig(rounds=2), self.teams)
        result[self.matchup0] = [Iterated.Result(0, 0, 0), Iterated.Result(0, 0, 0)]
        result[self.matchup1] = [Iterated.Result(0, 0, 0), Iterated.Result(0, 0, 0)]
        self.assertEqual(result.calculate_points(100), {self.team0: 50, self.team1: 50})

    def test_calculate_points_iterated_draw(self):
        """Two teams should get an equal amount of points if both solved a problem equally well."""
        result = MatchResult(MatchConfig(rounds=2), self.teams)
        result[self.matchup0] = [Iterated.Result(20, 0, 0), Iterated.Result(10, 0, 0)]
        result[self.matchup1] = [Iterated.Result(10, 0, 0), Iterated.Result(20, 0, 0)]
        self.assertEqual(result.calculate_points(100), {self.team0: 50, self.team1: 50})

    def test_calculate_points_iterated_domination(self):
        """One team should get all points if it solved anything and the other team nothing."""
        result = MatchResult(MatchConfig(rounds=2), self.teams)
        result[self.matchup0] = [Iterated.Result(10, 0, 0), Iterated.Result(10, 0, 0)]
        result[self.matchup1] = [Iterated.Result(0, 0, 0), Iterated.Result(0, 0, 0)]
        self.assertEqual(result.calculate_points(100), {self.team0: 0, self.team1: 100})

    def test_calculate_points_iterated_one_team_better(self):
        """One team should get more points than the other if it performed better."""
        result = MatchResult(MatchConfig(rounds=2), self.teams)
        result[self.matchup0] = [Iterated.Result(10, 0, 0), Iterated.Result(10, 0, 0)]
        result[self.matchup1] = [Iterated.Result(20, 0, 0), Iterated.Result(20, 0, 0)]
        self.assertEqual(result.calculate_points(100), {self.team0: 66.6, self.team1: 33.4})

    def test_calculate_points_averaged_no_successful_round(self):
        """Two teams should get an equal amount of points if nobody solved anything."""
        result = MatchResult(MatchConfig(rounds=2, battle_type=Averaged), self.teams)
        result[self.matchup0] = [Averaged.Result(1, 1, 1, [0, 0, 0]), Averaged.Result(1, 1, 1, [0, 0, 0])]
        result[self.matchup1] = [Averaged.Result(1, 1, 1, [0, 0, 0]), Averaged.Result(1, 1, 1, [0, 0, 0])]
        self.assertEqual(result.calculate_points(100), {self.team0: 50, self.team1: 50})

    def test_calculate_points_averaged_draw(self):
        """Two teams should get an equal amount of points if both solved a problem equally well."""
        result = MatchResult(MatchConfig(rounds=2, battle_type=Averaged), self.teams)
        result[self.matchup0] = [Averaged.Result(1, 1, 1, [1.5, 1.5, 1.5]), Averaged.Result(1, 1, 1, [1.5, 1.5, 1.5])]
        result[self.matchup1] = [Averaged.Result(1, 1, 1, [1.5, 1.5, 1.5]), Averaged.Result(1, 1, 1, [1.5, 1.5, 1.5])]
        self.assertEqual(result.calculate_points(100), {self.team0: 50, self.team1: 50})

    def test_calculate_points_averaged_domination(self):
        """One team should get all points if it solved anything and the other team nothing."""
        result = MatchResult(MatchConfig(rounds=2, battle_type=Averaged), self.teams)
        result[self.matchup0] = [Averaged.Result(1, 1, 1, [0, 0, 0]), Averaged.Result(1, 1, 1, [0, 0, 0])]
        result[self.matchup1] = [Averaged.Result(1, 1, 1, [1, 1, 1]), Averaged.Result(1, 1, 1, [1, 1, 1])]
        self.assertEqual(result.calculate_points(100), {self.team0: 100, self.team1: 0})

    def test_calculate_points_averaged_one_team_better(self):
        """One team should get more points than the other if it performed better."""
        result = MatchResult(MatchConfig(rounds=2, battle_type=Averaged), self.teams)
        result[self.matchup0] = [Averaged.Result(1, 1, 1, [1.5, 1.5, 1.5]), Averaged.Result(1, 1, 1, [1.5, 1.5, 1.5])]
        result[self.matchup1] = [Averaged.Result(1, 1, 1, [1, 1, 1]), Averaged.Result(1, 1, 1, [1, 1, 1])]
        self.assertEqual(result.calculate_points(100), {self.team0: 60, self.team1: 40})

    # TODO: Add tests for remaining functions


class Execution(unittest.TestCase):
    """Some basic tests for the execution of the battles."""

    @classmethod
    def setUpClass(cls) -> None:
        logging.disable(logging.NOTSET)  # reenable logging
        setup_logging(Path.home() / ".algobattle_logs", verbose_logging=True, silent=False)
        problem_path = Path(__file__).parent / "testsproblem"
        cls.problem = testsproblem.Problem()
        cls.config = MatchConfig(timeout_generator=2, timeout_solver=2, rounds=2)
        cls.iter_config = Iterated.Config(iteration_cap=5)
        cls.avg_config = Averaged.Config(instance_size=5,iterations=3)
        cls.generator = problem_path / "generator"
        cls.solver = problem_path / "solver"
        if get_os_type() == "windows":
            cls.generator /= "Dockerfile_windows"
            cls.solver /= "Dockerfile_windows"

    @classmethod
    def tearDownClass(cls) -> None:
        logging.disable(logging.CRITICAL)
        return super().tearDownClass()

    def test_basic(self):
        team = TeamInfo("team0", self.generator, self.solver)
        with TeamHandler.build([team]) as teams:
            run_match(self.config, self.iter_config, self.problem, teams)

    def test_multi_team(self):
        team0 = TeamInfo("team0", self.generator, self.solver)
        team1 = TeamInfo("team1", self.generator, self.solver)
        with TeamHandler.build([team0, team1]) as teams:
            run_match(self.config, self.iter_config, self.problem, teams)

    def test_averaged(self):
        team = TeamInfo("team0", self.generator, self.solver)
        with TeamHandler.build([team]) as teams:
            config = MatchConfig(timeout_generator=2, timeout_solver=2, rounds=2, battle_type=Averaged)
            run_match(config, self.avg_config, self.problem, teams)



if __name__ == "__main__":
    unittest.main()
