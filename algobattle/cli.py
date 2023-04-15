"""Main battle script. Executes all possible types of battles, see battle --help for all options."""
from argparse import ArgumentParser
from contextlib import ExitStack
import curses
from dataclasses import dataclass, field
from functools import partial
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, ParamSpec, Self, TypeVar
from importlib.metadata import version as pkg_version

from prettytable import DOUBLE_BORDER, PrettyTable
from anyio import create_task_group, run, sleep

from algobattle.battle import Battle, Fight, FightUiData
from algobattle.docker_util import GeneratorResult, Image, ProgramRunInfo, SolverResult
from algobattle.match import MatchConfig, Match, Ui
from algobattle.problem import Problem
from algobattle.team import Matchup, TeamInfo
from algobattle.util import Role, TimerInfo, check_path, flat_intersperse


@dataclass
class CliOptions:
    """Config data regarding program execution."""

    problem_path: Path = Path()
    silent: bool = False
    result_output: Path | None = None


def parse_cli_args(args: list[str]) -> tuple[CliOptions, MatchConfig]:
    """Parse a given CLI arg list into config objects."""
    parser = ArgumentParser()
    parser.add_argument("problem", type=check_path, help="Path to a folder with the problem file.")
    parser.add_argument(
        "--config",
        type=partial(check_path, type="file"),
        help="Path to a config file, defaults to '{problem} / config.toml'.",
    )
    parser.add_argument("-s", "--silent", action="store_true", help="Disable the cli Ui.")
    parser.add_argument(
        "--result_output", type=check_path, help="If set, the match result object will be saved to the specified file."
    )

    parsed = parser.parse_args(args)
    exec_config = CliOptions(
        problem_path=parsed.problem,
        silent=parsed.silent,
        result_output=parsed.result_output,
    )
    cfg_path: Path = parsed.config or exec_config.problem_path / "config.toml"

    if cfg_path.is_file():
        try:
            config = MatchConfig.from_file(cfg_path)
        except Exception as e:
            raise ValueError(f"Invalid config file, terminating execution.\n{e}")
    else:
        config = MatchConfig()
    if config.docker.advanced_run_params is not None:
        Image.run_kwargs = config.docker.advanced_run_params.to_docker_args()
    if config.docker.advanced_build_params is not None:
        Image.run_kwargs = config.docker.advanced_build_params.to_docker_args()

    if not config.teams:
        config.teams.append(
            TeamInfo(
                name="team_0",
                generator=exec_config.problem_path / "generator",
                solver=exec_config.problem_path / "solver",
            )
        )

    return exec_config, config


async def _run_with_ui(
    match_config: MatchConfig,
    problem: type[Problem],
    ui: "CliUi | None",
) -> Match:
    async with create_task_group() as tg:
        if ui is not None:
            tg.start_soon(ui.loop)
        result = await Match.run(match_config, problem, ui)
        tg.cancel_scope.cancel()
        return result


def main():
    """Entrypoint of `algobattle` CLI."""
    try:
        exec_config, config = parse_cli_args(sys.argv[1:])

    except KeyboardInterrupt:
        raise SystemExit("Received keyboard interrupt, terminating execution.")

    try:
        problem = Problem.import_from_path(exec_config.problem_path)
        with ExitStack() as stack:
            if exec_config.silent:
                ui = None
            else:
                ui = CliUi()
                stack.enter_context(ui)

            result = run(_run_with_ui, config, problem, ui)
            print("\n".join(CliUi.display_match(result)))

            if config.points > 0:
                points = result.calculate_points(config.points)
                for team, pts in points.items():
                    print(f"Team {team} gained {pts:.1f} points.")

            if exec_config.result_output is not None:
                t = datetime.now()
                filename = f"{t.year:04d}-{t.month:02d}-{t.day:02d}_{t.hour:02d}-{t.minute:02d}-{t.second:02d}.json"
                with open(exec_config.result_output / filename, "w+") as f:
                    f.write(result.json())

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
    def display_fight(fight: Fight, index: int) -> list[str]:
        """Formats a completed fight into a compact overview."""
        out = [f"Fight {index} at size {fight.size}:"]
        if fight.generator.error is not None:
            out.append("Generator failed!")
            return out
        assert fight.solver is not None
        if fight.solver.error is not None:
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
