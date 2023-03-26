"""Tests for the Match class."""
# pyright: reportMissingSuperCall=false
from unittest import TestCase, main
import logging
from pathlib import Path

from algobattle.cli import Config, ExecutionConfig, parse_cli_args, setup_logging
from algobattle.battle import Iterated, Averaged
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
        match = Match(MatchConfig(), Iterated.Config(), TestProblem, self.teams)
        self.assertEqual(match.calculate_points(), {self.team0.name: 0, self.team1.name: 0})

    def test_calculate_points_iterated_no_successful_round(self):
        """Two teams should get an equal amount of points if nobody solved anything."""
        match = Match(MatchConfig(), Iterated.Config(), TestProblem, self.teams)
        battle = Iterated()
        battle.reached = 0
        match.results[self.matchup0] = battle
        match.results[self.matchup1] = battle
        self.assertEqual(match.calculate_points(), {self.team0.name: 50, self.team1.name: 50})

    def test_calculate_points_iterated_draw(self):
        """Two teams should get an equal amount of points if both solved a problem equally well."""
        match = Match(MatchConfig(), Iterated.Config(), TestProblem, self.teams)
        battle = Iterated()
        battle.reached = 20
        match.results[self.matchup0] = battle
        match.results[self.matchup1] = battle
        self.assertEqual(match.calculate_points(), {self.team0.name: 50, self.team1.name: 50})

    def test_calculate_points_iterated_domination(self):
        """One team should get all points if it solved anything and the other team nothing."""
        match = Match(MatchConfig(), Iterated.Config(), TestProblem, self.teams)
        battle = Iterated()
        battle.reached = 10
        battle2 = Iterated()
        battle2.reached = 0
        match.results[self.matchup0] = battle
        match.results[self.matchup1] = battle2
        self.assertEqual(match.calculate_points(), {self.team0.name: 0, self.team1.name: 100})

    def test_calculate_points_iterated_one_team_better(self):
        """One team should get more points than the other if it performed better."""
        match = Match(MatchConfig(), Iterated.Config(), TestProblem, self.teams)
        battle = Iterated()
        battle.reached = 10
        battle2 = Iterated()
        battle2.reached = 20
        match.results[self.matchup0] = battle
        match.results[self.matchup1] = battle2
        self.assertEqual(match.calculate_points(), {self.team0.name: 66.6, self.team1.name: 33.4})

    def test_calculate_points_averaged_no_successful_round(self):
        """Two teams should get an equal amount of points if nobody solved anything."""
        match = Match(MatchConfig(battle_type=Averaged), Averaged.Config(), TestProblem, self.teams)
        battle = Averaged()
        battle.scores = [0, 0, 0]
        match.results[self.matchup0] = battle
        match.results[self.matchup1] = battle
        self.assertEqual(match.calculate_points(), {self.team0.name: 50, self.team1.name: 50})

    def test_calculate_points_averaged_draw(self):
        """Two teams should get an equal amount of points if both solved a problem equally well."""
        match = Match(MatchConfig(battle_type=Averaged), Averaged.Config(), TestProblem, self.teams)
        battle = Averaged()
        battle.scores = [.5, .5, .5]
        match.results[self.matchup0] = battle
        match.results[self.matchup1] = battle
        self.assertEqual(match.calculate_points(), {self.team0.name: 50, self.team1.name: 50})

    def test_calculate_points_averaged_domination(self):
        """One team should get all points if it solved anything and the other team nothing."""
        match = Match(MatchConfig(battle_type=Averaged), Averaged.Config(), TestProblem, self.teams)
        battle = Averaged()
        battle.scores = [0, 0, 0]
        battle2 = Averaged()
        battle2.scores = [1, 1, 1]
        match.results[self.matchup0] = battle
        match.results[self.matchup1] = battle2
        self.assertEqual(match.calculate_points(), {self.team0.name: 100, self.team1.name: 0})

    def test_calculate_points_averaged_one_team_better(self):
        """One team should get more points than the other if it performed better."""
        match = Match(MatchConfig(battle_type=Averaged), Averaged.Config(), TestProblem, self.teams)
        battle = Averaged()
        battle.scores = [.6, .6, .6]
        battle2 = Averaged()
        battle2.scores = [.4, .4, .4]
        match.results[self.matchup0] = battle
        match.results[self.matchup1] = battle2
        self.assertEqual(match.calculate_points(), {self.team0.name: 60, self.team1.name: 40})

    # TODO: Add tests for remaining functions


