"""Main battle script. Executes all possible types of battles, see battle --help for all options."""
from __future__ import annotations
from argparse import ArgumentParser, Namespace
from contextlib import ExitStack
from functools import partial
import sys
import logging
import datetime as dt
from pathlib import Path
from typing import Any, ClassVar, Literal, Mapping, Self
import tomllib

from pydantic import BaseModel, validator

from algobattle.battle import Battle
from algobattle.docker_util import DockerConfig, Image
from algobattle.match import MatchConfig, Match
from algobattle.problem import Problem
from algobattle.team import TeamHandler, TeamInfo
from algobattle.ui import Ui
from algobattle.util import check_path


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

    display: Literal["silent", "logs", "ui"] = "logs"
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
        " ui displays a small GUI showing the progress of the battle. Default: logs.",
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


def main():
    """Entrypoint of `algobattle` CLI."""
    try:
        problem, config = parse_cli_args(sys.argv[1:])
        logger = setup_logging(config.execution.logging_path, config.execution.verbose, config.execution.display != "logs")

    except KeyboardInterrupt:
        raise SystemExit("Received keyboard interrupt, terminating execution.")

    try:
        problem = Problem.import_from_path(problem)
        with TeamHandler.build(config.teams, problem, config.docker, config.execution.safe_build) as teams, ExitStack() as stack:
            if config.execution.display == "ui":
                ui = Ui()
                stack.enter_context(ui)
            else:
                ui = None

            result = Match.run(config.match, config.battle_config, problem, teams, ui)

            logger.info("#" * 78)
            logger.info(result.display())
            if config.match.points > 0:
                points = result.calculate_points()
                for team, pts in points.items():
                    logger.info(f"Team {team} gained {pts:.1f} points.")

    except KeyboardInterrupt:
        logger.critical("Received keyboard interrupt, terminating execution.")


if __name__ == "__main__":
    main()
