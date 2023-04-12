"""Main battle script. Executes all possible types of battles, see battle --help for all options."""
from argparse import ArgumentParser, Namespace
from contextlib import ExitStack
import curses
from dataclasses import dataclass, field
from functools import partial
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, ClassVar, Mapping, ParamSpec, Self, TypeVar
import tomllib
from importlib.metadata import version as pkg_version

from prettytable import DOUBLE_BORDER, PrettyTable
from pydantic import validator
from anyio import create_task_group, run, sleep

from algobattle.battle import Battle, Fight, FightUiData
from algobattle.docker_util import DockerConfig, GeneratorResult, Image, ProgramError, ProgramResult, SolverResult
from algobattle.match import MatchConfig, Match, Ui
from algobattle.problem import Problem
from algobattle.team import Matchup, TeamHandler, TeamInfo
from algobattle.util import Role, TimerInfo, check_path, BaseModel, flat_intersperse


class ExecutionConfig(BaseModel):
    """Config data regarding program execution."""

    silent: bool = False
    safe_build: bool = False
    result_output: Path | None = None


class BattleConfig(BaseModel):
    """Pydantic model to parse the config file."""

    teams: list[TeamInfo] = []
    execution: ExecutionConfig = ExecutionConfig()
    match: MatchConfig = MatchConfig()
    docker: DockerConfig = DockerConfig()
    battle: dict[str, Battle.BattleConfig] = {n: b.BattleConfig() for n, b in Battle.all().items()}

    @property
    def battle_config(self) -> Battle.BattleConfig:
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
            out[name] = battle_cls.BattleConfig.parse_obj(data)
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
        BattleConfig._include_cli(self, cli, self._cli_mapping)
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
                BattleConfig._include_cli(value, cli, mapping.get(name, {}))
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


def parse_cli_args(args: list[str]) -> tuple[Path, BattleConfig]:
    """Parse a given CLI arg list into config objects."""
    parser = ArgumentParser()
    parser.add_argument("problem", type=check_path, help="Path to a folder with the problem file.")
    parser.add_argument(
        "--config", type=partial(check_path, type="file"), help="Path to a config file, defaults to '{problem} / config.toml'."
    )
    parser.add_argument("-s", "--silent", action="store_const", const=True, help="Disable the cli Ui.")
    parser.add_argument(
        "--result_output", type=check_path, help="If set, the match result object will be saved to the specified file."
    )

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
        for name, kwargs in battle.BattleConfig.as_argparse_args():
            group.add_argument(f"--{battle_name.lower()}_{name}", **kwargs)

    parsed = parser.parse_args(args)
    problem: Path = parsed.problem

    if parsed.battle_type is not None:
        parsed.battle_type = Battle.all()[parsed.battle_type]
    cfg_path: Path = parsed.config or parsed.problem / "config.toml"

    if cfg_path.is_file():
        try:
            config = BattleConfig.from_file(cfg_path)
        except Exception as e:
            raise ValueError(f"Invalid config file, terminating execution.\n{e}")
    else:
        config = BattleConfig()
    config.include_cli(parsed)
    if config.docker.advanced_run_params is not None:
        Image.run_kwargs = config.docker.advanced_run_params.to_docker_args()
    if config.docker.advanced_build_params is not None:
        Image.run_kwargs = config.docker.advanced_build_params.to_docker_args()

    if not config.teams:
        config.teams.append(TeamInfo(name="team_0", generator=problem / "generator", solver=problem / "solver"))

    return problem, config


async def _run_with_ui(
    match_config: MatchConfig, battle_config: Battle.BattleConfig, problem: type[Problem], teams: TeamHandler, ui: "CliUi | None"
) -> Match:
    async with create_task_group() as tg:
        if ui is not None:
            tg.start_soon(ui.loop)
        result = await Match.run(match_config, battle_config, problem, teams, ui)
        tg.cancel_scope.cancel()
        return result


