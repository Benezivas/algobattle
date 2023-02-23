"""Main battle script. Executes all possible types of battles, see battle --help for all options."""
from __future__ import annotations
from argparse import ArgumentParser, Namespace
from contextlib import ExitStack
from functools import partial
import sys
import logging
import datetime as dt
from pathlib import Path
from typing import Any, ClassVar, Literal
import tomllib

from pydantic import BaseModel, Field

from algobattle.battle import Battle
from algobattle.docker_util import DockerConfig, RunParameters
from algobattle.match import MatchConfig, Match
from algobattle.problem import Problem
from algobattle.team import TeamHandler, TeamInfo
from algobattle.ui import Ui
from algobattle.util import check_path, getattr_set


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


class Config(BaseModel):
    """Pydantic model to parse the config file."""

    problem: Path
    teams: list[TeamInfo] = []
    display: Literal["silent", "logs", "ui"] = "logs"
    logging_path: Path = Field(default=Path.home() / ".algobattle_logs", cli_alias="logging_path")
    match: MatchConfig
    docker: DockerConfig

    _cli_mapping: ClassVar[dict[str, Any]] = {
        "teams": None,
        "docker": {
            "generator": {
                "timeout": "generator_timeout",
                "spcace": "generator_space",
                "cpus": "generator_cpus",
            },
            "solver": {
                "timeout": "space_timeout",
                "spcace": "space_space",
                "cpus": "space_cpus",
            },
        },
    }

    def include_cli(self, cli: Namespace) -> None:
        """Updates itself using the data in the passed argparse namespace."""
        Config._include_cli(self, cli, self._cli_mapping)

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


def parse_cli_args(args: list[str]) -> tuple[Config, Battle.Config]:
    """Parse a given CLI arg list into config objects."""
    parser = ArgumentParser()
    parser.add_argument("problem", type=check_path, help="Path to a folder with the problem file.")
    parser.add_argument("--config", type=partial(check_path, type="file"), help="Path to a config file, defaults to '{problem} / config.toml'.")
    parser.add_argument("--logging_path", type=partial(check_path, type="dir"), help="Folder that logs are written into, defaults to '~/.algobattle_logs'.")
    parser.add_argument("--display", choices=["silent", "logs", "ui"], help="Choose output mode, silent disables all output, logs displays the battle logs on STDERR, ui displays a small GUI showing the progress of the battle. Default: logs.")

    parser.add_argument("--verbose", "-v", dest="verbose", action="store_const", const=True, help="More detailed log output.")
    parser.add_argument("--safe_build", action="store_const", const=True, help="Isolate docker image builds from each other. Significantly slows down battle setup but closes prevents images from interfering with each other.")

    parser.add_argument("--battle_type", choices=[name.lower() for name in Battle.all()], help="Type of battle to be used.")
    parser.add_argument("--rounds", type=int, help="Number of rounds that are to be fought in the battle (points are split between all rounds).")
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

    if parsed.battle_type is not None:
        parsed.battle_type = Battle.all()[parsed.battle_type]
    cfg_path = parsed.config if parsed.config is not None else parsed.problem / "config.toml"
    if cfg_path.is_file():
        with open(cfg_path, "rb") as file:
            try:
                config_dict = tomllib.load(file)
            except tomllib.TOMLDecodeError as e:
                raise ValueError(f"The config file at {cfg_path} is not a properly formatted TOML file!\n{e}")
    else:
        config_dict = {}

    config = Config.parse_obj(config_dict)
    config.include_cli(parsed)

    if not config.teams:
        config.teams.append(TeamInfo(
            name="team_0",
            generator=config.problem / "generator",
            solver=config.problem / "solver",
        ))

    battle_type = config.match.battle_type
    battle_name = battle_type.name().lower()
    battle_config_dict = config_dict.get(battle_name, {})
    battle_config = battle_type.Config.parse_obj(battle_config_dict)
    for name in battle_config.__fields__:
        cli_name = f"{battle_name}_{name}"
        if getattr(parsed, cli_name) is not None:
            setattr(battle_config, name, getattr(parsed, cli_name))

    return config, battle_config


def main():
    """Entrypoint of `algobattle` CLI."""
    try:
        config, battle_config = parse_cli_args(sys.argv[1:])
        logger = setup_logging(config.logging_path, config.match.verbose, config.display != "logs")

    except KeyboardInterrupt:
        raise SystemExit("Received keyboard interrupt, terminating execution.")

    try:
        problem = Problem.import_from_path(config.problem)
        with TeamHandler.build(config.teams, problem, config.docker) as teams, ExitStack() as stack:
            if config.display == "ui":
                ui = Ui()
                stack.enter_context(ui)
            else:
                ui = None

            result = Match.run(config.match, battle_config, problem, teams, ui)

            logger.info('#' * 78)
            logger.info(result.display())
            if config.match.points > 0:
                points = result.calculate_points(config.match.points)
                for team, pts in points.items():
                    logger.info(f"Group {team} gained {pts:.1f} points.")

    except KeyboardInterrupt:
        logger.critical("Received keyboard interrupt, terminating execution.")


if __name__ == "__main__":
    main()
