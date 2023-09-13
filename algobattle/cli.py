"""Cli entrypoint to execute matches.

Provides a command line interface to start matches and observe them. See `battle --help` for further options.
"""
from argparse import ArgumentParser
from types import TracebackType
import curses
from dataclasses import dataclass, field
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable, ParamSpec, Self, TypeVar
from importlib.metadata import version as pkg_version

from prettytable import DOUBLE_BORDER, PrettyTable
from anyio import create_task_group, run, sleep
from anyio.abc import TaskGroup

from algobattle.battle import Battle, Fight
from algobattle.match import Match, Ui, AlgobattleConfig
from algobattle.problem import AnyProblem, Problem
from algobattle.team import Matchup
from algobattle.util import Role, RunningTimer, flat_intersperse


@dataclass
class CliOptions:
    """Options used by the cli."""

    problem: AnyProblem
    silent: bool = False
    result: Path | None = None


def parse_cli_args(args: list[str]) -> tuple[CliOptions, AlgobattleConfig]:
    """Parse a given CLI arg list into config objects."""
    parser = ArgumentParser()
    parser.add_argument(
        "path",
        type=Path,
        help="Path to either a config file or a directory containing one and/or the other necessary files.",
    )
    parser.add_argument("--silent", "-s", action="store_true", help="Disable the cli Ui.")
    parser.add_argument(
        "--result", "-r", type=Path, help="If set, the match result object will be saved to the specified file."
    )

    parsed = parser.parse_args(args)
    path: Path = parsed.path
    if not path.exists():
        raise ValueError("Passed path does not exist.")
    if path.is_dir():
        path /= "config.toml"

    config = AlgobattleConfig.from_file(path)
    problem = Problem.get(config.match.problem)

    exec_config = CliOptions(
        problem=problem,
        silent=parsed.silent,
        result=parsed.result,
    )

    return exec_config, config


async def _run_with_ui(
    match_config: AlgobattleConfig,
    problem: AnyProblem,
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

        if config.execution.points > 0:
            points = result.calculate_points(config.execution.points)
            for team, pts in points.items():
                print(f"Team {team} gained {pts:.1f} points.")

        if exec_config.result is not None:
            t = datetime.now()
            filename = f"{t.year:04d}-{t.month:02d}-{t.day:02d}_{t.hour:02d}-{t.minute:02d}-{t.second:02d}.json"
            with open(exec_config.result / filename, "w+") as f:
                f.write(result.model_dump_json(exclude_defaults=True))

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
    max_size: int
    generator: RunningTimer | None = None
    gen_runtime: float | None = None
    solver: RunningTimer | None = None
    sol_runtime: float | None = None


@dataclass
class CliUi(Ui):
    """A :class:`Ui` displaying the data to the cli.

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

    async def __aexit__(self, _type: type[Exception], _value: Exception, _traceback: TracebackType) -> None:
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

    def start_fight(self, matchup: Matchup, max_size: int) -> None:
        """Informs the Ui of a newly started fight."""
        self.fight_data[matchup] = _FightUiData(max_size)

    def end_fight(self, matchup: Matchup) -> None:  # noqa: D102
        del self.fight_data[matchup]

    def start_program(self, matchup: Matchup, role: Role, data: RunningTimer) -> None:  # noqa: D102
        match role:
            case Role.generator:
                self.fight_data[matchup].generator = data
            case Role.solver:
                self.fight_data[matchup].solver = data

    def end_program(self, matchup: Matchup, role: Role, runtime: float) -> None:  # noqa: D102
        match role:
            case Role.generator:
                self.fight_data[matchup].gen_runtime = runtime
            case Role.solver:
                self.fight_data[matchup].sol_runtime = runtime

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
        out.append(f"Algobattle version {pkg_version('algobattle_base')}")
        status = self.build_status
        if isinstance(status, str):
            out.append(status)
        elif isinstance(status, _BuildInfo):
            runtime = (datetime.now() - status.start).total_seconds()
            status_str = f"Building {status.role.name} of team {status.team}: {runtime:3.1f}s"
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
                    res = "Error!"
                table.add_row([generating, solving, res])

        return str(table).split("\n")

    @staticmethod
    def display_program(role: Role, timer: RunningTimer | None, runtime: float | None) -> str:
        """Formats program runtime data."""
        role_str = role.name.capitalize() + ": "
        out = f"{role_str: <11}"

        if timer is None:
            return out

        if runtime is None:
            # currently running fight
            runtime = (datetime.now() - timer.start).total_seconds()
            state_glyph = "…"
        else:
            runtime = runtime
            state_glyph = "✓"

        out += f"{runtime:3.1f}s"
        if timer.timeout is None:
            out += "         "  # same length padding as timeout info string
        else:
            out += f" / {timer.timeout:3.1f}s"

        out += f" {state_glyph}"
        return out

    @staticmethod
    def display_current_fight(fight: _FightUiData) -> list[str]:
        """Formats the current fight of a battle into a compact overview."""
        return [
            f"Current fight at size {fight.max_size}:",
            CliUi.display_program(Role.generator, fight.generator, fight.gen_runtime),
            CliUi.display_program(Role.solver, fight.solver, fight.sol_runtime),
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
        fights = battle.fights[-3:] if len(battle.fights) >= 3 else battle.fights
        sections: list[list[str]] = []

        if matchup in self.battle_data:
            sections.append([f"{key}: {val}" for key, val in self.battle_data[matchup].model_dump().items()])

        if matchup in self.fight_data:
            sections.append(self.display_current_fight(self.fight_data[matchup]))

        if fights:
            fight_history: list[str] = []
            for i, fight in enumerate(fights, max(len(battle.fights) - 2, 1)):
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
