"""Cli entrypoint to execute matches.

Provides a command line interface to start matches and observe them. See `battle --help` for further options.
"""
from enum import StrEnum
from functools import cached_property
import json
from os import environ
from pathlib import Path
from random import choice
from shutil import rmtree
from subprocess import PIPE, Popen
import sys
from typing import Annotated, Any, ClassVar, Iterable, Literal, Optional, Self, cast
from typing_extensions import override
from importlib.metadata import version as pkg_version
from zipfile import ZipFile

from anyio import run as run_async_fn
from pydantic import Field, ValidationError
from typer import Exit, Typer, Argument, Option, Abort, get_app_dir, launch
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
    ProgressColumn,
    Task,
)
from rich.panel import Panel
from rich.text import Text
from rich.columns import Columns
from rich.prompt import Prompt, Confirm
from tomlkit import TOMLDocument, parse as parse_toml, dumps as dumps_toml, table
from tomlkit.exceptions import ParseError
from tomlkit.items import Table as TomlTable

from algobattle.battle import Battle
from algobattle.match import AlgobattleConfig, EmptyUi, Match, MatchConfig, Ui, ProjectConfig
from algobattle.problem import Instance, Problem, Solution
from algobattle.program import Generator, Matchup, Solver
from algobattle.util import BuildError, EncodableModel, ExceptionInfo, Role, RunningTimer, BaseModel, TempDir, timestamp
from algobattle.templates import Language, PartialTemplateArgs, TemplateArgs, write_templates


__all__ = ("app",)

help_message = """The Algobattle command line program.

You can use this to setup your workspace, develop programs, run matches, and more!
For more detailed documentation, visit our website at http://algobattle.org/docs/tutorial
"""
app = Typer(pretty_exceptions_show_locals=True, help=help_message)
console = Console()


class _InstallMode(StrEnum):
    normal = "normal"
    user = "user"


class _General(BaseModel):
    team_name: str | None = None
    install_mode: _InstallMode | None = None


class CliConfig(BaseModel):
    general: _General = Field(default_factory=dict, validate_default=True)
    default_project_config: ProjectConfig | None = Field(default=None)

    _doc: TOMLDocument
    path: ClassVar[Path] = Path(get_app_dir("algobattle")) / "config.toml"

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
    def default_project_doc(self) -> TomlTable | None:
        """The default exec config for each problem."""
        exec: Any = self._doc.get("default_project_config", table().append("results", "results"))
        return exec

    @cached_property
    def install_cmd(self) -> list[str]:
        cmd = [sys.executable, "-m", "pip", "install"]
        if self.general.install_mode is None:
            command_str: str = Prompt.ask(
                "[cyan]Do you want to install problems normally, or into the user directory?[/] If you're using an "
                "environment manager like venv or conda you should install them normally, otherwise user installs "
                "might be better.",
                default="normal",
                choices=["normal", "user"],
            )
            if command_str == "user":
                cmd.append("--user")
                self.general.install_mode = _InstallMode.user
            else:
                self.general.install_mode = _InstallMode.normal
            if "general" not in self._doc:
                self._doc.add("general", table())
            cast(TomlTable, self._doc["general"])["install_mode"] = command_str
            self.save()
        return cmd


@app.command("run")
def run_match(
    path: Annotated[
        Path, Argument(exists=True, help="Path to either a config file or a directory containing one.")
    ] = Path(),
    ui: Annotated[bool, Option(help="Whether to show the CLI UI during match execution.")] = True,
    save: Annotated[bool, Option(help="Whether to save the match result.")] = True,
) -> Match:
    """Runs a match using the config found at the provided path and displays it to the cli."""
    config = AlgobattleConfig.from_file(path)
    result = Match()
    try:
        with CliUi() if ui else EmptyUi() as ui_obj:
            run_async_fn(result.run, config, ui_obj)
    except KeyboardInterrupt:
        console.print("Received keyboard interrupt, terminating execution.")
    finally:
        try:
            console.print(CliUi.display_match(result))
            if config.project.points > 0:
                points = result.calculate_points(config.project.points)
                for team, pts in points.items():
                    print(f"Team {team} gained {pts:.1f} points.")

            if save:
                res_string = result.model_dump_json(exclude_defaults=True)
                config.project.results.joinpath(f"{timestamp()}.json").write_text(res_string)
            return result
        except KeyboardInterrupt:
            raise Exit


