"""Tests for the Match class."""
# pyright: reportMissingSuperCall=false
from unittest import TestCase, main
import logging
from pathlib import Path

from algobattle.battle import parse_cli_args, setup_logging
from algobattle.battle_wrapper import Iterated, Averaged
from algobattle.match import MatchConfig, Match
from algobattle.team import Team, Matchup, TeamHandler, TeamInfo
from algobattle.docker_util import DockerConfig, RunParameters, get_os_type
from .testsproblem import Problem as TestProblem

logging.disable(logging.CRITICAL)


class TestTeam(Team):
    """Team that doesn't rely on actual docker images."""

    def __init__(self, team_name: str) -> None:
        self.name = team_name


class Matchtests(TestCase):
    """Tests for the match object."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up a match object."""
        cls.team0 = TestTeam("0")
        cls.team1 = TestTeam("1")
        cls.matchup0 = Matchup(cls.team0, cls.team1)
        cls.matchup1 = Matchup(cls.team1, cls.team0)
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
        match = Match(MatchConfig(rounds=0), Iterated.Config(), TestProblem, self.teams)
        self.assertEqual(match.calculate_points(100), {self.team0: 0, self.team1: 0})

    def test_calculate_points_iterated_no_successful_round(self):
        """Two teams should get an equal amount of points if nobody solved anything."""
        match = Match(MatchConfig(rounds=2), Iterated.Config(), TestProblem, self.teams)
        battle = Iterated()
        battle.reached = 0
        match.results[self.matchup0] = [battle, battle]
        match.results[self.matchup1] = [battle, battle]
        self.assertEqual(match.calculate_points(100), {self.team0: 50, self.team1: 50})

    def test_calculate_points_iterated_draw(self):
        """Two teams should get an equal amount of points if both solved a problem equally well."""
        match = Match(MatchConfig(rounds=2), Iterated.Config(), TestProblem, self.teams)
        battle = Iterated()
        battle.reached = 20
        battle2 = Iterated()
        battle2.reached = 10
        match.results[self.matchup0] = [battle, battle2]
        match.results[self.matchup1] = [battle2, battle]
        self.assertEqual(match.calculate_points(100), {self.team0: 50, self.team1: 50})

    def test_calculate_points_iterated_domination(self):
        """One team should get all points if it solved anything and the other team nothing."""
        match = Match(MatchConfig(rounds=2), Iterated.Config(), TestProblem, self.teams)
        battle = Iterated()
        battle.reached = 10
        battle2 = Iterated()
        battle2.reached = 0
        match.results[self.matchup0] = [battle, battle]
        match.results[self.matchup1] = [battle2, battle2]
        self.assertEqual(match.calculate_points(100), {self.team0: 0, self.team1: 100})

    def test_calculate_points_iterated_one_team_better(self):
        """One team should get more points than the other if it performed better."""
        match = Match(MatchConfig(rounds=2), Iterated.Config(), TestProblem, self.teams)
        battle = Iterated()
        battle.reached = 10
        battle2 = Iterated()
        battle2.reached = 20
        match.results[self.matchup0] = [battle, battle]
        match.results[self.matchup1] = [battle2, battle2]
        self.assertEqual(match.calculate_points(100), {self.team0: 66.6, self.team1: 33.4})

    def test_calculate_points_averaged_no_successful_round(self):
        """Two teams should get an equal amount of points if nobody solved anything."""
        match = Match(MatchConfig(rounds=2, battle_type=Averaged), Averaged.Config(), TestProblem, self.teams)
        battle = Averaged()
        battle.scores = [0, 0, 0]
        match.results[self.matchup0] = [battle, battle]
        match.results[self.matchup1] = [battle, battle]
        self.assertEqual(match.calculate_points(100), {self.team0: 50, self.team1: 50})

    def test_calculate_points_averaged_draw(self):
        """Two teams should get an equal amount of points if both solved a problem equally well."""
        match = Match(MatchConfig(rounds=2, battle_type=Averaged), Averaged.Config(), TestProblem, self.teams)
        battle = Averaged()
        battle.scores = [.5, .5, .5]
        match.results[self.matchup0] = [battle, battle]
        match.results[self.matchup1] = [battle, battle]
        self.assertEqual(match.calculate_points(100), {self.team0: 50, self.team1: 50})

    def test_calculate_points_averaged_domination(self):
        """One team should get all points if it solved anything and the other team nothing."""
        match = Match(MatchConfig(rounds=2, battle_type=Averaged), Averaged.Config(), TestProblem, self.teams)
        battle = Averaged()
        battle.scores = [0, 0, 0]
        battle2 = Averaged()
        battle2.scores = [1, 1, 1]
        match.results[self.matchup0] = [battle, battle]
        match.results[self.matchup1] = [battle2, battle2]
        self.assertEqual(match.calculate_points(100), {self.team0: 100, self.team1: 0})

    def test_calculate_points_averaged_one_team_better(self):
        """One team should get more points than the other if it performed better."""
        match = Match(MatchConfig(rounds=2, battle_type=Averaged), Averaged.Config(), TestProblem, self.teams)
        battle = Averaged()
        battle.scores = [.6, .6, .6]
        battle2 = Averaged()
        battle2.scores = [.4, .4, .4]
        match.results[self.matchup0] = [battle, battle]
        match.results[self.matchup1] = [battle2, battle2]
        self.assertEqual(match.calculate_points(100), {self.team0: 60, self.team1: 40})

    # TODO: Add tests for remaining functions


