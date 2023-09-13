"""Cli entrypoint to execute matches.

Provides a command line interface to start matches and observe them. See `battle --help` for further options.
"""
from dataclasses import dataclass
from datetime import datetime
from os import environ
from pathlib import Path
from random import choice
from shutil import rmtree
from subprocess import PIPE, run as run_process
import sys
from typing import Annotated, Any, ClassVar, Iterable, Literal, Optional, Self, cast
from typing_extensions import override
from importlib.metadata import version as pkg_version
from textwrap import dedent
from zipfile import ZipFile

from anyio import run as run_async_fn
from pydantic import Field, ValidationError, BaseModel
from typer import Exit, Typer, Argument, Option, Abort, get_app_dir, launch, confirm
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
from rich.status import Status
from tomlkit import TOMLDocument, parse as parse_toml, dumps as dumps_toml, table
from tomlkit.items import Table as TomlTable
from tomlkit.container import Container as TomlContainer

from algobattle.battle import Battle
from algobattle.match import BaseConfig, EmptyUi, Match, Ui
from algobattle.problem import Problem
from algobattle.team import Matchup
from algobattle.util import ExecutionConfig, Role, RunningTimer, BaseModel as AlgobattleBaseModel, TempDir
from algobattle.templates import Language, PartialTemplateArgs, TemplateArgs, write_templates


__all__ = ("app",)


app = Typer(pretty_exceptions_show_locals=True)
console = Console()


class _General(BaseModel):
    team_name: str | None = None
    install_command: list[str] = [sys.executable, "-m", "pip", "install"]


class CliConfig(BaseModel, frozen=True):
    general: _General = Field(default_factory=dict, validate_default=True)
    execution: ExecutionConfig = Field(default_factory=dict, validate_default=True)

    _doc: TOMLDocument
    path: ClassVar[Path] = Path(get_app_dir("algobattle")) / "config.toml"
    model_config = AlgobattleBaseModel.model_config

    @classmethod
    def init_file(cls) -> None:
        """Initializes the config file if it does not exist."""
        if not cls.path.is_file():
            cls.path.parent.mkdir(parents=True, exist_ok=True)
            cls.path.write_text("# The Algobattle cli configuration\n")

    @classmethod
    def load(cls) -> Self:
        """Parses a config object from a toml file."""
        cls.init_file()
        doc = parse_toml(cls.path.read_text())
        self = cls.model_validate(doc)
        object.__setattr__(self, "_doc", doc)
        return self

    def save(self) -> None:
        """Saves the config to file."""
        self.path.write_text(dumps_toml(self._doc))

    @property
    def default_exec(self) -> TomlTable | None:
        """The default exec config for each problem."""
        exec: Any = self._doc.get("exec", None)
        return exec


