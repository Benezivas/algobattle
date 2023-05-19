"""Cli entrypoint to execute matches.

Provides a command line interface to start matches and observe them. See `battle --help` for further options.
"""
from argparse import ArgumentParser
import curses
from dataclasses import dataclass, field
from functools import partial
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable, ParamSpec, Self, TypeVar
from importlib.metadata import version as pkg_version

from prettytable import DOUBLE_BORDER, PrettyTable
from anyio import create_task_group, run, sleep
from anyio.abc import TaskGroup

from algobattle.battle import Battle, Fight
from algobattle.docker_util import GeneratorResult, ProgramRunInfo, SolverResult
from algobattle.match import BaseConfig, Match, Ui
from algobattle.problem import Problem
from algobattle.team import Matchup, TeamInfo
from algobattle.util import Role, TimerInfo, check_path, flat_intersperse


@dataclass
class CliOptions:
    """Options used by the cli."""

    problem: type[Problem]
    silent: bool = False
    result: Path | None = None


def parse_cli_args(args: list[str]) -> tuple[CliOptions, BaseConfig]:
    """Parse a given CLI arg list into config objects."""
    parser = ArgumentParser()
    parser.add_argument("problem", help="Either the name of an installed problem, or a path to a problem file.")
    parser.add_argument(
        "--config",
        "-c",
        type=partial(check_path, type="file"),
        help="Path to a config file, defaults to '{problem} / config.toml'.",
    )
    parser.add_argument("--silent", "-s", action="store_true", help="Disable the cli Ui.")
    parser.add_argument(
        "--result", "-r", type=check_path, help="If set, the match result object will be saved to the specified file."
    )

    parsed = parser.parse_args(args)
    installed_problems = Problem.all()
    if parsed.problem in installed_problems:
        problem = installed_problems[parsed.problem]
        base_path = Path()
    else:
        problem_path = Path(parsed.problem)
        if not problem_path.exists():
            raise ValueError(
                f"Passed argument '{parsed.problem}' is neither the name of an installed problem nor a path to one."
            )
        problem = Problem.import_from_path(problem_path)
        base_path = problem_path

    exec_config = CliOptions(
        problem=problem,
        silent=parsed.silent,
        result=parsed.result,
    )
    cfg_path: Path = parsed.config or base_path / "config.toml"

    if cfg_path.is_file():
        try:
            config = BaseConfig.from_file(cfg_path)
        except Exception as e:
            raise ValueError(f"Invalid config file, terminating execution.\n{e}")
    else:
        config = BaseConfig()

    if not config.teams:
        config.teams["team_0"] = TeamInfo(generator=base_path / "generator", solver=base_path / "solver")

    return exec_config, config


async def _run_with_ui(
    match_config: BaseConfig,
    problem: type[Problem],
) -> Match:
    async with CliUi() as ui:
        return await Match.run(match_config, problem, ui)


def main():
    """Entrypoint of `algobattle` CLI."""
    try:
        exec_config, config = parse_cli_args(sys.argv[1:])

        if exec_config.silent:
            result = run(Match.run, config, exec_config.problem)
        else:
            result = run(_run_with_ui, config, exec_config.problem)
        print("\n".join(CliUi.display_match(result)))

        if config.match.points > 0:
            points = result.calculate_points(config.match.points)
            for team, pts in points.items():
                print(f"Team {team} gained {pts:.1f} points.")

        if exec_config.result is not None:
            t = datetime.now()
            filename = f"{t.year:04d}-{t.month:02d}-{t.day:02d}_{t.hour:02d}-{t.minute:02d}-{t.second:02d}.json"
            with open(exec_config.result / filename, "w+") as f:
                f.write(result.json())

    except KeyboardInterrupt:
        raise SystemExit("Received keyboard interrupt, terminating execution.")


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
class _BuildInfo:
    team: str
    role: Role
    timeout: float | None
    start: datetime


@dataclass
class _FightUiData:
    size: int
    generator: TimerInfo | float | ProgramRunInfo | None = None
    solver: TimerInfo | float | ProgramRunInfo | None = None


