"""Main battle script. Executes all possible types of battles, see battle --help for all options."""
from argparse import ArgumentParser, Namespace
from contextlib import ExitStack
import curses
from dataclasses import dataclass, field
from functools import partial
import sys
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, ClassVar, Literal, Mapping, ParamSpec, Self, TypeVar
import tomllib
from importlib.metadata import version as pkg_version
from prettytable import DOUBLE_BORDER, PrettyTable

from pydantic import BaseModel, validator
from anyio import create_task_group, run, sleep

from algobattle.battle import Battle, FightUiData
from algobattle.docker_util import DockerConfig, GeneratorResult, Image, ProgramError, SolverResult
from algobattle.match import MatchConfig, Match, Ui
from algobattle.problem import Problem
from algobattle.team import Matchup, TeamHandler, TeamInfo
from algobattle.util import Role, TimerInfo, check_path

logger = logging.getLogger("algobattle.cli")


def setup_logging(logging_path: Path, verbose_logging: bool, silent: bool):
    """Creates and returns a parent logger.

    Parameters
    ----------
    logging_path : Path
        Path to folder where the logfile should be stored at.
    verbose_logging : bool
        Flag indicating whether to include debug messages in the output
    silent : bool
        Flag indicating whether not to pipe the logging output to stderr.

    Returns
    -------
    logger : Logger
        The Logger object.
    """
    common_logging_level = logging.INFO

    if verbose_logging:
        common_logging_level = logging.DEBUG

    Path(logging_path).mkdir(exist_ok=True)

    t = datetime.now()
    current_timestamp = f"{t.year:04d}-{t.month:02d}-{t.day:02d}_{t.hour:02d}-{t.minute:02d}-{t.second:02d}"
    logging_path = Path(logging_path, current_timestamp + ".log")

    logging.basicConfig(
        handlers=[logging.FileHandler(logging_path, "w", "utf-8")],
        level=common_logging_level,
        format="%(asctime)s %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    logger = logging.getLogger("algobattle")

    if not silent:
        # Pipe logging out to console
        _consolehandler = logging.StreamHandler(stream=sys.stderr)
        _consolehandler.setLevel(common_logging_level)

        _consolehandler.setFormatter(logging.Formatter("%(message)s"))

        logger.addHandler(_consolehandler)

    logger.info(f"You can find the log files for this run in {logging_path}")
    return logger


class ExecutionConfig(BaseModel):
    """Config data regarding program execution."""

    display: Literal["silent", "logs", "ui"] = "ui"
    logging_path: Path = Path.home() / ".algobattle_logs"
    verbose: bool = False
    safe_build: bool = False


class Config(BaseModel):
    """Pydantic model to parse the config file."""

    teams: list[TeamInfo] = []
    execution: ExecutionConfig = ExecutionConfig()
    match: MatchConfig = MatchConfig()
    docker: DockerConfig = DockerConfig()
    battle: dict[str, Battle.Config] = {n: b.Config() for n, b in Battle.all().items()}

    @property
    def battle_config(self) -> Battle.Config:
        """The config object for the used battle type."""
        return self.battle[self.match.battle_type.name().lower()]

    @validator("battle", pre=True)
    def val_battle_configs(cls, vals):
        """Parses the dict of battle configs into their corresponding config objects."""
        battle_types = Battle.all()
        if not isinstance(vals, Mapping):
            raise TypeError
        out = {}
        for name, battle_cls in battle_types.items():
            data = vals.get(name, {})
            out[name] = battle_cls.Config.parse_obj(data)
        return out

    _cli_mapping: ClassVar[dict[str, Any]] = {
        "teams": None,
        "battle": None,
        "docker": {
            "generator": {"timeout": "generator_timeout", "space": "generator_space", "cpus": "generator_cpus"},
            "solver": {"timeout": "solver_timeout", "space": "solver_space", "cpus": "solver_cpus"},
            "advanced_run_params": None,
            "advanced_build_params": None,
        },
    }

    def include_cli(self, cli: Namespace) -> None:
        """Updates itself using the data in the passed argparse namespace."""
        Config._include_cli(self, cli, self._cli_mapping)
        for battle_name, config in self.battle.items():
            for name in config.__fields__:
                cli_name = f"{battle_name}_{name}"
                if getattr(cli, cli_name) is not None:
                    setattr(config, name, getattr(cli, cli_name))

    @staticmethod
    def _include_cli(model: BaseModel, cli: Namespace, mapping: dict[str, Any]) -> None:
        for name in model.__fields__:
            if name in mapping and mapping[name] is None:
                continue
            value = getattr(model, name)
            if isinstance(value, BaseModel):
                Config._include_cli(value, cli, mapping.get(name, {}))
            else:
                cli_val = getattr(cli, mapping.get(name, name))
                if cli_val is not None:
                    setattr(model, name, cli_val)

    @classmethod
    def from_file(cls, file: Path) -> Self:
        """Parses a config object from a toml file."""
        if not file.is_file():
            raise ValueError("Path doesn't point to a file.")
        with open(file, "rb") as f:
            try:
                config_dict = tomllib.load(f)
            except tomllib.TOMLDecodeError as e:
                raise ValueError(f"The config file at {file} is not a properly formatted TOML file!\n{e}")
        return cls.parse_obj(config_dict)


def parse_cli_args(args: list[str]) -> tuple[Path, Config]:
    """Parse a given CLI arg list into config objects."""
    parser = ArgumentParser()
    parser.add_argument("problem", type=check_path, help="Path to a folder with the problem file.")
    parser.add_argument(
        "--config", type=partial(check_path, type="file"), help="Path to a config file, defaults to '{problem} / config.toml'."
    )
    parser.add_argument(
        "--logging_path",
        type=partial(check_path, type="dir"),
        help="Folder that logs are written into, defaults to '~/.algobattle_logs'.",
    )
    parser.add_argument(
        "--display",
        choices=["silent", "logs", "ui"],
        help="Choose output mode, silent disables all output, logs displays the battle logs on STDERR,"
        " ui displays a small GUI showing the progress of the battle. Default: ui.",
    )

    parser.add_argument("--verbose", "-v", dest="verbose", action="store_const", const=True, help="More detailed log output.")
    parser.add_argument(
        "--safe_build",
        action="store_const",
        const=True,
        help="Isolate docker image builds from each other. Significantly slows down battle setup"
        " but prevents images from interfering with each other.",
    )

    parser.add_argument("--battle_type", choices=[name.lower() for name in Battle.all()], help="Type of battle to be used.")
    parser.add_argument(
        "--parallel_battles",
        type=int,
        help="Number of battles that are executed in parallel.",
    )
    parser.add_argument("--points", type=int, help="number of points distributed between teams.")

    parser.add_argument("--build_timeout", type=float, help="Timeout for the build step of each docker image.")
    parser.add_argument("--generator_timeout", type=float, help="Time limit for the generator execution.")
    parser.add_argument("--solver_timeout", type=float, help="Time limit for the solver execution.")
    parser.add_argument("--generator_space", type=int, help="Memory limit for the generator execution, in MB.")
    parser.add_argument("--solver_space", type=int, help="Memory limit the solver execution, in MB.")
    parser.add_argument("--generator_cpus", type=int, help="Number of cpu cores used for generator container execution.")
    parser.add_argument("--solver_cpus", type=int, help="Number of cpu cores used for solver container execution.")

    # battle types have their configs automatically added to the CLI args
    for battle_name, battle in Battle.all().items():
        group = parser.add_argument_group(battle_name)
        for name, kwargs in battle.Config.as_argparse_args():
            group.add_argument(f"--{battle_name.lower()}_{name}", **kwargs)

    parsed = parser.parse_args(args)
    problem: Path = parsed.problem

    if parsed.battle_type is not None:
        parsed.battle_type = Battle.all()[parsed.battle_type]
    cfg_path: Path = parsed.config or parsed.problem / "config.toml"

    if cfg_path.is_file():
        try:
            config = Config.from_file(cfg_path)
        except Exception as e:
            raise ValueError(f"Invalid config file, terminating execution.\n{e}")
    else:
        config = Config()
    config.include_cli(parsed)
    if config.docker.advanced_run_params is not None:
        Image.run_kwargs = config.docker.advanced_run_params.to_docker_args()
    if config.docker.advanced_build_params is not None:
        Image.run_kwargs = config.docker.advanced_build_params.to_docker_args()

    if not config.teams:
        config.teams.append(TeamInfo(name="team_0", generator=problem / "generator", solver=problem / "solver"))

    return problem, config


async def _run_with_ui(
    match_config: MatchConfig, battle_config: Battle.Config, problem: type[Problem], teams: TeamHandler, ui: "CliUi"
):
    async with create_task_group() as tg:
        tg.start_soon(ui.loop)
        result = await Match.run(match_config, battle_config, problem, teams, ui)
        tg.cancel_scope.cancel()
        return result


def main():
    """Entrypoint of `algobattle` CLI."""
    try:
        problem_path, config = parse_cli_args(sys.argv[1:])
        logger = setup_logging(config.execution.logging_path, config.execution.verbose, config.execution.display != "logs")

    except KeyboardInterrupt:
        raise SystemExit("Received keyboard interrupt, terminating execution.")

    try:
        problem = Problem.import_from_path(problem_path)
        with TeamHandler.build(
            config.teams, problem, config.docker, config.execution.safe_build
        ) as teams, ExitStack() as stack:
            if config.execution.display == "ui":
                ui = CliUi()
                stack.enter_context(ui)
            else:
                ui = None

            result = run(_run_with_ui, config.match, config.battle_config, problem, teams, ui)

            logger.info("#" * 78)
            logger.info(CliUi.display_match(result))
            print("\n".join(CliUi.display_match(result)))
            if config.match.points > 0:
                points = result.calculate_points()
                for team, pts in points.items():
                    line = f"Team {team} gained {pts:.1f} points."
                    print(line)
                    logger.info(line)

    except KeyboardInterrupt:
        logger.critical("Received keyboard interrupt, terminating execution.")


P = ParamSpec("P")
R = TypeVar("R")


def check_for_terminal(function: Callable[P, R]) -> Callable[P, R | None]:
    """Ensure that we are attached to a terminal."""

    def wrapper(*args: P.args, **kwargs: P.kwargs):
        if not sys.stdout.isatty():
            logger.error("Not attached to a terminal.")
            return None
        else:
            return function(*args, **kwargs)

    return wrapper


@dataclass
class CliUi(Ui):
    """A Ui displaying the data to the cli."""

    battle_data: dict[Matchup, Battle.UiData] = field(default_factory=dict, init=False)
    fight_data: dict[Matchup, FightUiData] = field(default_factory=dict, init=False)

    @check_for_terminal
    def __enter__(self) -> Self:
        self.match_result: Any = None
        self.battle_info: Any = None
        self.stdscr = curses.initscr()
        curses.cbreak()
        curses.noecho()
        self.stdscr.keypad(True)
        return self

    @check_for_terminal
    def __exit__(self, _type, _value, _traceback):
        """Restore the console."""
        curses.nocbreak()
        self.stdscr.keypad(False)
        curses.echo()
        curses.endwin()

    @check_for_terminal
    def battle_completed(self, matchup: Matchup) -> None:
        """Notifies the Ui that a specific battle has been completed."""
        self.battle_data.pop(matchup, None)
        self.fight_data.pop(matchup, None)

    def update_battle_data(self, matchup: Matchup, data: Battle.UiData) -> None:
        """Passes new custom battle data to the Ui."""
        self.battle_data[matchup] = data

    def start_fight(self, matchup: Matchup, size: int) -> None:
        """Informs the Ui of a newly started fight."""
        self.fight_data[matchup] = FightUiData(size, None, None)

    def update_curr_fight(
        self,
        matchup: Matchup,
        role: Role | None = None,
        data: TimerInfo | float | GeneratorResult | SolverResult | None = None,
    ) -> None:
        """Passes new info about the current fight to the Ui."""
        if role == "generator" or role is None:
            assert not isinstance(data, SolverResult)
            self.fight_data[matchup].generator = data
        if role == "solver" or role is None:
            assert not isinstance(data, GeneratorResult)
            self.fight_data[matchup].solver = data

    async def loop(self) -> None:
        """Periodically updates the Ui with the current match info."""
        while True:
            self.update()
            await sleep(0.1)

    @check_for_terminal
    def update(self) -> None:
        """Disaplys the current status of the match to the cli."""
        terminal_height, _ = self.stdscr.getmaxyx()
        out: list[str] = []
        out.append(f"Algobattle version {pkg_version(__package__)}")
        out += self.display_match(self.match)
        for matchup in self.active_battles:
            out += [
                "",
                "",
                f"{matchup.generator.name} vs {matchup.solver.name}",
            ] + self.display_battle(matchup)

        if len(out) > terminal_height:
            out = out[:terminal_height]
        self.stdscr.clear()
        self.stdscr.addstr(0, 0, "\n".join(out))
        self.stdscr.refresh()
        self.stdscr.nodelay(True)

        # on windows curses swallows the ctrl+C event, we need to manually check for the control sequence
        c = self.stdscr.getch()
        if c == 3:
            raise KeyboardInterrupt
        else:
            curses.flushinp()

    @staticmethod
    def display_match(match: Match) -> list[str]:
        """Formats the match data into a table that can be printed to the terminal."""
        table = PrettyTable(field_names=["Generator", "Solver", "Result"], min_width=5)
        table.set_style(DOUBLE_BORDER)
        table.align["Result"] = "r"

        for matchup, result in match.results.items():
            table.add_row([str(matchup.generator), str(matchup.solver), result.format_score(result.score())])

        return [f"Battle Type: {match.config.battle_type.name()}"] + list(str(table).split("\n"))

    def display_current_fight(self, matchup: Matchup) -> list[str]:
        """Formats the current fight of a battle into a compact overview."""
        fight = self.fight_data[matchup]
        out = [
            f"Current fight at size {fight.size}:",
        ]
        if fight.generator is not None:
            out.append("Generator:")
            if isinstance(fight.generator, TimerInfo):
                runtime_info = str(round((datetime.now() - fight.generator.start).total_seconds(), 1))
                if fight.generator.timeout is not None:
                    runtime_info += f"/{round(fight.generator.timeout, 1)}"
                out.append(f"Currently running... ({runtime_info})")
            elif isinstance(fight.generator, float):
                out.append(f"Runtime: {fight.generator}")
            else:
                out.append(f"Runtime: {fight.generator.runtime}")
                if isinstance(fight.generator.result, ProgramError):
                    out.append("Failed!")
                    out.append(str(fight.generator.result))
                else:
                    out.append("Ran successfully.")
        if fight.solver is not None:
            out.append("Solver:")
            if isinstance(fight.solver, TimerInfo):
                runtime_info = str(round((datetime.now() - fight.solver.start).total_seconds(), 1))
                if fight.solver.timeout is not None:
                    runtime_info += f"/{round(fight.solver.timeout, 1)}"
                out.append(f"Currently running... ({runtime_info})")
            elif isinstance(fight.solver, float):
                out.append(f"Runtime: {fight.solver}")
            else:
                out.append(f"Runtime: {fight.solver.runtime}")
                if isinstance(fight.solver.result, Problem.Solution):
                    out.append("Ran successfully.")
                else:
                    out.append("Failed!")
                    out.append(str(fight.solver.result))
        return out

    def display_battle(self, matchup: Matchup) -> list[str]:
        """Formats the battle data into a string that can be printed to the terminal."""
        battle = self.match.results[matchup]
        fights = battle.fight_results[-3:] if len(battle.fight_results) >= 3 else battle.fight_results
        out = []

        if matchup in self.battle_data:
            out += [""] + [f"{key}: {val}" for key, val in self.battle_data[matchup].dict().items()]

        if matchup in self.fight_data:
            out += self.display_current_fight(matchup)

        for i, fight in enumerate(fights, max(len(battle.fight_results) - 2, 1)):
            out += [
                "",
                f"Fight {i} at size {fight.generator.size}:",
            ]
            if isinstance(fight.generator.result, ProgramError):
                out.append("Generator failed!")
                out.append(str(fight.generator.result))
            elif isinstance(fight.solver, ProgramError):
                out.append("Solver failed!")
                out.append(str(fight.solver.result))
            else:
                out.append("Successful fight")
            out.append(f"Score: {fight.score}")

        return out


if __name__ == "__main__":
    main()