def _init_program(target: Path, lang: Language, args: PartialTemplateArgs, role: Role) -> None:
    dir = target / role
    if dir.exists():
        replace = Confirm.ask(
            f"[magenta2]The targeted directory already contains a {role}, do you want to replace it?",
            default=True,
        )
        if replace:
            rmtree(dir)
            dir.mkdir()
        else:
            return
    else:
        dir.mkdir(parents=True, exist_ok=True)
    with console.status(f"Initializing {role}"):
        write_templates(dir, lang, TemplateArgs(program=role.value, **args))
    console.print(f"Created a {lang} {role} in [cyan]{dir}")


@app.command()
def init(
    target: Annotated[
        Optional[Path], Argument(file_okay=False, writable=True, help="The folder to initialize.")
    ] = None,
    problem_: Annotated[
        Optional[str],
        Option(
            "--problem",
            "-p",
            help="Path to the .algo file to use, or the name of an installed problem.",
        ),
    ] = None,
    language: Annotated[
        Optional[Language], Option("--language", "-l", help="The language to use for the programs.")
    ] = None,
    generator: Annotated[
        Optional[Language], Option("--generator", "-g", help="The language to use for the generator.")
    ] = None,
    solver: Annotated[Optional[Language], Option("--solver", "-s", help="The language to use for the solver.")] = None,
    schemas: Annotated[bool, Option(help="Whether to also save the problem's IO schemas.")] = False,
) -> None:
    """Initializes a project directory, setting up the problem files and program folders.

    Generates dockerfiles and an initial project structure for the language(s) you choose. Either use `--language` to
    use the same language for both, or specify each individually with `--generator` and `--solver`.
    """
    if language is not None and (generator is not None or solver is not None):
        console.print("You cannot use both `--language` and `--generator`/`--solver` at the same time.")
        raise Abort
    if language:
        generator = solver = language
    config = CliConfig.load()
    team_name = config.general.team_name or choice(
        ("Dogs", "Cats", "Otters", "Red Pandas", "Crows", "Rats", "Cockatoos", "Dingos", "Penguins", "Kiwis", "Orcas")
        + ("Bearded Dragons", "Macaws", "Wombats", "Wallabies", "Owls", "Seals", "Octopuses", "Frogs", "Jellyfish")
    )

    if problem_ is None:  # use the preexisting config file in the target folder
        if target is None:
            target = Path()
        try:
            parsed_config = AlgobattleConfig.from_file(target, relativize_paths=False)
        except FileNotFoundError:
            console.print("[red]You must either use a problem spec file or target a directory with an existing config.")
            raise Abort
        except ValueError as e:
            console.print("[red]The Algobattle config file is not formatted properly\n", e)
            raise Abort
        console.print("Using existing project data")
        if len(parsed_config.teams) == 1:
            team_name = next(iter(parsed_config.teams.keys()))

    elif problem_ in Problem.available():  # use a preinstalled problem
        if target is None:
            target = Path() / problem_
        target.mkdir(parents=True, exist_ok=True)
        target.joinpath("algobattle.toml").write_text(f"""[match]\nproblem = "{problem_}"\n""")
        parsed_config = AlgobattleConfig(match=MatchConfig(problem=problem_))

    elif (problem := Path(problem_)).is_file():  # use a problem spec file
        with TempDir() as unpack_dir:
            with console.status("Extracting problem data"):
                with ZipFile(problem) as problem_zip:
                    problem_zip.extractall(unpack_dir)

            parsed_config = AlgobattleConfig.from_file(unpack_dir, relativize_paths=False)
            if target is None:
                target = Path() / parsed_config.match.problem

            target.mkdir(parents=True, exist_ok=True)
            problem_data = list(unpack_dir.iterdir())
            if any(((target / path.name).exists() for path in problem_data)):
                copy_problem_data = Confirm.ask(
                    "[magenta2]The target directory already contains an algobattle project, do you want to replace it?",
                    default=True,
                )
            else:
                copy_problem_data = True
            if copy_problem_data:
                for path in problem_data:
                    if (file := target / path.name).is_file():
                        file.unlink()
                    elif (dir := target / path.name).is_dir():
                        rmtree(dir)
                    path.rename(target / path.name)
                console.print("Unpacked problem data")
            else:
                parsed_config = AlgobattleConfig.from_file(target, relativize_paths=False)
                console.print("Using existing problem data")

    else:
        console.print(
            "[red]The problem argument is neither the name of an installed problem, nor the path to a problem spec"
        )
        raise Abort

    problem_name = parsed_config.match.problem
    info = parsed_config.problems.get(problem_name, None)
    if info is not None and not info.location.is_absolute():
        info.location = target / info.location
    if info is not None and info.dependencies:
        cmd = config.install_cmd
        with console.status(f"Installing {problem_name}'s dependencies"), Popen(
            cmd + info.dependencies, env=environ.copy(), stdout=PIPE, stderr=PIPE, text=True
        ) as installer:
            assert installer.stdout is not None
            assert installer.stderr is not None
            for line in installer.stdout:
                console.print(line.strip("\n"))
            error = "".join(installer.stderr.readlines())
        if installer.returncode:
            console.print(f"[red]Couldn't install the dependencies[/]\n{error}")
            raise Abort
        else:
            console.print(f"[green]Installed dependencies of {problem_name}")

    with console.status("Initializing metadata"):
        config_doc = parse_toml(target.joinpath("algobattle.toml").read_text())
        if "teams" not in config_doc:
            config_doc.add(
                "teams",
                table().add(
                    team_name,
                    table().add("generator", "generator").add("solver", "solver"),
                ),
            )
        if config.default_project_doc is not None and "project" not in config_doc:
            config_doc["project"] = config.default_project_doc
        target.joinpath("algobattle.toml").write_text(dumps_toml(config_doc))
        res_path = parsed_config.project.results
        if not res_path.is_absolute():
            res_path = target / res_path
        res_path.mkdir(parents=True, exist_ok=True)
        if res_path.resolve().is_relative_to(target.resolve()):
            target.joinpath(".gitignore").write_text(f"{res_path.relative_to(target)}/\n")

    problem_obj = parsed_config.problem
    if schemas:
        instance: type[Instance] = problem_obj.instance_cls
        solution: type[Solution[Instance]] = problem_obj.solution_cls
        schema_folder = target / "schemas"
        schema_folder.mkdir(exist_ok=True)
        if s := instance.io_schema():
            schema_folder.joinpath("instance.json").write_text(s)
        if s := solution.io_schema():
            schema_folder.joinpath("solution.json").write_text(s)

    template_args: PartialTemplateArgs = {
        "problem": problem_name,
        "team": team_name,
        "with_solution": problem_obj.with_solution,
        "instance_json": issubclass(problem_obj.instance_cls, EncodableModel),
        "solution_json": issubclass(problem_obj.solution_cls, EncodableModel),
    }
    if generator is not None:
        _init_program(target, generator, template_args, Role.generator)
    elif not target.joinpath("generator").exists():
        _init_program(target, Language.plain, template_args, Role.generator)
    if solver is not None:
        _init_program(target, solver, template_args, Role.solver)
    elif not target.joinpath("solver").exists():
        _init_program(target, Language.plain, template_args, Role.solver)

    console.print(f"[green]Success![/] initialized algobattle project data in [cyan]{target}[/]")


