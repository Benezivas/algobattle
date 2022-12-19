"""Main battle script. Executes all possible types of battles, see battle --help for all options."""
from __future__ import annotations
from argparse import ArgumentParser
from contextlib import ExitStack
from dataclasses import dataclass
from functools import partial
import sys
import logging
import datetime as dt
from pathlib import Path
from typing import Callable, Literal, TypeVar, cast
import tomli
from algobattle.battle_wrapper import BattleWrapper

from algobattle.match import MatchConfig, run_match
from algobattle.team import TeamHandler, TeamInfo
from algobattle.ui import Ui
from algobattle.util import check_path, import_problem_from_path
from algobattle.battle_wrappers.averaged import Averaged
from algobattle.battle_wrappers.iterated import Iterated


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

    t = dt.datetime.now()
    current_timestamp = f"{t.year:04d}-{t.month:02d}-{t.day:02d}_{t.hour:02d}-{t.minute:02d}-{t.second:02d}"
    logging_path = Path(logging_path, current_timestamp + '.log')

    logging.basicConfig(handlers=[logging.FileHandler(logging_path, 'w', 'utf-8')],
                        level=common_logging_level,
                        format='%(asctime)s %(levelname)s: %(message)s',
                        datefmt='%H:%M:%S')
    logger = logging.getLogger('algobattle')

    if not silent:
        # Pipe logging out to console
        _consolehandler = logging.StreamHandler(stream=sys.stderr)
        _consolehandler.setLevel(common_logging_level)

        _consolehandler.setFormatter(logging.Formatter('%(message)s'))

        logger.addHandler(_consolehandler)

    logger.info(f"You can find the log files for this run in {logging_path}")
    return logger


@dataclass
class ProgramConfig:
    problem: Path
    display: Literal["silent", "logs", "ui"]
    logs: Path
    teams: list[TeamInfo]




_T = TypeVar("_T")
def _optional(f: Callable[[str], _T]) -> Callable[[str], _T | None]:
    def inner(arg: str) -> _T | None:
        if arg.lower() == "none":
            return None
        else:
            return f(arg)
    return inner


_float = _optional(float)
_int = _optional(int)


def parse_cli_args(args: list[str]) -> tuple[ProgramConfig, MatchConfig, BattleWrapper.Config]:
    """Parse a given CLI arg list into config objects."""

    parser = ArgumentParser()
    parser.add_argument("path", type=check_path, help="Path to the needed files if they aren't specified seperately.")
    parser.add_argument("--problem", type=partial(check_path, type="dir"), help="Path to a problem folder.")
    parser.add_argument("--config", type=partial(check_path, type="file"), help="Path to a config file.")
    parser.add_argument("--logging_path", type=partial(check_path, type="dir"), help="Folder that logs are written into.")
    parser.add_argument("--display", choices=["silent", "logs", "ui"], help="Choose output mode, silent disables all output, logs displays the battle logs on STDERR, ui displays a small GUI showing the progress of the battle.")

    parser.add_argument("--verbose", "-v", dest="verbose", action="store_const", const=True, help="More detailed log output.")
    parser.add_argument("--safe_build", action="store_const", const=True, help="Isolate docker image builds from each other. Significantly slows down battle setup but closes prevents images from interfering with each other.")

    parser.add_argument("--battle_type", type=BattleWrapper.get_wrapper, choices=[Iterated, Averaged], help="Type of battle wrapper to be used.")
    parser.add_argument("--rounds", type=int, help="Number of rounds that are to be fought in the battle (points are split between all rounds).")
    parser.add_argument("--points", type=int, help="number of points distributed between teams.")

    parser.add_argument("--timeout_build", type=_float, help="Timeout for the build step of each docker image.")
    parser.add_argument("--timeout_generator", type=_float, help="Time limit for the generator execution.")
    parser.add_argument("--timeout_solver", type=_float, help="Time limit for the solver execution.")
    parser.add_argument("--space_generator", type=_int, help="Memory limit for the generator execution, in MB.")
    parser.add_argument("--space_solver", type=_int, help="Memory limit the solver execution, in MB.")
    parser.add_argument("--cpus", type=int, help="Number of cpu cores used for each docker container execution.")
    

    # battle wrappers have their configs automatically added to the CLI args
    for wrapper in (Iterated, Averaged):
        group = parser.add_argument_group(wrapper.name())
        for name, kwargs in wrapper.Config.as_argparse_args():
            group.add_argument(f"--{wrapper.name().lower()}_{name}", **kwargs)

    parsed = parser.parse_args(args)

    cfg_path = cast(Path, getattr(parsed, "config", parsed.path / "config.toml"))
    if cfg_path.is_file():
        with open(cfg_path, "rb") as file:
            try:
                config = tomli.load(file)
            except tomli.TOMLDecodeError as e:
                raise ValueError(f"The config file at {cfg_path} is not a properly formatted TOML file!\n{e}")
    else:
        config = {}

    if "teams" in config:
        team_specs = config["teams"]
    else:
        team_specs = [{
            "name": parsed.path.name,
            "generator": parsed.path / "generator",
            "solver": parsed.path / "solver",
        }]
    teams = []
    for spec in team_specs:
        try:
            name = spec["name"]
            gen = check_path(spec["generator"], type="dir")
            sol = check_path(spec["solver"], type="dir")
            teams.append(TeamInfo(name=name, generator=gen, solver=sol))
        except TypeError:
            raise ValueError(f"The config file at {cfg_path} is incorrectly formatted!")
    
    program_config = ProgramConfig(
        teams=teams,
        problem=getattr(parsed, "problem", cast(Path, parsed.path)),
        display=getattr(parsed, "display", "logs"),
        logs=getattr(parsed, "logging_path", Path.home() / ".algobattle_logs"),
    )

    match_config = MatchConfig.from_dict(config.get("algobattle", {}))
    for name in vars(match_config):
        if hasattr(parsed, name):
            setattr(match_config, name, getattr(parsed, name))

    wrapper_config = match_config.battle_type.Config(**config.get(match_config.battle_type.name(), {}))
    for name in vars(match_config):
        cli_name = f"--{match_config}_{name}"
        if hasattr(parsed, cli_name):
            setattr(match_config, name, getattr(parsed, cli_name))

    return program_config, match_config, wrapper_config


def main():
    """Entrypoint of `algobattle` CLI."""
    try:
        program_config, match_config, wrapper_config = parse_cli_args(sys.argv[1:])
        logger = setup_logging(program_config.logs, match_config.verbose, program_config.display != "logs")

    except KeyboardInterrupt:
        raise SystemExit("Received keyboard interrupt, terminating execution.")

    try:
        problem = import_problem_from_path(program_config.problem)
        with TeamHandler.build(program_config.teams) as teams, ExitStack() as stack:
            if program_config.display == "ui":
                ui = Ui()
                stack.enter_context(ui)
            else:
                ui = None

            result = run_match(match_config, wrapper_config, problem, teams, ui)

            logger.info('#' * 78)
            logger.info(str(result))
            if match_config.points > 0:
                points = result.calculate_points(match_config.points)
                for team, pts in points.items():
                    logger.info(f"Group {team} gained {pts:.1f} points.")

    except KeyboardInterrupt:
        logger.critical("Received keyboard interrupt, terminating execution.")


if __name__ == "__main__":
    main()