class Execution(TestCase):
    """Some basic tests for the execution of the battles."""

    @classmethod
    def setUpClass(cls) -> None:
        logging.disable(logging.NOTSET)  # reenable logging
        setup_logging(Path.home() / ".algobattle_logs", verbose_logging=True, silent=False)
        problem_path = Path(__file__).parent / "testsproblem"
        cls.problem = TestProblem
        cls.config = MatchConfig(rounds=2)
        run_params = RunParameters(timeout=2)
        cls.docker_config = DockerConfig(generator=run_params, solver=run_params)
        cls.iter_config = Iterated.Config(iteration_cap=10)
        cls.avg_config = Averaged.Config(instance_size=5, iterations=3)
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
        with TeamHandler.build([team], self.problem, self.docker_config, safe_build=True) as teams:
            Match.run(self.config, self.iter_config, TestProblem, teams)

    def test_multi_team(self):
        team0 = TeamInfo("team0", self.generator, self.solver)
        team1 = TeamInfo("team1", self.generator, self.solver)
        with TeamHandler.build([team0, team1], self.problem, self.docker_config, safe_build=True) as teams:
            Match.run(self.config, self.iter_config, TestProblem, teams)

    def test_averaged(self):
        team = TeamInfo("team0", self.generator, self.solver)
        with TeamHandler.build([team], self.problem, self.docker_config, safe_build=True) as teams:
            config = MatchConfig(rounds=2, battle_type=Averaged)
            Match.run(config, self.avg_config, TestProblem, teams)