class TestErrors(BaseModel):
    """Helper class holding test error messages."""

    generator_build: ExceptionInfo | None = None
    solver_build: ExceptionInfo | None = None
    generator_run: ExceptionInfo | None = None
    solver_run: ExceptionInfo | None = None


@app.command()
def test(
    folder: Annotated[Path, Argument(help="The project folder to use.")] = Path(),
) -> None:
    """Tests whether the programs install successfully and run on dummy instances without crashing."""
    if not (folder.is_file() or folder.joinpath("algobattle.toml").is_file()):
        console.print("[red]The folder does not contain an Algobattle project")
        raise Abort
    config = AlgobattleConfig.from_file(folder)
    problem = config.problem
    all_errors: dict[str, Any] = {}

    for team, team_info in config.teams.items():
        console.print(f"Testing programs of team {team}")
        errors = TestErrors()
        instance = None

        async def gen_builder() -> Generator:
            with console.status("Building generator"):
                return await Generator.build(
                    team_info.generator, problem=problem, config=config.as_prog_config(), team_name=team
                )

        try:
            with run_async_fn(gen_builder) as gen:
                console.print("[green]Generator built successfully")
                with console.status("Running generator"):
                    instance = gen.test()
                if isinstance(instance, ExceptionInfo):
                    console.print("[red]Generator didn't run successfully")
                    errors.generator_run = instance
                    instance = None
                else:
                    console.print("[green]Generator ran successfully")
        except BuildError as e:
            console.print("[red]Generator didn't build successfully")
            errors.generator_build = ExceptionInfo.from_exception(e)
            instance = None

        sol_error = None

        async def sol_builder() -> Solver:
            with console.status("Building solver"):
                return await Solver.build(
                    team_info.solver, problem=problem, config=config.as_prog_config(), team_name=team
                )

        try:
            with run_async_fn(sol_builder) as sol:
                console.print("[green]Solver built successfully")

                instance = instance or cast(Instance, problem.test_instance)
                if instance:
                    with console.status("Running solver"):
                        sol_error = sol.test(instance)
                    if isinstance(sol_error, ExceptionInfo):
                        console.print("[red]Solver didn't run successfully")
                        errors.solver_run = sol_error
                    else:
                        console.print("[green]Solver ran successfully")
                else:
                    console.print("[orange3]Cannot test running the solver")
        except BuildError as e:
            console.print("[red]Solver didn't build successfully")
            errors.solver_build = ExceptionInfo.from_exception(e)
            instance = None

        if errors != TestErrors():
            all_errors[team] = errors.model_dump(exclude_defaults=True)

    if all_errors:
        err_path = config.project.results.joinpath(f"{timestamp()}.json")
        err_path.write_text(json.dumps(all_errors, indent=4))
        console.print(f"You can find detailed error messages at {err_path}")