class Execution(TestCase):
    """Some basic tests for the execution of the battles."""

    @classmethod
    def setUpClass(cls) -> None:
        logging.disable(logging.NOTSET)  # reenable logging
        setup_logging(Path.home() / ".algobattle_logs", verbose_logging=True, silent=False)
        problem_path = Path(__file__).parent / "testsproblem"
        cls.problem = TestProblem
        cls.config = MatchConfig()
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
            config = MatchConfig(battle_type=Averaged)
            Match.run(config, self.avg_config, TestProblem, teams)


class Parsing(TestCase):
    """Testing the parsing of CLI and config files."""

    @classmethod
    def setUpClass(cls) -> None:
        path = Path(__file__).parent
        cls.problem_path = path / "testsproblem"
        cls.configs_path = path / "configs"
        cls.teams = [TeamInfo(
            name="team_0",
            generator=cls.problem_path / "generator",
            solver=cls.problem_path / "solver",
        )]

    def test_no_cfg_default(self):
        problem, cfg = parse_cli_args([str(self.problem_path)])
        self.assertEqual(problem, self.problem_path)
        self.assertEqual(cfg, Config(teams=self.teams))
        self.assertEqual(cfg.battle_config, Iterated.Config())

    def test_empty_cfg(self):
        problem, cfg = parse_cli_args(
            [str(self.problem_path), "--config", str(self.configs_path / "empty.toml")]
        )
        self.assertEqual(problem, self.problem_path)
        self.assertEqual(cfg, Config(teams=self.teams))
        self.assertEqual(cfg.battle_config, Iterated.Config())

    def test_cfg(self):
        problem, cfg = parse_cli_args(
            [str(self.problem_path), "--config", str(self.configs_path / "test.toml")]
        )
        self.assertEqual(problem, self.problem_path)
        self.assertEqual(cfg, Config(
            match=MatchConfig(
                points=10,
                battle_type=Averaged,
            ),
            teams=self.teams,
            execution=ExecutionConfig(safe_build=True),
            docker=DockerConfig(generator=RunParameters(space=10)),
            battle={
                "averaged": Averaged.Config(iterations=1),
            }
        ))

    def test_cli(self):
        problem, cfg = parse_cli_args(
            [
                str(self.problem_path),
                "--points=10",
                "--generator_space=10",
                "--safe_build",
                "--battle_type=averaged",
                "--averaged_iterations=1",
            ]
        )
        self.assertEqual(problem, self.problem_path)
        self.assertEqual(cfg, Config(
            match=MatchConfig(
                points=10,
                battle_type=Averaged,
            ),
            teams=self.teams,
            execution=ExecutionConfig(safe_build=True),
            docker=DockerConfig(generator=RunParameters(space=10)),
            battle={
                "averaged": Averaged.Config(iterations=1),
            },
        ))

    def test_cli_overwrite_cfg(self):
        problem, cfg = parse_cli_args(
            [
                str(self.problem_path),
                "--points=20",
                "--safe_build",
                "--battle_type=iterated",
                "--averaged_iterations=1",
                f"--config={self.configs_path / 'test.toml'}",
            ]
        )
        self.assertEqual(problem, self.problem_path)
        self.assertEqual(cfg, Config(
            match=MatchConfig(
                points=20,
                battle_type=Iterated,
            ),
            teams=self.teams,
            execution=ExecutionConfig(safe_build=True),
            docker=DockerConfig(generator=RunParameters(space=10)),
            battle={
                "averaged": Averaged.Config(iterations=1),
            },
        ))

    def test_cli_no_problem_path(self):
        with self.assertRaises(SystemExit):
            parse_cli_args([])

    def test_cli_incorrect_battle_type(self):
        with self.assertRaises(SystemExit):
            parse_cli_args([str(self.problem_path), "--battle_type=NotABattleType"])

    def test_cfg_team(self):
        _, cfg = parse_cli_args([str(self.problem_path), f"--config={self.configs_path / 'teams.toml'}"])
        self.assertEqual(cfg, Config(
            teams=[TeamInfo("team 1", Path(), Path()), TeamInfo("team 2", Path(), Path())]
        ))

    def test_cfg_team_no_name(self):
        with self.assertRaises(ValueError):
            parse_cli_args([str(self.problem_path), f"--config={self.configs_path / 'teams_incorrect.toml'}"])


if __name__ == "__main__":
    main()