class Parsing(TestCase):
    """Testing the parsing of CLI and config files."""

    @classmethod
    def setUpClass(cls) -> None:
        path = Path(__file__).parent
        cls.problem_path = path / "testsproblem"
        cls.configs_path = path / "configs"

    def test_no_cfg_default(self):
        program_cfg, docker_cfg, match_cfg, wrapper_cfg = parse_cli_args([str(self.problem_path)])
        self.assertEqual(program_cfg.problem, self.problem_path)
        self.assertEqual(program_cfg.display, "logs")
        self.assertEqual(program_cfg.logs, Path.home() / ".algobattle_logs")
        self.assertEqual(
            program_cfg.teams, [TeamInfo("team_0", self.problem_path / "generator", self.problem_path / "solver")]
        )
        self.assertEqual(match_cfg, MatchConfig())
        self.assertEqual(wrapper_cfg, Iterated.Config())
        self.assertEqual(docker_cfg, DockerConfig())

    def test_empty_cfg(self):
        program_cfg, docker_cfg, match_cfg, wrapper_cfg = parse_cli_args(
            [str(self.problem_path), "--config", str(self.configs_path / "empty.toml")]
        )
        self.assertEqual(program_cfg.problem, self.problem_path)
        self.assertEqual(program_cfg.display, "logs")
        self.assertEqual(program_cfg.logs, Path.home() / ".algobattle_logs")
        self.assertEqual(
            program_cfg.teams, [TeamInfo("team_0", self.problem_path / "generator", self.problem_path / "solver")]
        )
        self.assertEqual(match_cfg, MatchConfig())
        self.assertEqual(wrapper_cfg, Iterated.Config())
        self.assertEqual(docker_cfg, DockerConfig())

    def test_cfg(self):
        program_cfg, docker_cfg, match_cfg, wrapper_cfg = parse_cli_args(
            [str(self.problem_path), "--config", str(self.configs_path / "test.toml")]
        )
        self.assertEqual(program_cfg.problem, self.problem_path)
        self.assertEqual(program_cfg.display, "logs")
        self.assertEqual(program_cfg.logs, Path.home() / ".algobattle_logs")
        self.assertEqual(
            program_cfg.teams, [TeamInfo("team_0", self.problem_path / "generator", self.problem_path / "solver")]
        )
        self.assertEqual(match_cfg, MatchConfig(points=10, safe_build=True, battle_type=Averaged))
        self.assertEqual(wrapper_cfg, Averaged.Config(iterations=1))
        self.assertEqual(docker_cfg, DockerConfig(generator=RunParameters(space=10)))

    def test_cli(self):
        program_cfg, docker_cfg, match_cfg, wrapper_cfg = parse_cli_args(
            [
                str(self.problem_path),
                "--points=10",
                "--space_generator=10",
                "--safe_build",
                "--battle_type=averaged",
                "--averaged_iterations=1",
            ]
        )
        self.assertEqual(program_cfg.problem, self.problem_path)
        self.assertEqual(program_cfg.display, "logs")
        self.assertEqual(program_cfg.logs, Path.home() / ".algobattle_logs")
        self.assertEqual(
            program_cfg.teams, [TeamInfo("team_0", self.problem_path / "generator", self.problem_path / "solver")]
        )
        self.assertEqual(match_cfg, MatchConfig(points=10, safe_build=True, battle_type=Averaged))
        self.assertEqual(wrapper_cfg, Averaged.Config(iterations=1))
        self.assertEqual(wrapper_cfg, Averaged.Config(iterations=1))
        self.assertEqual(docker_cfg, DockerConfig(generator=RunParameters(space=10)))

    def test_cli_overwrite_cfg(self):
        program_cfg, docker_cfg, match_cfg, wrapper_cfg = parse_cli_args(
            [
                str(self.problem_path),
                "--points=20",
                "--safe_build",
                "--battle_type=iterated",
                "--averaged_iterations=1",
                f"--config={self.configs_path / 'test.toml'}",
            ]
        )
        self.assertEqual(program_cfg.problem, self.problem_path)
        self.assertEqual(program_cfg.display, "logs")
        self.assertEqual(program_cfg.logs, Path.home() / ".algobattle_logs")
        self.assertEqual(
            program_cfg.teams, [TeamInfo("team_0", self.problem_path / "generator", self.problem_path / "solver")]
        )
        self.assertEqual(match_cfg, MatchConfig(points=20, safe_build=True, battle_type=Iterated))
        self.assertEqual(wrapper_cfg, Iterated.Config())
        self.assertEqual(docker_cfg, DockerConfig(generator=RunParameters(space=10)))

    def test_cli_no_problem_path(self):
        with self.assertRaises(SystemExit):
            parse_cli_args([])

    def test_cli_incorrect_wrapper(self):
        with self.assertRaises(SystemExit):
            parse_cli_args([str(self.problem_path), "--battle_type=NotAWrapperName"])

    def test_cfg_team(self):
        program_cfg, _, _, _ = parse_cli_args([str(self.problem_path), f"--config={self.configs_path / 'teams.toml'}"])
        self.assertEqual(program_cfg.teams, [TeamInfo("team 1", Path(), Path()), TeamInfo("team 2", Path(), Path())])

    def test_cfg_team_no_name(self):
        with self.assertRaises(ValueError):
            parse_cli_args([str(self.problem_path), f"--config={self.configs_path / 'teams_incorrect.toml'}"])


if __name__ == "__main__":
    main()