@dataclass
class CliUi(Ui):
    """A :cls:`Ui` displaying the data to the cli.

    Uses curses to continually draw a basic text based ui to the terminal.
    """

    battle_data: dict[Matchup, Battle.UiData] = field(default_factory=dict, init=False)
    fight_data: dict[Matchup, _FightUiData] = field(default_factory=dict, init=False)
    task_group: TaskGroup | None = field(default=None, init=False)
    build_status: _BuildInfo | str | None = field(default=None, init=False)

    async def __aenter__(self) -> Self:
        self.stdscr = curses.initscr()
        curses.cbreak()
        curses.noecho()
        self.stdscr.keypad(True)

        self.task_group = create_task_group()
        await self.task_group.__aenter__()
        self.task_group.start_soon(self.loop)

        return self

    async def __aexit__(self, _type, _value, _traceback) -> None:
        """Restore the console."""
        if self.task_group is not None:
            self.task_group.cancel_scope.cancel()
            await self.task_group.__aexit__(_type, _value, _traceback)

        curses.nocbreak()
        self.stdscr.keypad(False)
        curses.echo()
        curses.endwin()

    def start_build(self, team: str, role: Role, timeout: float | None) -> None:
        """Informs the ui that a new program is being built."""
        self.build_status = _BuildInfo(team, role, timeout, datetime.now())

    def finish_build(self) -> None:
        """Informs the ui that the current build has been finished."""
        self.build_status = None

    @check_for_terminal
    def battle_completed(self, matchup: Matchup) -> None:
        """Notifies the Ui that a specific battle has been completed."""
        self.battle_data.pop(matchup, None)
        self.fight_data.pop(matchup, None)
        super().battle_completed(matchup)

    def update_battle_data(self, matchup: Matchup, data: Battle.UiData) -> None:
        """Passes new custom battle data to the Ui."""
        self.battle_data[matchup] = data

    def start_fight(self, matchup: Matchup, size: int) -> None:
        """Informs the Ui of a newly started fight."""
        self.fight_data[matchup] = _FightUiData(size, None, None)

    def update_curr_fight(
        self,
        matchup: Matchup,
        role: Role | None = None,
        data: TimerInfo | float | ProgramRunInfo | None = None,
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
        status = self.build_status
        if isinstance(status, str):
            out.append(status)
        elif isinstance(status, _BuildInfo):
            runtime = (datetime.now() - status.start).total_seconds()
            status_str = f"Building {status.role} of team {status.team}: {runtime:3.1f}s"
            if status.timeout is not None:
                status_str += f" / {status.timeout:3.1f}s"
            out.append(status_str)

        if self.match is not None:
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
    def display_program(role: Role, data: TimerInfo | float | ProgramRunInfo | None) -> str:
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
            state_glyph = "✓" if data.error is None else "🗙"

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
    def display_fight(fight: Fight, index: int) -> str:
        """Formats a completed fight into a compact overview."""
        if fight.generator.error is not None:
            exec_info = ", generator failed!"
        elif fight.solver is not None and fight.solver.error is not None:
            exec_info = ", solver failed!"
        else:
            exec_info = ""
        return f"Fight {index} at size {fight.max_size}: {fight.score}{exec_info}"

    def display_battle(self, matchup: Matchup) -> list[str]:
        """Formats the battle data into a string that can be printed to the terminal."""
        if self.match is None:
            return []
        battle = self.match.results[matchup.generator.name][matchup.solver.name]
        fights = battle.fight_results[-3:] if len(battle.fight_results) >= 3 else battle.fight_results
        sections: list[list[str]] = []

        if matchup in self.battle_data:
            sections.append([f"{key}: {val}" for key, val in self.battle_data[matchup].dict().items()])

        if matchup in self.fight_data:
            sections.append(self.display_current_fight(matchup))

        if fights:
            fight_history: list[str] = []
            for i, fight in enumerate(fights, max(len(battle.fight_results) - 2, 1)):
                fight_history.append(self.display_fight(fight, i))
            fight_display = [
                "Most recent fight results:",
            ] + fight_history[::-1]
            sections.append(fight_display)

        combined_sections = list(flat_intersperse(sections, ""))
        return [
            f"Battle {matchup.generator.name} vs {matchup.solver.name}:",
        ] + combined_sections


if __name__ == "__main__":
    main()
