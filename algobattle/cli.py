"""Cli entrypoint to execute matches.

Provides a command line interface to start matches and observe them. See `battle --help` for further options.
"""
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any, Iterable, Literal, Optional, Self, cast
from typing_extensions import override
from importlib.metadata import version as pkg_version

from anyio import run as run_async_fn
from typer import Exit, Typer, Argument, Option
from rich.console import Group, RenderableType, Console
from rich.live import Live
from rich.table import Table, Column
from rich.progress import (
    Progress,
    TextColumn,
    SpinnerColumn,
    BarColumn,
    MofNCompleteColumn,
    TimeElapsedColumn,
    TaskID,
    ProgressColumn,
    Task,
)
from rich.panel import Panel
from rich.text import Text
from rich.columns import Columns

from algobattle.battle import Battle
from algobattle.match import BaseConfig, EmptyUi, Match, Ui
from algobattle.problem import Problem
from algobattle.team import Matchup
from algobattle.util import Role, RunningTimer


__all__ = ("app",)


app = Typer(pretty_exceptions_show_locals=False)
console = Console()


@app.command()
def run(
    path: Annotated[Path, Argument(exists=True, help="Path to either a config file or a directory containing one.")],
    ui: Annotated[bool, Option(help="Whether to show the CLI UI during match execution.")] = True,
    result_path: Annotated[
        Optional[Path],  # typer doesn't support union syntax
        Option(
            "--result",
            "-r",
            exists=True,
            dir_okay=True,
            file_okay=False,
            writable=True,
            help="If set, the match result object will be saved in the folder.",
        ),
    ] = None,
) -> Match:
    """Runs a match using the config found at the provided path and displays it to the cli."""
    config = BaseConfig.from_file(path)
    problem = Problem.get(config.match.problem)
    result = Match()
    try:
        with CliUi() if ui else EmptyUi() as ui_obj:
            run_async_fn(result.run, config, problem, ui_obj)
    except KeyboardInterrupt:
        console.print("Received keyboard interrupt, terminating execution.")
    finally:
        try:
            console.print(CliUi.display_match(result))
            if config.execution.points > 0:
                points = result.calculate_points(config.execution.points)
                for team, pts in points.items():
                    print(f"Team {team} gained {pts:.1f} points.")

            if result_path is not None:
                t = datetime.now()
                filename = f"{t.year:04d}-{t.month:02d}-{t.day:02d}_{t.hour:02d}-{t.minute:02d}-{t.second:02d}.json"
                with open(result_path / filename, "w+") as f:
                    f.write(result.model_dump_json(exclude_defaults=True))
            return result
        except KeyboardInterrupt:
            raise Exit


@dataclass
class _BuildState:
    overall_progress: Progress
    overall_task: TaskID
    team_progress: Progress
    team_tasks: dict[str, TaskID]
    group: Group


class TimerTotalColumn(ProgressColumn):
    """Renders time elapsed."""

    def render(self, task: Task) -> Text:
        """Show time elapsed."""
        if not task.started:
            return Text("")
        elapsed = task.finished_time if task.finished else task.elapsed
        total = f" / {task.fields['total_time']}" if "total_time" in task.fields else ""
        current = f"{elapsed:.1f}" if elapsed is not None else ""
        return Text(current + total, style="progress.elapsed")


class LazySpinnerColumn(SpinnerColumn):
    """Spinner that only starts once the task starts."""

    @override
    def render(self, task: Task) -> RenderableType:
        if not task.started:
            return " "
        return super().render(task)


class FightPanel(Panel):
    """Panel displaying a currently running fight."""

    def __init__(self, max_size: int) -> None:
        self.max_size = max_size
        self.progress = Progress(
            TextColumn("[progress.description]{task.description}"),
            LazySpinnerColumn(),
            TimerTotalColumn(),
            TextColumn("{task.fields[message]}"),
            transient=True,
        )
        self.generator = self.progress.add_task("Generator", start=False, total=1, message="")
        self.solver = self.progress.add_task("Solver", start=False, total=1, message="")
        super().__init__(self.progress, title="Current Fight", width=35)


class BattlePanel(Panel):
    """Panel that displays the state of a battle."""

    def __init__(self, matchup: Matchup) -> None:
        self.matchup = matchup
        self._battle_data: RenderableType = ""
        self._curr_fight: FightPanel | Literal[""] = ""
        self._past_fights = self._fights_table()
        super().__init__(self._make_renderable(), title=f"Battle {self.matchup}")

    def _make_renderable(self) -> RenderableType:
        return Group(
            Columns((self._battle_data, self._curr_fight), expand=True, equal=True, column_first=True, align="center"),
            self._past_fights,
        )

    @property
    def battle_data(self) -> RenderableType:
        return self._battle_data

    @battle_data.setter
    def battle_data(self, value: RenderableType) -> None:
        self._battle_data = value
        self.renderable = self._make_renderable()

    @property
    def curr_fight(self) -> FightPanel | Literal[""]:
        return self._curr_fight

    @curr_fight.setter
    def curr_fight(self, value: FightPanel | Literal[""]) -> None:
        self._curr_fight = value
        self.renderable = self._make_renderable()

    @property
    def past_fights(self) -> Table:
        return self._past_fights

    @past_fights.setter
    def past_fights(self, value: Table) -> None:
        self._past_fights = value
        self.renderable = self._make_renderable()

    def _fights_table(self) -> Table:
        return Table(
            Column("Fight", justify="right"),
            Column("Max size", justify="right"),
            Column("Score", justify="right"),
            "Detail",
            title="Most recent fights",
        )