@app.command("run")
def run_match(
    path: Annotated[Path, Argument(exists=True, help="Path to either a config file or a directory containing one.")],
    ui: Annotated[bool, Option(help="Whether to show the CLI UI during match execution.")] = True,
    save: Annotated[bool, Option(help="Whether to save the match result.")] = True,
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

            if save:
                t = datetime.now()
                filename = f"{t.year:04d}-{t.month:02d}-{t.day:02d}_{t.hour:02d}-{t.minute:02d}-{t.second:02d}.json"
                with open(config.execution.results / filename, "w+") as f:
                    f.write(result.model_dump_json(exclude_defaults=True))
            return result
        except KeyboardInterrupt:
            raise Exit


def _init_program(target: Path, lang: Language, args: PartialTemplateArgs, role: Role) -> None:
    dir = target / role.value
    if dir.exists():
        replace = confirm(f"The targeted directory already contains a {role}, do you want to replace it?", default=True)
        if replace:
            rmtree(dir)
            dir.mkdir()
        else:
            return
    else:
        dir.mkdir(parents=True, exist_ok=True)
    write_templates(dir, lang, cast(TemplateArgs, args | {"program": role.value}))


@app.command()
def init(
    target: Annotated[
        Optional[Path], Argument(exists=True, file_okay=False, writable=True, help="The folder to initialize.")
    ] = None,
    problem: Annotated[
        Optional[Path],
        Option("--problem", "-p", exists=True, dir_okay=False, help="A problem spec file to use for this."),
    ] = None,
    language: Annotated[
        Optional[Language], Option("--language", "-l", help="The language to use for the programs.")
    ] = None,
    generator: Annotated[
        Optional[Language], Option("--generator", "-g", help="The language to use for the generator.")
    ] = None,
    solver: Annotated[Optional[Language], Option("--solver", "-s", help="The language to use for the solver.")] = None,
) -> None:
    """Initializes a project directory, setting up the problem files and program folders with docker files.

    Generates dockerfiles and an initial project structure for the language(s) you choose. Either use `--language` to
    use the same language for both, or specify each individually with `--generator` and `--solver`.
    """
    if language is not None and (generator is not None or solver is not None):
        console.print("You cannot use both `--language` and `--generator`/`--solver` at the same time.")
        raise Abort
    if language:
        generator = solver = language
    config = CliConfig.load()
    team_name = config.general.team_name or choice(("Dogs", "Cats", "Otters", "Red Pandas", "Possums", "Rats"))

    if problem is None and Path("problem.aprb").is_file():
        problem = Path("problem.aprb")
    if problem is not None:
        with TempDir() as build_dir:
            with Status("Extracting problem data"):
                with ZipFile(problem) as problem_zip:
                    problem_zip.extractall(build_dir)

            problem_config = parse_toml((build_dir / "config.toml").read_text())
            parsed_config = BaseConfig.model_validate(problem_config)  # ! paths in this arent properly relativized
            problem_name = parsed_config.match.problem
            assert isinstance(problem_name, str)
            if target is None:
                target = Path() if Path().name == problem_name else Path() / problem_name

            new_problem = True
            problem_data = list(build_dir.iterdir())
            if any(((target / path.name).exists() for path in problem_data)):
                replace = confirm(
                    "The target directory already contains problem data, do you want to replace it?", default=True
                )
                if replace:
                    for path in problem_data:
                        if (file := target / path.name).is_file():
                            file.unlink()
                        elif (dir := target / path.name).is_dir():
                            rmtree(dir)
                else:
                    new_problem = False

            if new_problem:
                with Status("Installing problem"):
                    res = run_process(
                        config.general.install_command + [build_dir.absolute()],
                        shell=False,
                        capture_output=True,
                        text=True,
                        env=environ.copy(),
                    )
                if res.returncode:
                    print("Couldn't install the problem")
                    console.print(f"[red]{res.stderr}")
                    raise Abort
                for path in problem_data:
                    path.rename(target / path.name)
    else:
        problem_name = "Unknown Problem"
        problem_config = TOMLDocument()
        if target is None:
            target = Path()
        parsed_config = BaseConfig()  # ! paths in this arent properly relativized

    with Status("Initializing metadata"):
        problem_config.add(
            "teams",
            table().add(
                team_name,
                table().add("generator", "./generator").add("solver", "./solver"),
            ),
        )
        if config.default_exec is not None:
            problem_config.add(config.default_exec)
        (target / "config.toml").write_text(dumps_toml(problem_config))
        res_path = parsed_config.execution.results
        if not res_path.is_absolute():
            res_path = (target / res_path).resolve()
        res_path.mkdir(parents=True, exist_ok=True)

    template_args: PartialTemplateArgs = {
        "problem": problem_name,
        "team": team_name,
    }

    if generator is not None:
        with Status("Initializing generator"):
            _init_program(target, generator, template_args, Role.generator)

    if solver is not None:
        with Status("Initializing solver"):
            _init_program(target, solver, template_args, Role.solver)
    print(f"Initialized problem directory at {target}")


@app.command()
def config() -> None:
    """Opens the algobattle cli tool config file."""
    CliConfig.init_file()
    print(f"Opening the algobattle cli config file at {CliConfig.path}.")
    launch(str(CliConfig.path))


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


class BuildView(Group):
    """Displays the build process."""

    def __init__(self, teams: Iterable[str]) -> None:
        teams = list(teams)
        self.overall_progress = Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            transient=True,
        )
        self.team_progress = Progress(
            TextColumn("[cyan]{task.fields[name]}"),
            LazySpinnerColumn(),
            BarColumn(bar_width=10),
            TimeElapsedColumn(),
        )
        self.overall_task = self.overall_progress.add_task("[blue]Building programs", total=2 * len(teams))
        team_dict: dict[str, TaskID] = {}
        for team in teams:
            team_dict[team] = self.team_progress.add_task(team, start=False, total=2, failed="", name=team)
        self.teams = team_dict
        super().__init__(self.overall_progress, self.team_progress)


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
        super().__init__(self.progress, title="Current Fight", width=30)


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
            Columns((self._battle_data, self._curr_fight), expand=True, equal=True, align="center"),
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
        self.battle_panels: dict[Matchup, BattlePanel] = {}
        super().__init__(None, refresh_per_second=10, transient=True)

    def __enter__(self) -> Self:
        return cast(Self, super().__enter__())

    def _update_renderable(self, renderable: RenderableType | None = None) -> None:
        if renderable is None:
            assert self.match is not None
            renderable = Group(self.display_match(self.match), *self.battle_panels.values())
        self.update(Panel(renderable, title=f"[orange1]Algobattle {pkg_version('algobattle_base')}"))

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
        self._update_renderable(BuildView(teams))

    @override
    def start_build(self, team: str, role: Role) -> None:
        assert isinstance(self.renderable, Panel)
        view = self.renderable.renderable
        assert isinstance(view, BuildView)
        task = view.teams[team]
        view.team_progress.start_task(task)
        view.team_progress.advance(task)

    @override
    def finish_build(self, team: str, success: bool) -> None:
        assert isinstance(self.renderable, Panel)
        view = self.renderable.renderable
        assert isinstance(view, BuildView)
        task = view.teams[team]
        current = view.team_progress._tasks[task].completed
        view.team_progress.update(task, completed=2, failed="" if success else ":warning:")
        view.overall_progress.advance(view.overall_task, 2 - current)

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