def main():
    """Entrypoint of `algobattle` CLI."""
    try:
        problem_path, config = parse_cli_args(sys.argv[1:])

    except KeyboardInterrupt:
        raise SystemExit("Received keyboard interrupt, terminating execution.")

    try:
        problem = Problem.import_from_path(problem_path)
        with TeamHandler.build(
            config.teams, problem, config.docker, config.execution.safe_build
        ) as teams, ExitStack() as stack:
            if config.execution.silent:
                ui = None
            else:
                ui = CliUi()
                stack.enter_context(ui)

            result = run(_run_with_ui, config.match, config.battle_config, problem, teams, ui)
            print("\n".join(CliUi.display_match(result)))
            if config.match.points > 0:
                points = result.calculate_points(config.match.points)
                for team, pts in points.items():
                    print(f"Team {team} gained {pts:.1f} points.")
            if config.execution.result_output:
                t = datetime.now()
                filename = f"{t.year:04d}-{t.month:02d}-{t.day:02d}_{t.hour:02d}-{t.minute:02d}-{t.second:02d}.json"
                output_path = config.execution.result_output / filename
                json = result.json()
                with open(output_path, "w+") as f:
                    f.write(json)

    except KeyboardInterrupt:
        print("Received keyboard interrupt, terminating execution.")


P = ParamSpec("P")
R = TypeVar("R")


def check_for_terminal(function: Callable[P, R]) -> Callable[P, R | None]:
    """Ensure that we are attached to a terminal."""

    def wrapper(*args: P.args, **kwargs: P.kwargs):
        if not sys.stdout.isatty():
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

        for generating, battles in match.results.items():
            for solving, result in battles.items():
                if result.run_exception is None:
                    res = result.format_score(result.score())
                else:
                    res = f"Error: {result.run_exception}"
                table.add_row([generating, solving, res])

        return str(table).split("\n")

    @staticmethod
    def display_program(role: Role, data: TimerInfo | float | ProgramResult | None) -> str:
        """Formats program runtime data."""
        role_str = role.capitalize() + ": "
        out = f"{role_str: <11}"
        if data is None:
            return out

        if isinstance(data, TimerInfo):
            runtime = (datetime.now() - data.start).total_seconds()
            timeout = data.timeout
            state_glyph = "…"
        elif isinstance(data, float):
            runtime = data
            timeout = None
            state_glyph = "…"
        else:
            runtime = data.runtime
            timeout = data.params.timeout
            state_glyph = "🗙" if isinstance(data.result, ProgramError) else "✓"

        out += f"{runtime:3.1f}s"
        if timeout is None:
            out += "         "  # same length padding as timeout info string
        else:
            out += f" / {timeout:3.1f}s"

        out += f" {state_glyph}"
        return out

    def display_current_fight(self, matchup: Matchup) -> list[str]:
        """Formats the current fight of a battle into a compact overview."""
        fight = self.fight_data[matchup]
        return [
            f"Current fight at size {fight.size}:",
            self.display_program("generator", fight.generator),
            self.display_program("solver", fight.solver),
        ]

    @staticmethod
    def display_fight(fight: Fight, index: int) -> list[str]:
        """Formats a completed fight into a compact overview."""
        out = [f"Fight {index} at size {fight.generator.size}:"]
        if isinstance(fight.generator.result, ProgramError):
            out.append("Generator failed!")
            return out
        assert fight.solver is not None
        if isinstance(fight.solver.result, ProgramError):
            out.append("Solver failed!")
            return out
        out.append(f"Score: {fight.score}")
        return out

    def display_battle(self, matchup: Matchup) -> list[str]:
        """Formats the battle data into a string that can be printed to the terminal."""
        battle = self.match.results[matchup.generator.name][matchup.solver.name]
        fights = battle.fight_results[-3:] if len(battle.fight_results) >= 3 else battle.fight_results
        sections: list[list[str]] = []

        if matchup in self.battle_data:
            sections.append([f"{key}: {val}" for key, val in self.battle_data[matchup].dict().items()])

        if matchup in self.fight_data:
            sections.append(self.display_current_fight(matchup))

        if fights:
            fight_history: list[list[str]] = []
            for i, fight in enumerate(fights, max(len(battle.fight_results) - 2, 1)):
                fight_history.append(self.display_fight(fight, i))
            fight_history = fight_history[::-1]
            fight_display = [
                "Most recent fights:",
            ] + list(flat_intersperse(fight_history, ""))
            sections.append(fight_display)

        combined_sections = list(flat_intersperse(sections, ""))
        return [
            f"Battle {matchup.generator.name} vs {matchup.solver.name}:",
        ] + combined_sections


if __name__ == "__main__":
    main()