@app.command()
def config() -> None:
    """Opens the algobattle cli tool config file."""
    CliConfig.init_file()
    print(f"Opening the algobattle cli config file at {CliConfig.path}.")
    launch(str(CliConfig.path))


@app.command()
def package(
    problem_path: Annotated[
        Optional[Path], Argument(exists=True, help="Path to problem python file or a package containing it.")
    ] = None,
    config: Annotated[Optional[Path], Option(exists=True, dir_okay=False, help="Path to the config file.")] = None,
    description: Annotated[
        Optional[Path], Option(exists=True, dir_okay=False, help="Path to a problem description file.")
    ] = None,
    out: Annotated[
        Optional[Path], Option("--out", "-o", dir_okay=False, file_okay=False, help="Location of the output.")
    ] = None,
) -> None:
    """Packages problem data into an `.algo` file."""
    if problem_path is None:
        if Path("problem.py").is_file():
            problem_path = Path("problem.py")
        elif Path("problem").is_dir():
            problem_path = Path("problem")
        else:
            console.print("[red]Couldn't find a problem package")
            raise Abort
    if config is None:
        if problem_path.parent.joinpath("algobattle.toml").is_file():
            config = problem_path.parent / "algobattle.toml"
        else:
            console.log("[red]Couldn't find a config file")
            raise Abort
    if description is None:
        match list(problem_path.parent.resolve().glob("description.*")):
            case []:
                pass
            case [desc]:
                description = desc
            case _:
                console.print(
                    "[red]Found multiple potential description files[/], explicitly specify which you want to include"
                )
                raise Abort

    try:
        config_doc = parse_toml(config.read_text())
        parsed_config = AlgobattleConfig.from_file(config)
    except (ValidationError, ParseError) as e:
        console.print(f"[red]Improperly formatted config file\nError: {e}")
        raise Abort
    problem_name = parsed_config.match.problem
    try:
        with console.status("Loading problem"):
            Problem.load_file(problem_name, problem_path)
    except (ValueError, RuntimeError) as e:
        console.print(f"[red]Couldn't load the problem file[/]\nError: {e}")
        raise Abort
    problem_info = parsed_config.problems[problem_name]

    if "project" in config_doc:
        config_doc.remove("project")
    if "teams" in config_doc:
        config_doc.remove("teams")
    info_doc = table().append(
        "location",
        "problem.py"
        if problem_path.is_file()
        else Path("problem") / problem_info.location.resolve().relative_to(problem_path.resolve()),
    )
    if problem_info.dependencies:
        info_doc.append("dependencies", problem_info.dependencies)
    config_doc["problems"] = table().append(problem_name, info_doc)

    if out is None:
        out = problem_path.parent / f"{problem_name.lower().replace(' ', '_')}.algo"
    with console.status("Packaging data"), ZipFile(out, "w") as file:
        if problem_path.is_file():
            file.write(problem_path, "problem.py")
        else:
            for path in problem_path.glob("**"):
                if path.is_file():
                    file.write(path, Path("problem") / path.relative_to(problem_path))
        file.writestr("algobattle.toml", dumps_toml(config_doc))
        if description is not None:
            file.write(description, description.name)
    console.print("[green]Packaged Algobattle project into[/]", out)


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
            TextColumn("[cyan]{task.fields[status]}"),
        )
        self.overall_task = self.overall_progress.add_task("[blue]Building programs", total=2 * len(teams))
        self.teams = {
            team: self.team_progress.add_task(team, start=False, total=2, status="", name=team) for team in teams
        }
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
        super().__init__(Group(f"Max size: {self.max_size}", self.progress), title="[green]Current Fight", width=30)


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
            Columns((self._curr_fight, self._battle_data), align="left"),
            self._past_fights,
        )

    @property
    def battle_data(self) -> RenderableType:
        return self._battle_data

    @battle_data.setter
    def battle_data(self, value: RenderableType) -> None:
        self._battle_data = Panel(value, title="[green]Battle Data")
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

    match: Match

    def __init__(self) -> None:
        self.battle_panels: dict[Matchup, BattlePanel] = {}
        super().__init__(None, refresh_per_second=10, transient=True)

    def __enter__(self) -> Self:
        return cast(Self, super().__enter__())

    def _update_renderable(self, renderable: RenderableType | None = None) -> None:
        if renderable is None:
            renderable = Group(self.display_match(self.match), *self.battle_panels.values())
        self.update(Panel(renderable, title=f"[orange1]Algobattle {pkg_version('algobattle_base')}"))

    @staticmethod
    def display_match(match: Match) -> RenderableType:
        """Formats the match data into a table that can be printed to the terminal."""
        table = Table(
            Column("Generating", justify="center"),
            Column("Solving", justify="center"),
            Column("Result", justify="right"),
            title="[green]Match overview",
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
        match role:
            case Role.generator:
                view.team_progress.start_task(task)
            case Role.solver:
                view.team_progress.advance(task)
                view.overall_progress.advance(view.overall_task, 1)

    @override
    def finish_build(self, team: str, success: bool) -> None:
        assert isinstance(self.renderable, Panel)
        view = self.renderable.renderable
        assert isinstance(view, BuildView)
        task = view.teams[team]
        current = view.team_progress._tasks[task].completed
        view.team_progress.update(task, completed=2, status="" if success else "[red]failed!")
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
        battle = self.match.battle(matchup)
        assert battle is not None
        fights = battle.fights[-1:-6:-1]
        panel = self.battle_panels[matchup]
        table = panel._fights_table()
        for i, fight in zip(range(len(battle.fights), len(battle.fights) - len(fights), -1), fights):
            if fight.generator.error:
                info = f"[red]Generator failed[/]: {fight.generator.error.message}"
            elif fight.solver and fight.solver.error:
                info = f"[red]Solver failed[/]: {fight.solver.error.message}"
            else:
                assert fight.solver is not None
                info = f"Runtimes: gen {fight.generator.runtime:.1f}s, sol {fight.solver.runtime:.1f}s"
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
            *(f"[orchid]{key}[/]: [cyan]{value}" for key, value in data.model_dump().items())
        )


if __name__ == "__main__":
    app(prog_name="algobattle")