class CliUi(Live, Ui):
    """Ui that uses rich to draw to the console."""

    def __init__(self) -> None:
        self.match = None
        self.build: _BuildState | None = None
        self.battle_panels: dict[Matchup, BattlePanel] = {}
        super().__init__(None, refresh_per_second=10, transient=True)

    def __enter__(self) -> Self:
        return cast(Self, super().__enter__())

    def _update_renderable(self) -> None:
        if self.build:
            r = self.build.group
        else:
            assert self.match is not None
            r = Group(self.display_match(self.match), *self.battle_panels.values())
        self.update(Panel(r, title=f"[orange1]Algobattle {pkg_version('algobattle_base')}"))

    @staticmethod
    def display_match(match: Match) -> RenderableType:
        """Formats the match data into a table that can be printed to the terminal."""
        table = Table(
            Column("Generating", justify="center"),
            Column("Solving", justify="center"),
            Column("Result", justify="right"),
            title="[blue]Match overview",
        )
        for generating, battles in match.results.items():
            for solving, result in battles.items():
                if result.run_exception is None:
                    res = result.format_score(result.score())
                else:
                    res = ":warning:"
                table.add_row(generating, solving, res)
        return table

    @override
    def start_build_step(self, teams: Iterable[str], timeout: float | None) -> None:
        team_dict: dict[str, Any] = {t: "none" for t in teams}
        overall_progress = Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            transient=True,
        )
        team_progress = Progress(
            TextColumn("[cyan]{task.fields[name]}"),
            TimeElapsedColumn(),
            SpinnerColumn(),
            TextColumn("{task.fields[failed]}"),
        )
        group = Group(overall_progress, team_progress)
        overall = overall_progress.add_task("[blue]Building team programs", total=len(team_dict))

        team_tasks = {}
        for team in team_dict:
            team_tasks[team] = team_progress.add_task(team, start=False, total=3, failed="", name=team)

        self.build = _BuildState(overall_progress, overall, team_progress, team_tasks, group)
        self._update_renderable()

    @override
    def start_build(self, team: str, role: Role) -> None:
        if self.build is not None:
            task = self.build.team_tasks[team]
            self.build.team_progress.start_task(task)
            self.build.team_progress.advance(task)

    @override
    def finish_build(self, team: str, success: bool) -> None:
        if self.build is not None:
            task = self.build.team_tasks[team]
            self.build.team_progress.update(task, completed=3, failed="" if success else ":warning:")
            self.build.overall_progress.advance(self.build.overall_task)

    @override
    def start_battles(self) -> None:
        self.build = None
        self._update_renderable()

    @override
    def start_battle(self, matchup: Matchup) -> None:
        self.battle_panels[matchup] = BattlePanel(matchup)
        self._update_renderable()

    @override
    def battle_completed(self, matchup: Matchup) -> None:
        del self.battle_panels[matchup]
        self._update_renderable()

    @override
    def start_fight(self, matchup: Matchup, max_size: int) -> None:
        self.battle_panels[matchup].curr_fight = FightPanel(max_size)

    @override
    def end_fight(self, matchup: Matchup) -> None:
        assert self.match is not None
        battle = self.match.battle(matchup)
        assert battle is not None
        fights = battle.fights[-1:-6:-1]
        panel = self.battle_panels[matchup]
        table = panel._fights_table()
        for i, fight in zip(range(len(battle.fights), len(battle.fights) - len(fights), -1), fights):
            if fight.generator.error:
                info = f"Generator failed: {fight.generator.error.message}"
            elif fight.solver and fight.solver.error:
                info = f"Solver failed: {fight.solver.error.message}"
            else:
                info = ""
            table.add_row(str(i), str(fight.max_size), f"{fight.score:.1%}", info)
        panel.past_fights = table

    @override
    def start_program(self, matchup: Matchup, role: Role, data: RunningTimer) -> None:
        fight = self.battle_panels[matchup].curr_fight
        assert fight != ""
        match role:
            case Role.generator:
                fight.progress.update(fight.generator, total_time=data.timeout)
                fight.progress.start_task(fight.generator)
            case Role.solver:
                fight.progress.update(fight.solver, total_time=data.timeout)
                fight.progress.start_task(fight.solver)

    @override
    def end_program(self, matchup: Matchup, role: Role, runtime: float) -> None:
        fight = self.battle_panels[matchup].curr_fight
        assert fight != ""
        match role:
            case Role.generator:
                fight.progress.update(fight.generator, completed=1, message=":heavy_check_mark:")
            case Role.solver:
                fight.progress.update(fight.solver, completed=1)

    @override
    def update_battle_data(self, matchup: Matchup, data: Battle.UiData) -> None:
        self.battle_panels[matchup].battle_data = Group(
            "[green]Battle Data:", *(f"[orchid]{key}[/]: [cyan]{value}" for key, value in data.model_dump().items())
        )


if __name__ == "__main__":
    app(prog_name="algobattle")
